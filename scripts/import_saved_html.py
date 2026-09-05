"""Convert a saved record table to a reviewed-source CSV, without fetching URLs."""
import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from models import LeadRecord, VALID_COUNTIES, VALID_SOURCE_TYPES
from site_adapters.scrapling_html import extract_table


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path)
    parser.add_argument("--county", choices=sorted(VALID_COUNTIES), required=True)
    parser.add_argument("--source-type", choices=sorted(VALID_SOURCE_TYPES), required=True)
    parser.add_argument("--source-url", required=True, help="Provenance only; never fetched")
    parser.add_argument("--table", default="table")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Output exists; choose a new filename to preserve previous imports")
    if args.html.stat().st_size > 5_000_000:
        parser.error("Saved HTML exceeds 5 MB")
    mapping = {"address": "address", "property address": "address", "owner": "owner_name",
               "owner name": "owner_name", "mailing address": "mailing_address", "case number": "case_no"}
    try:
        rows = extract_table(args.html.read_text(encoding="utf-8-sig"), mapping, args.table)
        for row in rows:
            row.update(county=args.county, source_type=args.source_type, source_url=args.source_url)
            LeadRecord(**row)
            row["retrieved_at"] = datetime.now(timezone.utc).isoformat()
            row["verification_status"] = "unreviewed"
    except (ValueError, TypeError) as exc:
        parser.error(str(exc))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=sorted({key for row in rows for key in row}))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Imported {len(rows)} records to {args.out}. Review identities before acting.")


if __name__ == "__main__":
    main()
