"""Mandatory testing requirement #3: run the matching pipeline 3x on the
same combined dataset and confirm identical output. match.py is pure/
deterministic (no AI, no randomness) so any variance is a bug.

This covers the enrichment pass too (enrich.py, which recovers missing
addresses from the HCAD roll). That pass reads a SQLite index and ranks
candidates by fuzzy score, so it has more room to wobble than match.py
does -- ties are broken by market value and then account number precisely
so it cannot. Skipped automatically when the index has not been built.

Usage (PowerShell, from the project root):
    python scripts\\check_pipeline_determinism.py path\\to\\dataset.json

The dataset file is a JSON list of objects matching LeadRecord's fields,
e.g. what you'd get from dumping run.py's all_records before matching.
"""
import argparse
import json
import sys

sys.path.insert(0, ".")

from enrich import enrich_leads
from hcad_owner_index import HcadOwnerIndex
from match import cluster_records
from models import LeadRecord


def load_records(path: str):
    with open(path) as f:
        raw = json.load(f)
    return [LeadRecord(**r) for r in raw]


def fingerprint(leads):
    return [(l.address, l.owner_name, l.county, l.distress_score,
             tuple(sorted(l.sources_hit)), l.address_source, l.address_confidence,
             l.parcel_id, l.market_value)
            for l in leads]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", help="path to a JSON dump of LeadRecord dicts")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--no-enrich", action="store_true",
                        help="check match.py only, skipping the HCAD enrichment pass")
    args = parser.parse_args()

    records = load_records(args.dataset)
    index = None if args.no_enrich else HcadOwnerIndex()
    if index is not None and not index.available:
        print("note: HCAD owner index not built — checking match.py only")
        index = None

    fingerprints = []
    for i in range(args.runs):
        leads = cluster_records(records)
        recovered = ""
        if index is not None:
            stats = enrich_leads(leads, index=index)
            recovered = f", {stats['addresses_recovered']} addresses recovered"
        fingerprints.append(fingerprint(leads))
        print(f"run {i + 1}: {len(leads)} matched leads{recovered}")

    if all(fp == fingerprints[0] for fp in fingerprints):
        print("PASS: identical output across all runs")
    else:
        stage = "match.py" if index is None else "match.py or enrich.py"
        print(f"FAIL: output differs between runs — {stage} has a non-determinism bug")
        sys.exit(1)


if __name__ == "__main__":
    main()
