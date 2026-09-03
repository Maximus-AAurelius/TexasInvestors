"""Mandatory testing requirement #3: run the matching pipeline 3x on the
same combined dataset and confirm identical output. match.py is pure/
deterministic (no AI, no randomness) so any variance is a bug.

Usage (PowerShell, from the project root):
    python scripts\\check_pipeline_determinism.py path\\to\\dataset.json

The dataset file is a JSON list of objects matching LeadRecord's fields,
e.g. what you'd get from dumping run.py's all_records before matching.
"""
import argparse
import json
import sys

sys.path.insert(0, ".")

from match import cluster_records
from models import LeadRecord


def load_records(path: str):
    with open(path) as f:
        raw = json.load(f)
    return [LeadRecord(**r) for r in raw]


def fingerprint(leads):
    return [(l.address, l.owner_name, l.county, l.distress_score, tuple(sorted(l.sources_hit)))
            for l in leads]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", help="path to a JSON dump of LeadRecord dicts")
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()

    records = load_records(args.dataset)
    fingerprints = []
    for i in range(args.runs):
        leads = cluster_records(records)
        fingerprints.append(fingerprint(leads))
        print(f"run {i + 1}: {len(leads)} matched leads")

    if all(fp == fingerprints[0] for fp in fingerprints):
        print("PASS: identical output across all runs")
    else:
        print("FAIL: output differs between runs — match.py has a non-determinism bug")
        sys.exit(1)


if __name__ == "__main__":
    main()
