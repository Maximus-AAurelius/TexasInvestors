from models import LeadRecord, SOURCE_TAX_DELINQUENT, SOURCE_PROBATE, SOURCE_TRUSTEE_SALE
from match import cluster_records, UNKNOWN_ADDRESS_LABEL


def test_same_property_different_sources_merges():
    records = [
        LeadRecord("123 Main Street", "John Smith", SOURCE_TAX_DELINQUENT, "Harris"),
        LeadRecord("123 Main St", "Smith, John", SOURCE_TRUSTEE_SALE, "Harris"),
    ]
    leads = cluster_records(records)
    assert len(leads) == 1
    assert leads[0].distress_score == 2
    assert set(leads[0].sources_hit) == {SOURCE_TAX_DELINQUENT, SOURCE_TRUSTEE_SALE}


def test_different_properties_do_not_merge():
    records = [
        LeadRecord("123 Main St", "John Smith", SOURCE_TAX_DELINQUENT, "Harris"),
        LeadRecord("999 Oak Ave", "Jane Doe", SOURCE_TAX_DELINQUENT, "Harris"),
    ]
    leads = cluster_records(records)
    assert len(leads) == 2


def test_same_house_number_different_street_does_not_merge():
    records = [
        LeadRecord("123 Main St", "John Smith", SOURCE_TAX_DELINQUENT, "Harris"),
        LeadRecord("123 Elm Ave", "Jane Doe", SOURCE_TAX_DELINQUENT, "Harris"),
    ]
    leads = cluster_records(records)
    assert len(leads) == 2


def test_probate_joins_by_owner_name():
    records = [
        LeadRecord("123 Main St", "John Smith", SOURCE_TAX_DELINQUENT, "Harris"),
        LeadRecord(address="", owner_name="Estate of John Smith",
                   source_type=SOURCE_PROBATE, county="Harris"),
    ]
    leads = cluster_records(records)
    assert len(leads) == 1
    assert leads[0].distress_score == 2
    assert leads[0].address == "123 Main St"


def test_probate_does_not_false_match_on_shared_common_word():
    # Regression test: found live 2026-09-02 that fuzz.WRatio scored
    # "IN THE ESTATE OF: MARGARET ELIZABETH DAVIS MEYERS, DECEASED" vs
    # "DAVIS FARRAR M" (unrelated people who only share the surname
    # "DAVIS") at 85.5 — above the threshold at the time — because
    # WRatio's token-set-style scoring gives credit for any shared word.
    # match.py now uses fuzz.ratio on the pre-sorted normalized strings
    # instead, which correctly treats this as dissimilar.
    records = [
        LeadRecord("12407 HONEYWOOD TRL", "DAVIS FARRAR M", SOURCE_TAX_DELINQUENT, "Harris"),
        LeadRecord(address="", owner_name="In the Estate of: Margaret Elizabeth Davis Meyers, Deceased",
                   source_type=SOURCE_PROBATE, county="Harris"),
    ]
    leads = cluster_records(records)
    assert len(leads) == 2
    unmatched = [l for l in leads if l.address == UNKNOWN_ADDRESS_LABEL]
    assert len(unmatched) == 1


def test_probate_with_no_owner_match_stays_unaddressed():
    records = [
        LeadRecord("123 Main St", "John Smith", SOURCE_TAX_DELINQUENT, "Harris"),
        LeadRecord(address="", owner_name="Estate of Someone Else",
                   source_type=SOURCE_PROBATE, county="Harris"),
    ]
    leads = cluster_records(records)
    assert len(leads) == 2
    unmatched = [l for l in leads if l.address == UNKNOWN_ADDRESS_LABEL]
    assert len(unmatched) == 1


def test_deterministic_across_runs():
    records = [
        LeadRecord("123 Main St", "John Smith", SOURCE_TAX_DELINQUENT, "Harris"),
        LeadRecord("123 Main Street", "Smith John", SOURCE_TRUSTEE_SALE, "Harris"),
        LeadRecord("999 Oak Ave", "Jane Doe", SOURCE_TAX_DELINQUENT, "Nacogdoches"),
    ]
    first = cluster_records(records)
    for _ in range(2):
        again = cluster_records(records)
        assert [(l.address, l.distress_score, tuple(l.sources_hit)) for l in first] == \
               [(l.address, l.distress_score, tuple(l.sources_hit)) for l in again]


def test_counties_do_not_cross_match():
    records = [
        LeadRecord("123 Main St", "John Smith", SOURCE_TAX_DELINQUENT, "Harris"),
        LeadRecord("123 Main St", "John Smith", SOURCE_TAX_DELINQUENT, "Nacogdoches"),
    ]
    leads = cluster_records(records)
    assert len(leads) == 2
