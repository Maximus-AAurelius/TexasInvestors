"""Address recovery + HCAD backfill, driven off a tiny in-memory index.

Builds the same schema scripts/build_hcad_owner_index.py writes, so these
tests exercise the real SQL and the real fuzzy scoring without needing the
1GB county roll on disk.
"""
import sqlite3

import pytest

from enrich import MAX_AMBIGUOUS_PARCELS, enrich_leads
from hcad_owner_index import HcadOwnerIndex
from match import (
    ADDRESS_SOURCE_FILED,
    ADDRESS_SOURCE_HCAD,
    ADDRESS_SOURCE_UNKNOWN,
    MatchedLead,
    UNKNOWN_ADDRESS_LABEL,
)
from models import LeadRecord, SOURCE_PROBATE
from normalize import normalize_owner_name
from scripts.build_hcad_owner_index import MIN_TOKEN_LEN, SCHEMA


def build_index(tmp_path, parcels):
    """parcels: list of (acct, site_addr, city, zip, owner_name, market_value)"""
    db_path = tmp_path / "owner_index.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    for acct, site_addr, city, zipcode, owner, market in parcels:
        conn.execute(
            "INSERT OR REPLACE INTO parcel VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (acct, site_addr, city, zipcode, "PO BOX 1 HOUSTON TX 77001",
             "A1", 1975, 1450, 0.15, market * 0.9, market, "01/01/2005"),
        )
        norm = normalize_owner_name(owner)
        conn.execute("INSERT INTO owner VALUES (?,?,?,?)", (acct, "1", owner, norm))
        for token in set(norm.split()):
            if len(token) >= MIN_TOKEN_LEN:
                conn.execute("INSERT INTO owner_token VALUES (?,?)", (token, acct))
    conn.execute(
        "INSERT INTO owner_token_freq (token, freq) "
        "SELECT token, COUNT(*) FROM owner_token GROUP BY token"
    )
    conn.execute("CREATE INDEX idx_owner_token ON owner_token(token)")
    conn.execute("CREATE INDEX idx_owner_norm ON owner(name_norm)")
    conn.execute("CREATE INDEX idx_owner_acct ON owner(acct)")
    conn.commit()
    conn.close()
    return HcadOwnerIndex(db_path)


def unknown_probate_lead(owner_name, county="Harris", case_no="470000"):
    record = LeadRecord(address="", owner_name=owner_name,
                        source_type=SOURCE_PROBATE, county=county, case_no=case_no)
    return MatchedLead(UNKNOWN_ADDRESS_LABEL, owner_name, county, 1,
                       [SOURCE_PROBATE], [record],
                       address_source=ADDRESS_SOURCE_UNKNOWN)


def test_probate_decedent_gets_address_from_hcad(tmp_path):
    index = build_index(tmp_path, [
        ("0011", "4614 ROBERTSON ST", "HOUSTON", "77009", "CARRENO PAUL VICENTE", 210_000),
    ])
    leads = [unknown_probate_lead("IN THE ESTATE OF: PAUL VICENTE CARRENO, DECEASED")]

    stats = enrich_leads(leads, index=index)

    assert stats["addresses_recovered"] == 1
    assert stats["unknown_after"] == 0
    assert leads[0].address == "4614 ROBERTSON ST HOUSTON 77009"
    assert leads[0].address_source == ADDRESS_SOURCE_HCAD
    assert leads[0].address_confidence == 100.0
    assert leads[0].parcel_id == "0011"
    assert leads[0].market_value == 210_000
    assert leads[0].year_built == 1975


def test_recovered_lead_still_reports_its_case_number(tmp_path):
    index = build_index(tmp_path, [
        ("0011", "4614 ROBERTSON ST", "HOUSTON", "77009", "CARRENO PAUL VICENTE", 210_000),
    ])
    leads = [unknown_probate_lead("PAUL VICENTE CARRENO, DECEASED", case_no="470123")]
    enrich_leads(leads, index=index)
    assert leads[0].case_numbers == "470123"


