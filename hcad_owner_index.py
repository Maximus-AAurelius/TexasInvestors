"""Owner-name -> property lookup against the HCAD bulk roll.

Reads data/hcad/owner_index.db, built by scripts/build_hcad_owner_index.py.
This is the recovery path for leads that arrive with an owner but no
property address -- probate filings, chiefly. No AI calls, no network: the
same rapidfuzz scoring match.py already uses, run against HCAD's own
county-wide owner list.

The index is optional. If the .db has not been built, every lookup returns
no match and the pipeline behaves exactly as it did before, so the report
still generates on a machine that has not downloaded the ~1GB roll.
"""
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from name_match import score_names
from normalize import normalize_owner_name

DB_PATH = Path(__file__).parent / "data" / "hcad" / "owner_index.db"

# Higher than match.py's OWNER_MATCH_THRESHOLD (90) on purpose. That
# threshold joins a probate case onto a property we ALREADY have distress
# evidence for, so a wrong join mislabels an existing lead. This one
# invents the address outright from a county-wide pool of ~2M names, where
# near-collisions between unrelated people are far more likely, so it has
# to clear a higher bar before we put an address in front of the investor.
# Scored by name_match.score_names, not raw fuzz.ratio -- see that module
# for why whole-string ratio cannot be used against the HCAD roll.
DEFAULT_MIN_SCORE = 93

# A candidate must share at least this many normalized name tokens with
# the query (or all of them, for one-token names). Two shared tokens is
# effectively "same surname AND same given name", which is what keeps the
# fuzzy pass small enough to run per-lead.
MIN_SHARED_TOKENS = 2

MIN_TOKEN_LEN = 3

# Candidate generation uses a name's RAREST tokens first, adding tokens
# until their combined index footprint would exceed this many rows. A name
# built entirely from common tokens ("MARIA GARCIA") still gets its two
# rarest, so it always has a candidate set -- it just costs more to scan.
TOKEN_ROW_BUDGET = 300_000
MAX_QUERY_TOKENS = 4

# Guard rail: a name whose token set is so generic that it pulls a huge
# candidate list is not going to produce a trustworthy single match.
MAX_CANDIDATES = 400


@dataclass
class ParcelMatch:
    acct: str
    site_addr: str
    site_city: str
    site_zip: str
    mail_addr: str
    state_class: str
    year_built: Optional[int]
    building_sqft: Optional[int]
    lot_acres: Optional[float]
    assessed_value: Optional[float]
    market_value: Optional[float]
    ownership_change_date: str
    matched_owner_name: str
    score: float

    @property
    def full_address(self) -> str:
        parts = [self.site_addr, self.site_city, self.site_zip]
        return " ".join(p.strip() for p in parts if p and p.strip())


_PARCEL_COLUMNS = (
    "p.acct, p.site_addr, p.site_city, p.site_zip, p.mail_addr, p.state_class, "
    "p.yr_impr, p.bld_ar, p.acreage, p.assessed_val, p.tot_mkt_val, p.new_own_dt, "
    "o.name_raw, o.name_norm"
)


class HcadOwnerIndex:
    """Thin read-only wrapper over owner_index.db.

    Safe to construct when the .db is absent -- `available` is False and
    every lookup returns an empty list.
    """

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = Path(db_path)
        self._conn = None
        if self.db_path.exists():
            self._conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True,
                                         check_same_thread=False)

    @property
    def available(self) -> bool:
        return self._conn is not None

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _select_query_tokens(self, tokens: List[str]) -> List[str]:
        """Rarest tokens first, up to a row budget.

        "SALOME" appears 73 times in the roll and "MARIA" tens of
        thousands; seeking on SALOME first makes the candidate set tiny
        without dropping MARIA from the comparison, which is what the old
        frequency-pruned index got wrong.
        """
        placeholders = ",".join("?" for _ in tokens)
        freqs = dict(self._conn.execute(
            f"SELECT token, freq FROM owner_token_freq WHERE token IN ({placeholders})",
            tokens,
        ).fetchall())
        # Unknown token = not in the roll at all; freq 0 sorts it first and
        # it contributes nothing, which is correct.
        ordered = sorted(tokens, key=lambda t: (freqs.get(t, 0), t))

        selected, used = [], 0
        for token in ordered:
            if len(selected) >= MIN_SHARED_TOKENS and (
                len(selected) >= MAX_QUERY_TOKENS or used + freqs.get(token, 0) > TOKEN_ROW_BUDGET
            ):
                break
            selected.append(token)
            used += freqs.get(token, 0)
        return selected

    def _candidate_rows(self, tokens: List[str]):
        placeholders = ",".join("?" for _ in tokens)
        required = min(MIN_SHARED_TOKENS, len(tokens))
        sql = (
            f"SELECT {_PARCEL_COLUMNS} FROM ("
            f"  SELECT acct FROM owner_token WHERE token IN ({placeholders})"
            f"  GROUP BY acct HAVING COUNT(DISTINCT token) >= ?"
            f"  LIMIT ?"
            f") c "
            f"JOIN parcel p ON p.acct = c.acct "
            f"JOIN owner  o ON o.acct = c.acct"
        )
        return self._conn.execute(sql, (*tokens, required, MAX_CANDIDATES)).fetchall()

    def lookup(self, owner_name: str, min_score: float = DEFAULT_MIN_SCORE,
               limit: int = 5) -> List[ParcelMatch]:
        """Parcels whose owner name matches `owner_name`, best score first.

        An exact match on the normalized name short-circuits the fuzzy
        pass and scores 100.
        """
        if not self.available:
            return []
        query_norm = normalize_owner_name(owner_name)
        if not query_norm:
            return []

        tokens = sorted({t for t in query_norm.split() if len(t) >= MIN_TOKEN_LEN})
        if not tokens:
            return []
        tokens = self._select_query_tokens(tokens)
        if not tokens:
            return []

        matches = []
        seen_accts = set()
        for row in self._candidate_rows(tokens):
            acct, name_norm = row[0], row[13]
            scored = score_names(query_norm, name_norm)
            # Both bars must clear: a high average is not enough if it came
            # from one strong token and a pile of initials.
            if scored.score < min_score or not scored.is_confident:
                continue
            score = scored.score
            # One parcel can carry several owner name lines; keep only the
            # best-scoring line per parcel so a joint deed does not look
            # like several separate properties.
            if acct in seen_accts:
                existing = next(m for m in matches if m.acct == acct)
                if score <= existing.score:
                    continue
                matches.remove(existing)
            seen_accts.add(acct)
            matches.append(ParcelMatch(
                acct=acct, site_addr=row[1], site_city=row[2], site_zip=row[3],
                mail_addr=row[4], state_class=row[5], year_built=row[6],
                building_sqft=row[7], lot_acres=row[8], assessed_value=row[9],
                market_value=row[10], ownership_change_date=row[11],
                matched_owner_name=row[12], score=round(float(score), 1),
            ))

        # Deterministic order: score desc, then market value desc, then
        # acct asc so repeated runs produce byte-identical reports.
        matches.sort(key=lambda m: (-m.score, -(m.market_value or 0), m.acct))
        return matches[:limit]
