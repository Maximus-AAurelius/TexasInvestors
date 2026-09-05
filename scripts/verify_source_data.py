"""Cross-check every displayed HCAD profile against the local source roll."""
import csv
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app
import hcad_profile


def main():
    leads = app.load_leads()
    expected = {lead["hcad"]["parcel_id"]:lead["hcad"] for lead in leads if lead.get("hcad",{}).get("parcel_id")}
    checked = set()
    discrepancies = []
    with hcad_profile.REAL_ACCT_PATH.open(encoding="latin-1", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            account = row.get("acct", "").strip()
            if account not in expected:
                continue
            actual = hcad_profile._profile(row)
            for field in ("building_sqft","property_type","hcad_market_value","year_improved","lot_acres"):
                if actual[field] != expected[account][field]:
                    discrepancies.append({"parcel_id":account,"field":field})
            checked.add(account)
    result = {"properties_loaded":len(leads),"appraisal_profiles":len(expected),"profiles_checked":len(checked),
              "discrepancies":discrepancies,"missing_accounts":sorted(set(expected)-checked),
              "sold_comps_loaded":len(app.get_sales()),
              "scope":"Consistency with local HCAD source file only; current ownership, sold prices, payoff and market value not independently verified"}
    target = app.OUTPUT_DIR / "source-data-validation.json"
    target.write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result))
    if discrepancies or set(expected)-checked:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
