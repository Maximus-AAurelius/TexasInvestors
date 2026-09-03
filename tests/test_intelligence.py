from intelligence import ScoringConfig, build_profile


def lead(mailing_address="9019 PHEASANT TRACE CT HOUSTON TX 77064"):
    return {
        "id": "Harris|123 MAIN ST", "address": "123 MAIN ST", "county": "Harris",
        "owner_name": "OWNER", "mailing_address": mailing_address,
        "sources": ["absentee_owner"], "source_files": ["output/leads.csv"],
    }


def test_profile_keeps_unsupported_economics_unknown():
    profile = build_profile(lead())

    assert profile.scores["motivation"] == 8
    assert profile.scores["opportunity"] is None
    assert "Independent current market value" in profile.data_gaps
    assert profile.recommendation == "RESEARCH FIRST"


def test_configurable_signal_weight_changes_score():
    config = ScoringConfig(signal_weights={"absentee_owner": 42})

    assert build_profile(lead(), config).scores["motivation"] == 42


def test_out_of_state_mailing_adds_only_supported_signal():
    profile = build_profile(lead("PO BOX 1788 OXFORD NC 27565"))

    assert profile.scores["motivation"] == 16
    assert [signal["type"] for signal in profile.signals] == ["absentee_owner", "out_of_state_mailing"]


def test_hcad_facts_add_verified_property_context():
    record = {"parcel_id": "123", "building_sqft": 1500, "hcad_market_value": 250000, "ownership_duration_years": 18}
    profile = build_profile({**lead(), "hcad": record})

    assert profile.property_facts["parcel_id"] == "123"
    assert profile.scores["data_confidence"] == 65
    assert any(signal["type"] == "long_ownership" for signal in profile.signals)