"""CSV-based manual entry for sources that cannot be automated because
the county's robots.txt disallows it (a human looking the record up in
a browser isn't a robots.txt concern — robots.txt governs automated
crawlers, not manual lookups).

Currently used for all Nacogdoches County sources:
  - esearch.nacocad.org disallows /Search/ and /Property/ (its own
    robots.txt, separate from nacocad.org's — confirmed 2026-09-02)
  - nacogdoches.tx.publicsearch.us disallows / entirely (probate,
    trustee-sale)

CSV columns expected: address,owner_name,source_type,date_recorded,
amount_owed,case_no,sale_date,mailing_address
Only address, owner_name, source_type are required; leave the rest
blank if not applicable. source_type must be one of the constants in
models.py (tax_delinquent, probate, trustee_sale, absentee_owner).
"""
import csv
from datetime import datetime
from pathlib import Path
from typing import List

from models import LeadRecord


def _parse_date(raw: str):
    if not raw:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def load_manual_csv(path: str) -> List[LeadRecord]:
    records = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                records.append(LeadRecord(
                    address=row.get("address", "").strip(),
                    owner_name=row.get("owner_name", "").strip(),
                    source_type=row.get("source_type", "").strip(),
                    county=row.get("county", "").strip(),
                    date_recorded=_parse_date(row.get("date_recorded", "").strip()),
                    amount_owed=float(row["amount_owed"]) if row.get("amount_owed") else None,
                    case_no=row.get("case_no") or None,
                    sale_date=_parse_date(row.get("sale_date", "").strip()),
                    mailing_address=row.get("mailing_address") or None,
                ))
            except ValueError as exc:
                print(f"[manual_import] skipping bad row in {Path(path).name}: {row!r} ({exc})")
    return records
