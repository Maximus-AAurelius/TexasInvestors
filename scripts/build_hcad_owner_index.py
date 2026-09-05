"""Build a local owner-name -> property lookup from the HCAD bulk roll.

Why this exists: probate filings (harris_probate.py) identify a deceased
OWNER, never a property. Before this index existed, any probate lead whose
owner name did not happen to fuzzy-match an already-addressed lead came out
of match.py labelled "(address unknown - see case_no)" -- which was most of
them, and the report did not even carry a case_no column to look up. HCAD's
own bulk roll already maps every Harris County owner name to that owner's
property, so the address is recoverable locally, with no scraping and no API.

Builds data/hcad/owner_index.db (SQLite):
    parcel       one row per account that has a real situs address
    owner        one row per owner NAME LINE (all ln_num values, not just
                 the primary -- a decedent is often the 2nd name on a
                 joint deed, e.g. "SMITH JOHN & MARY")
    owner_token  inverted index: normalized name token -> acct, so a
                 candidate lookup is an index seek instead of a scan of
                 ~2M owner names

Run once after fetch_hcad_bulk_data.py, and again whenever the roll is
refreshed:

    python scripts\\build_hcad_owner_index.py

Takes a few minutes (real_acct.txt is ~888MB / ~1.6M rows) and produces a
large .db. Both the source files and the .db are gitignored.
"""
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from normalize import normalize_owner_name

DATA_DIR = Path(__file__).parent.parent / "data" / "hcad"
REAL_ACCT_PATH = DATA_DIR / "real_acct.txt"
OWNERS_PATH = DATA_DIR / "owners.txt"
DB_PATH = DATA_DIR / "owner_index.db"

# Common tokens ("MARIA", "SMITH", "LLC") are kept in the index and their
# frequency recorded in owner_token_freq instead. An earlier version
# DELETEd any token appearing more than 20,000 times, to keep a lookup
# from pulling tens of thousands of candidates. That silently destroyed
# recall: "MARIA" was pruned to zero rows, so "CASTILLO MARIA SALOME"
# could only share ONE indexed token with "CASTILLO MARIA C" and never
# reached the two-shared-token bar -- it returned no candidates at all,
# despite the owner sitting right there in the roll. hcad_owner_index.py
# now bounds the work at query time by preferring a name's RAREST tokens,
# which costs nothing in recall.
MIN_TOKEN_LEN = 3
BATCH = 50_000

# HCAD parks parcels it cannot place at street number 0 ("0 IN HARRIS
# COUNTY", "0 CROSBY CEDAR BAYOU RD"). Those are not addresses anyone can
# drive to, so they must not be handed back as a recovered one.
PLACEHOLDER_ADDRESS_PREFIX = "0 "

REAL_ACCT_FIELDS = [
    "acct", "mail_addr_1", "mail_city", "mail_state", "mail_zip",
    "site_addr_1", "site_addr_2", "site_addr_3", "state_class",
    "yr_impr", "bld_ar", "acreage", "assessed_val", "tot_mkt_val", "new_own_dt",
]

SCHEMA = """
DROP TABLE IF EXISTS parcel;
DROP TABLE IF EXISTS owner;
DROP TABLE IF EXISTS owner_token;
DROP TABLE IF EXISTS owner_token_freq;
CREATE TABLE parcel (
    acct TEXT PRIMARY KEY,
    site_addr TEXT,
    site_city TEXT,
    site_zip TEXT,
    mail_addr TEXT,
    state_class TEXT,
    yr_impr INTEGER,
    bld_ar INTEGER,
    acreage REAL,
    assessed_val REAL,
    tot_mkt_val REAL,
    new_own_dt TEXT
);
CREATE TABLE owner (
    acct TEXT,
    ln_num TEXT,
    name_raw TEXT,
    name_norm TEXT
);
CREATE TABLE owner_token (
    token TEXT,
    acct TEXT
);
CREATE TABLE owner_token_freq (
    token TEXT PRIMARY KEY,
    freq INTEGER
);
"""


def _num(value, integer=False):
    try:
        parsed = float((value or "").strip())
        return int(parsed) if integer else parsed
    except (TypeError, ValueError):
        return None


def split_joint_owners(name_raw: str):
    """One HCAD name line -> the individual people on it.

    HCAD writes joint deeds surname-first with the second owner reduced to
    a given name: "GIACONE JOSEPH W & BEVERLY" is Joseph and Beverly
    Giacone, and "SMITH JOHN & MARY A" is John and Mary A Smith.
    normalize_owner_name() drops the "&" as noise, which flattens both
    people into one bag of words -- so a probate filing for Joseph Wade
    Giacone had to compete against BEVERLY as an unexplained extra token.

    Indexing each person separately keeps the ampersand's meaning. The
    original full line is indexed too, so nothing is lost if this split
    guesses wrong.
    """
    parts = [p.strip() for p in re.split(r"\s*(?:&|\bAND\b)\s*", name_raw.upper()) if p.strip()]
    if len(parts) < 2:
        return []

    lead_tokens = parts[0].split()
    if not lead_tokens:
        return []
    surname = lead_tokens[0]

    names = [parts[0]]
    for part in parts[1:]:
        tokens = part.split()
        if not tokens:
            continue
        # A trailing segment that already repeats the surname is a complete
        # name; a bare given name inherits it.
        names.append(part if tokens[0] == surname else f"{surname} {part}")
    return names


def _header_index(path):
    """Field-name -> column-index map. We index by position and split on
    tab manually rather than using csv.DictReader: DictReader builds a
    dict per row and roughly triples wall time on an 888MB file.
    """
    with open(path, encoding="latin-1") as handle:
        header = handle.readline().rstrip("\n").split("\t")
    return {name: i for i, name in enumerate(header)}


