"""Absentee-owner records are derived from tax-roll data, not scraped
separately: a property is "absentee-owned" when the mailing address on
file doesn't match the property's own address.
"""
from typing import List

from models import LeadRecord, SOURCE_ABSENTEE_OWNER
from normalize import normalize_address


def derive_absentee_owner_records(tax_records: List[LeadRecord]) -> List[LeadRecord]:
    derived = []
    for rec in tax_records:
        if not rec.mailing_address:
            continue
        if normalize_address(rec.mailing_address) == normalize_address(rec.address):
            continue  # owner-occupied, not absentee
        derived.append(LeadRecord(
            address=rec.address,
            owner_name=rec.owner_name,
            source_type=SOURCE_ABSENTEE_OWNER,
            county=rec.county,
            date_recorded=rec.date_recorded,
            mailing_address=rec.mailing_address,
            source_url=rec.source_url,
        ))
    return derived
