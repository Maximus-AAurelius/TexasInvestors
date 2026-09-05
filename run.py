"""Orchestrator: run every live adapter, load any manual-import CSVs,
derive absentee-owner leads, match across sources, write the ranked
.docx report, and log the run to the audit table.

Usage (PowerShell, from this folder):
    python run.py
    python run.py --lookback-days 45 --out output\leads.docx
    python run.py --headed                     # watch the browser instead of headless
    python run.py --manual-csv nacogdoches_tax.csv --manual-csv harris_tax.csv

Two sources are NOT live-scraped, by design — see README for why:
  - Harris tax-delinquent (caopay.harriscountytx.gov) is reCAPTCHA-gated
  - All Nacogdoches County sources: esearch.nacocad.org's own robots.txt
    disallows /Search/ and /Property/; nacogdoches.tx.publicsearch.us
    (probate, trustee-sale) disallows / entirely
Feed those in via --manual-csv instead (see site_adapters/manual_import.py
for the expected columns).

Harris foreclosure (trustee-sale) postings are NOT part of this pipeline
— the county's Foreclosures search only exposes Doc ID/Sale Date/File
Date (no address or owner; the actual notice is a scanned image), so
there's no join key for match.py. Pull those separately:
    python scripts\\pull_foreclosure_postings.py 2026 10
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

from audit_log import log_run
from docgen import write_csv, write_docx
from enrich import enrich_leads
from match import cluster_records
from models import LeadRecord, SOURCE_TAX_DELINQUENT
from site_adapters.absentee_owner import derive_absentee_owner_records
from site_adapters.harris_probate import HarrisProbateAdapter
from site_adapters.manual_import import load_manual_csv

OUTPUT_DIR = Path(__file__).parent / "output"


def run_adapter_safely(adapter, label: str) -> list:
    try:
        records = adapter.run()
        print(f"[{label}] {len(records)} records")
        return records
    except Exception as exc:
        print(f"[{label}] FAILED: {exc}", file=sys.stderr)
        return []


def main():
    parser = argparse.ArgumentParser(description="TX distress-lead pipeline")
    parser.add_argument("--lookback-days", type=int, default=30,
                         help="days back to search for probate/trustee-sale filings")
    parser.add_argument("--out", type=str, default=None,
                         help="output .docx path (default: output/leads_<timestamp>.docx)")
    parser.add_argument("--headed", action="store_true",
                         help="run browsers with a visible window instead of headless")
    parser.add_argument("--manual-csv", action="append", default=[],
                         help="path to a manually-collected CSV (repeatable) — see "
                              "site_adapters/manual_import.py for the expected columns")
    parser.add_argument("--no-enrich", action="store_true",
                         help="skip the HCAD address-recovery/backfill pass")
    parser.add_argument("--offline", action="store_true", help="use only manual CSVs and local HCAD data; no website requests")
    args = parser.parse_args()

    headless = not args.headed
    lookback = args.lookback_days

    all_records: list[LeadRecord] = []
    source_counts: dict[str, int] = {}

    adapters = [
        ("harris_probate", HarrisProbateAdapter(lookback_days=lookback, headless=headless)),
    ]
    if args.offline:
        adapters = []

    for label, adapter in adapters:
        records = run_adapter_safely(adapter, label)
        source_counts[label] = len(records)
        all_records.extend(records)

    for csv_path in args.manual_csv:
        records = load_manual_csv(csv_path)
        source_counts[f"manual:{Path(csv_path).name}"] = len(records)
        all_records.extend(records)
        print(f"[manual:{Path(csv_path).name}] {len(records)} records")

    tax_records = [r for r in all_records if r.source_type == SOURCE_TAX_DELINQUENT]
    absentee = derive_absentee_owner_records(tax_records)
    source_counts["absentee_owner"] = len(absentee)
    all_records.extend(absentee)

    print(f"Total raw records: {len(all_records)}")
    matched = cluster_records(all_records)
    print(f"Matched leads: {len(matched)}")

    # Recover addresses for probate leads and backfill HCAD property facts
    # before writing, so the report has no cells pointing at data it does
    # not carry.
    if args.no_enrich:
        print("[enrich] skipped (--no-enrich)")
    else:
        stats = enrich_leads(matched)
        if not stats["index_available"]:
            print("[enrich] HCAD owner index not built — run "
                  "scripts\build_hcad_owner_index.py to recover unknown addresses",
                  file=sys.stderr)
        else:
            print(f"[enrich] {stats['addresses_recovered']} addresses recovered from HCAD, "
                  f"{stats['facts_backfilled']} leads got property facts, "
                  f"{stats['unknown_after']} still unknown "
                  f"(was {stats['unknown_before']})")
        source_counts["enriched_addresses"] = stats["addresses_recovered"]

    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = args.out or str(OUTPUT_DIR / f"leads_{datetime.now().strftime('%Y%m%d_%H%M')}.docx")
    write_docx(matched, out_path)
    csv_path = str(Path(out_path).with_suffix(".csv"))
    write_csv(matched, csv_path)
    print(f"Wrote {out_path}")
    print(f"Wrote {csv_path}")

    log_run(source_counts, len(matched))


if __name__ == "__main__":
    main()