def load_parcels(conn):
    idx = _header_index(REAL_ACCT_PATH)
    missing = [f for f in REAL_ACCT_FIELDS if f not in idx]
    if missing:
        raise SystemExit(f"real_acct.txt is missing expected columns: {missing}")

    cols = {name: idx[name] for name in REAL_ACCT_FIELDS}
    max_col = max(cols.values())
    rows, total, kept = [], 0, 0

    with open(REAL_ACCT_PATH, encoding="latin-1") as handle:
        handle.readline()  # header
        for line in handle:
            total += 1
            parts = line.rstrip("\n").split("\t")
            if len(parts) <= max_col:
                continue

            site_addr = parts[cols["site_addr_1"]].strip()
            if not site_addr or site_addr.startswith(PLACEHOLDER_ADDRESS_PREFIX):
                continue  # no usable situs address = nothing to recover; skip

            kept += 1
            mail = " ".join(p for p in (
                parts[cols["mail_addr_1"]].strip(), parts[cols["mail_city"]].strip(),
                parts[cols["mail_state"]].strip(), parts[cols["mail_zip"]].strip(),
            ) if p)
            rows.append((
                parts[cols["acct"]].strip(),
                site_addr,
                parts[cols["site_addr_2"]].strip(),
                parts[cols["site_addr_3"]].strip(),
                mail,
                parts[cols["state_class"]].strip(),
                _num(parts[cols["yr_impr"]], integer=True),
                _num(parts[cols["bld_ar"]], integer=True),
                _num(parts[cols["acreage"]]),
                _num(parts[cols["assessed_val"]]),
                _num(parts[cols["tot_mkt_val"]]),
                parts[cols["new_own_dt"]].strip(),
            ))
            if len(rows) >= BATCH:
                conn.executemany("INSERT OR REPLACE INTO parcel VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
                rows.clear()
                print(f"  ...{total:,} rows scanned, {kept:,} parcels kept")

    if rows:
        conn.executemany("INSERT OR REPLACE INTO parcel VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    print(f"Parcels: {kept:,} kept out of {total:,} rows scanned")
    return kept


def load_owners(conn):
    idx = _header_index(OWNERS_PATH)
    for field in ("acct", "ln_num", "name"):
        if field not in idx:
            raise SystemExit(f"owners.txt is missing expected column: {field}")

    known = {row[0] for row in conn.execute("SELECT acct FROM parcel")}
    print(f"  {len(known):,} accounts available to join against")

    owner_rows, token_rows, total, kept = [], [], 0, 0
    max_col = max(idx["acct"], idx["ln_num"], idx["name"])
    with open(OWNERS_PATH, encoding="latin-1") as handle:
        handle.readline()
        for line in handle:
            total += 1
            parts = line.rstrip("\n").split("\t")
            if len(parts) <= max_col:
                continue
            acct = parts[idx["acct"]].strip()
            if acct not in known:
                continue
            name_raw = parts[idx["name"]].strip()
            name_norm = normalize_owner_name(name_raw)
            if not name_norm:
                continue

            kept += 1
            ln_num = parts[idx["ln_num"]].strip()
            indexed_tokens = set()
            # The full line, plus each person on a joint deed. name_raw
            # stays the original either way so the report shows what HCAD
            # actually records.
            for variant in [name_norm] + [normalize_owner_name(n)
                                          for n in split_joint_owners(name_raw)]:
                if not variant:
                    continue
                owner_rows.append((acct, ln_num, name_raw, variant))
                indexed_tokens.update(t for t in variant.split() if len(t) >= MIN_TOKEN_LEN)
            token_rows.extend((token, acct) for token in indexed_tokens)

            if len(owner_rows) >= BATCH:
                conn.executemany("INSERT INTO owner VALUES (?,?,?,?)", owner_rows)
                conn.executemany("INSERT INTO owner_token VALUES (?,?)", token_rows)
                owner_rows.clear()
                token_rows.clear()
                print(f"  ...{total:,} owner lines scanned, {kept:,} indexed")

    if owner_rows:
        conn.executemany("INSERT INTO owner VALUES (?,?,?,?)", owner_rows)
        conn.executemany("INSERT INTO owner_token VALUES (?,?)", token_rows)
    conn.commit()
    print(f"Owners: {kept:,} name lines indexed out of {total:,}")
    return kept


def build_frequencies_and_index(conn):
    print("Recording token frequencies ...")
    conn.execute(
        "INSERT INTO owner_token_freq (token, freq) "
        "SELECT token, COUNT(*) FROM owner_token GROUP BY token"
    )
    conn.commit()
    print("Creating indexes (slowest step) ...")
    conn.execute("CREATE INDEX idx_owner_token ON owner_token(token)")
    conn.execute("CREATE INDEX idx_owner_norm ON owner(name_norm)")
    conn.execute("CREATE INDEX idx_owner_acct ON owner(acct)")
    conn.commit()


def main():
    for path in (REAL_ACCT_PATH, OWNERS_PATH):
        if not path.exists():
            raise SystemExit(f"Missing {path}. Run scripts/fetch_hcad_bulk_data.py first.")

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    # Bulk-load settings: this DB is a derived artifact rebuilt from the
    # roll on demand, so durability during the build buys nothing.
    conn.execute("PRAGMA journal_mode = OFF")
    conn.execute("PRAGMA synchronous = OFF")
    conn.executescript(SCHEMA)

    print(f"Scanning {REAL_ACCT_PATH.name} ...")
    load_parcels(conn)
    print(f"Scanning {OWNERS_PATH.name} ...")
    load_owners(conn)
    build_frequencies_and_index(conn)
    conn.close()
    print(f"Wrote {DB_PATH} ({DB_PATH.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
