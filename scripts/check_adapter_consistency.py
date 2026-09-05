"""Mandatory testing requirement #1: run one adapter 3x against the live
target and confirm record counts match within ~5% tolerance. Bigger
swings usually mean a broken parser, not real data change.

Usage (PowerShell, from the project root):
    python scripts\\check_adapter_consistency.py harris_probate
    python scripts\\check_adapter_consistency.py harris_foreclosure --runs 3

This script could not import at all before 2026-09-03: it named a class
`HarrisTrusteeSaleAdapter` that had since been renamed to
`HarrisForeclosurePostingsAdapter`, and a `site_adapters.nacogdoches_tax`
module that does not exist (only a stale .pyc in __pycache__ suggested it
ever had). Adapters are registered as factories now, because they do not
share a constructor signature -- the foreclosure adapter needs a year and
month, the probate adapter a lookback window.
"""
import argparse
import sys
import time
from datetime import date

sys.path.insert(0, ".")

from site_adapters.harris_probate import HarrisProbateAdapter
from site_adapters.harris_tax import HarrisTaxDelinquentAdapter
from site_adapters.harris_trustee_sale import HarrisForeclosurePostingsAdapter

TODAY = date.today()

ADAPTERS = {
    "harris_probate": lambda headless: HarrisProbateAdapter(headless=headless),
    # reCAPTCHA-gated, so this will fail. Registered anyway so the failure
    # is explicit rather than the adapter silently going unchecked.
    "harris_tax": lambda headless: HarrisTaxDelinquentAdapter(headless=headless),
    "harris_foreclosure": lambda headless: HarrisForeclosurePostingsAdapter(
        year=TODAY.year, month=TODAY.month, headless=headless),
}

TOLERANCE = 0.05


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("adapter", choices=ADAPTERS.keys())
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()

    counts = []
    for i in range(args.runs):
        adapter = ADAPTERS[args.adapter](not args.headed)
        records = adapter.fetch_postings() if isinstance(adapter, HarrisForeclosurePostingsAdapter) else adapter.run()
        counts.append(len(records))
        print(f"run {i + 1}: {len(records)} records")
        if i < args.runs - 1:
            time.sleep(3)

    avg = sum(counts) / len(counts)
    max_dev = max(abs(c - avg) / avg for c in counts) if avg else 0
    print(f"counts={counts} avg={avg:.1f} max_deviation={max_dev:.1%}")
    if max_dev > TOLERANCE:
        print(f"FAIL: deviation exceeds {TOLERANCE:.0%} tolerance — investigate before trusting this adapter.")
        sys.exit(1)
    print("PASS")


if __name__ == "__main__":
    main()
