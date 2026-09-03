"""Extract verified HCAD facts for the addresses already in the lead set."""
import csv
import json
from datetime import date, datetime
from pathlib import Path

from normalize import normalize_address

ROOT = Path(__file__).parent
REAL_ACCT_PATH = ROOT / "data" / "hcad" / "real_acct.txt"
CACHE_PATH = ROOT / "output" / "hcad_lead_profiles.json"


def _number(value, integer=False):
    try:
        parsed = float((value or "").strip())
        return int(parsed) if integer else parsed
    except (TypeError, ValueError):
        return None


def _date(value):
    try:
        return datetime.strptime((value or "").strip(), "%m/%d/%Y").date()
    except (TypeError, ValueError):
        return None


def _profile(row):
    ownership_date = _date(row.get("new_own_dt"))
    years_owned = round((date.today() - ownership_date).days / 365.25, 1) if ownership_date else None
    return {
        "parcel_id": row.get("acct", "").strip() or None,
        "property_type": row.get("state_class", "").strip() or None,
        "year_improved": _number(row.get("yr_impr"), integer=True),
        "year_built": None,
        "building_sqft": _number(row.get("bld_ar"), integer=True),
        "lot_acres": _number(row.get("acreage")),
        "assessed_value": _number(row.get("assessed_val")),
        "hcad_market_value": _number(row.get("tot_mkt_val")),
        "ownership_change_date": ownership_date.isoformat() if ownership_date else None,
        "ownership_duration_years": years_owned,
        "neighborhood": row.get("Neighborhood_Grp", "").strip() or None,
        "market_area": row.get("Market_Area_1_Dscr", "").strip() or None,
        "source": "HCAD Real_acct_owner bulk roll",
    }


def enrich_leads(leads):
    """Return lead profiles joined by normalized situs address.

    The cache is invalidated when the HCAD source file changes. Only matching
    lead addresses are retained, so the cache stays small and page loads stay
    fast after the first scan.
    """
    addresses = {normalize_address(lead["address"]): lead["id"] for lead in leads}
    if not REAL_ACCT_PATH.exists():
        return {}
    source_stamp = REAL_ACCT_PATH.stat().st_mtime_ns
    try:
        cached = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        if cached.get("source_stamp") == source_stamp:
            return cached.get("profiles", {})
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass

    profiles = {}
    with REAL_ACCT_PATH.open(encoding="latin-1", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            lead_id = addresses.get(normalize_address(row.get("site_addr_1", "")))
            if lead_id and lead_id not in profiles:
                profiles[lead_id] = _profile(row)
    CACHE_PATH.parent.mkdir(exist_ok=True)
    CACHE_PATH.write_text(json.dumps({"source_stamp": source_stamp, "profiles": profiles}, indent=2), encoding="utf-8")
    return profiles