def test_unrelated_owner_is_not_matched(tmp_path):
    index = build_index(tmp_path, [
        ("0011", "4614 ROBERTSON ST", "HOUSTON", "77009", "ROOPNARINE VIJAY S", 210_000),
    ])
    leads = [unknown_probate_lead("IN THE ESTATE OF: FRANK S. ALEXANDER, DECEASED")]

    stats = enrich_leads(leads, index=index)

    assert stats["addresses_recovered"] == 0
    assert leads[0].address == UNKNOWN_ADDRESS_LABEL
    assert leads[0].address_source == ADDRESS_SOURCE_UNKNOWN


def test_ambiguous_owner_with_many_parcels_stays_unknown(tmp_path):
    """A portfolio owner resolves to several equally-good parcels. Guessing
    one would put a specific wrong address in front of the investor.
    """
    parcels = [
        (f"00{i}", f"{100 + i} MAIN ST", "HOUSTON", "77002", "SANCHEZ MARIA ELENA", 90_000)
        for i in range(MAX_AMBIGUOUS_PARCELS + 2)
    ]
    index = build_index(tmp_path, parcels)
    leads = [unknown_probate_lead("IN THE ESTATE OF: MARIA ELENA SANCHEZ, DECEASED")]

    stats = enrich_leads(leads, index=index)

    assert stats["addresses_recovered"] == 0
    assert leads[0].address == UNKNOWN_ADDRESS_LABEL


def test_owner_with_two_tied_parcels_stays_unknown(tmp_path):
    index = build_index(tmp_path, [
        ("0011", "100 MAIN ST", "HOUSTON", "77002", "SANCHEZ MARIA ELENA", 90_000),
        ("0012", "200 MAIN ST", "HOUSTON", "77002", "SANCHEZ MARIA ELENA", 260_000),
    ])
    leads = [unknown_probate_lead("MARIA ELENA SANCHEZ, DECEASED")]
    enrich_leads(leads, index=index)
    assert leads[0].address == UNKNOWN_ADDRESS_LABEL


def test_nacogdoches_leads_are_left_alone(tmp_path):
    """The HCAD roll is Harris-only; matching another county against it
    would invent an address in the wrong county entirely.
    """
    index = build_index(tmp_path, [
        ("0011", "4614 ROBERTSON ST", "HOUSTON", "77009", "CARRENO PAUL VICENTE", 210_000),
    ])
    leads = [unknown_probate_lead("PAUL VICENTE CARRENO", county="Nacogdoches")]

    stats = enrich_leads(leads, index=index)

    assert stats["addresses_recovered"] == 0
    assert leads[0].address == UNKNOWN_ADDRESS_LABEL


def test_addressed_lead_gets_property_facts_backfilled(tmp_path):
    index = build_index(tmp_path, [
        ("0011", "4614 ROBERTSON ST", "HOUSTON", "77009", "HERNANDEZ OSCAR", 185_000),
    ])
    leads = [MatchedLead("4614 Robertson Street", "HERNANDEZ OSCAR", "Harris", 2,
                         ["absentee_owner", "tax_delinquent"])]

    stats = enrich_leads(leads, index=index)

    assert stats["facts_backfilled"] == 1
    assert leads[0].address == "4614 Robertson Street"  # filed address is not overwritten
    assert leads[0].address_source == ADDRESS_SOURCE_FILED
    assert leads[0].parcel_id == "0011"
    assert leads[0].market_value == 185_000


def test_missing_index_is_a_no_op(tmp_path):
    index = HcadOwnerIndex(tmp_path / "does_not_exist.db")
    leads = [unknown_probate_lead("PAUL VICENTE CARRENO")]

    stats = enrich_leads(leads, index=index)

    assert stats["index_available"] is False
    assert stats["unknown_after"] == 1
    assert leads[0].address == UNKNOWN_ADDRESS_LABEL


def test_enrichment_is_deterministic(tmp_path):
    parcels = [
        ("0011", "100 MAIN ST", "HOUSTON", "77002", "SANCHEZ MARIA ELENA", 90_000),
        ("0012", "200 MAIN ST", "HOUSTON", "77002", "SANCHEZ MARIA ELENA", 90_000),
    ]
    results = []
    for _ in range(3):
        index = build_index(tmp_path, parcels)
        leads = [unknown_probate_lead("MARIA ELENA SANCHEZ")]
        enrich_leads(leads, index=index)
        results.append(leads[0].address)
        index.close()
    assert len(set(results)) == 1
