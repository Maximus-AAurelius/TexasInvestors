"""Rank HCAD's full Harris County bulk roll (data/hcad/real_acct.txt +
owners.txt — see fetch_hcad_bulk_data.py) down to a top-N absentee-owner
lead list, and write it in manual_import.py's CSV schema so it drops
straight into the main pipeline:

    python scripts\\hcad_top_absentee_leads.py
    python run.py --manual-csv output\\hcad_top_absentee_leads.csv

Filters applied, in order:
  1. Residential only — state_class in {A1, A2, A3, A4} (A1 = single-
     family, the overwhelming majority at ~1.16M of ~1.6M parcels in
     the 2026 roll; A2-A4 are mobile home / townhome / other small-
     residential variants). Excludes commercial, vacant land, etc. —
     not what a residential wholesaler is after.
  2. Absentee — normalized mailing address != normalized situs address
     (reuses normalize.py, the same logic match.py uses, so "absentee"
     here means the same thing it means everywhere else in this
     project).
  3. Value floor — tot_mkt_val >= MIN_MARKET_VALUE, to drop slivers/
     easements/degenerate parcels that technically pass the above but
     aren't a real house.

Ranking (transparent, adjustable — see WEIGHTS below): primarily by
years since last ownership change (new_own_dt) — long-held absentee
property is a reasonable proxy for "landlord who's had enough,"
"inherited and never dealt with," or built-up equity — with an
out-of-state-mailing-address bonus (an even stronger absentee signal)
and market value as a tiebreaker. This is one reasonable scoring
scheme, not the only valid one — adjust WEIGHTS/filters to taste.
"""
import csv
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rapidfuzz import fuzz

from normalize import normalize_address

ADDRESS_MATCH_THRESHOLD = 90  # same threshold match.py uses

DATA_DIR = Path(__file__).parent.parent / "data" / "hcad"
REAL_ACCT_PATH = DATA_DIR / "real_acct.txt"
OWNERS_PATH = DATA_DIR / "owners.txt"
OUT_PATH = Path(__file__).parent.parent / "output" / "hcad_top_absentee_leads.csv"

RESIDENTIAL_CLASSES = {"A1", "A2", "A3", "A4"}
MIN_MARKET_VALUE = 30_000
TOP_N = 100

WEIGHTS = {
    "years_owned": 1.0,
    "out_of_state_bonus": 5.0,   # roughly "5 extra years" of signal
    "value_tiebreak": 1e-7,      # tiny nudge, only matters on near-ties
}

TODAY = date.today()


def load_primary_owners(path) -> dict:
    owners = {}
    with open(path, encoding="latin-1", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            if row.get("ln_num") == "1":
                owners[row["acct"]] = row["name"].strip()
    return owners


def parse_date(raw: str):
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%m/%d/%Y").date()
    except ValueError:
        return None


def build_site_address(row: dict) -> str:
    """Full situs address for display (street + city + zip)."""
    parts = [row.get("site_addr_1", ""), row.get("site_addr_2", ""), row.get("site_addr_3", "")]
    return " ".join(p.strip() for p in parts if p and p.strip())


def build_mail_address(row: dict) -> str:
    """Full mailing address for display (street + city + state + zip)."""
    parts = [
        row.get("mail_addr_1", ""), row.get("mail_addr_2", ""),
        row.get("mail_city", ""), row.get("mail_state", ""), row.get("mail_zip", ""),
    ]
    return " ".join(p.strip() for p in parts if p and p.strip())


def is_absentee(row: dict) -> bool:
    """Compare just the street-address line (site_addr_1 vs mail_addr_1)
    with fuzzy matching, not the full multi-field address with exact
    equality. An earlier version compared full addresses (street + city
    + state + zip) with exact string equality and flagged 72% of all
    residential parcels as absentee — city/zip formatting differences
    (zip+4 vs zip5, "TX" present in one but not the other, etc.) are
    noise, not a real absentee signal, and killed exact-match comparison
    almost everywhere. Street-only + fuzzy (same threshold match.py
    uses elsewhere) is the correct comparison.
    """
    site_street = row.get("site_addr_1", "").strip()
    mail_street = row.get("mail_addr_1", "").strip()
    if not site_street or not mail_street:
        return False
    score = fuzz.WRatio(normalize_address(site_street), normalize_address(mail_street))
    return score < ADDRESS_MATCH_THRESHOLD


def main():
    print(f"Loading owner names from {OWNERS_PATH.name} ...")
    owners = load_primary_owners(OWNERS_PATH)
    print(f"  {len(owners):,} accounts with a primary owner")

    print(f"Scanning {REAL_ACCT_PATH.name} (this is the big one, ~1.6M rows) ...")
    candidates = []
    total = 0
    with open(REAL_ACCT_PATH, encoding="latin-1", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            total += 1
            if total % 250_000 == 0:
                print(f"  ...{total:,} rows scanned, {len(candidates):,} candidates so far")

            if row.get("state_class") not in RESIDENTIAL_CLASSES:
                continue

            try:
                market_val = float(row.get("tot_mkt_val") or 0)
            except ValueError:
                market_val = 0
            if market_val < MIN_MARKET_VALUE:
                continue

            if not is_absentee(row):
                continue  # owner-occupied (or a data gap — either way, not a lead)

            site_addr = build_site_address(row)
            mail_addr = build_mail_address(row)

            new_own_dt = parse_date(row.get("new_own_dt"))
            years_owned = (TODAY - new_own_dt).days / 365.25 if new_own_dt else 0
            out_of_state = (row.get("mail_state") or "").strip().upper() not in ("TX", "")

            score = (
                years_owned * WEIGHTS["years_owned"]
                + (WEIGHTS["out_of_state_bonus"] if out_of_state else 0)
                + market_val * WEIGHTS["value_tiebreak"]
            )

            owner_name = owners.get(row["acct"], row.get("mailto", "")).strip()
            if not owner_name:
                continue

            candidates.append({
                "score": score,
                "address": row.get("site_addr_1", "").strip(),
                "owner_name": owner_name,
                "county": "Harris",
                "mailing_address": mail_addr,
                "years_owned": round(years_owned, 1),
                "market_value": market_val,
                "out_of_state": out_of_state,
            })

    print(f"Scanned {total:,} total rows. {len(candidates):,} residential absentee-owner candidates found.")

    candidates.sort(key=lambda c: c["score"], reverse=True)
    top = candidates[:TOP_N]

    OUT_PATH.parent.mkdir(exist_ok=True)
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "address", "owner_name", "source_type", "county",
            "date_recorded", "amount_owed", "case_no", "sale_date", "mailing_address",
        ])
        writer.writeheader()
        for c in top:
            writer.writerow({
                "address": c["address"],
                "owner_name": c["owner_name"],
                "source_type": "absentee_owner",
                "county": c["county"],
                "date_recorded": "",
                "amount_owed": "",
                "case_no": "",
                "sale_date": "",
                "mailing_address": c["mailing_address"],
            })

    print(f"Wrote top {len(top)} to {OUT_PATH}")
    print(f"Top 5 by score: {[(c['address'], c['years_owned'], c['out_of_state']) for c in top[:5]]}")


if __name__ == "__main__":
    main()
