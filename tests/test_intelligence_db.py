import intelligence_db


def test_profile_store_preserves_history(tmp_path, monkeypatch):
    monkeypatch.setattr(intelligence_db, "DB_PATH", tmp_path / "intelligence.db")
    lead = {
        "id": "Harris|123 MAIN ST", "address": "123 MAIN ST", "county": "Harris",
        "owner_name": "OWNER", "sources": ["absentee_owner"], "source_files": ["lead.csv"],
        "intelligence": {"model_version": "rules-v1", "scores": {"motivation": 8}},
    }

    intelligence_db.save_profiles([lead])
    intelligence_db.save_profiles([lead])
    counts = intelligence_db.history_counts()

    assert counts["properties"] == 1
    assert counts["property_profiles"] == 1
    assert counts["score_snapshots"] == 1


def test_underwriting_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(intelligence_db, "DB_PATH", tmp_path / "intelligence.db")
    underwriting = {"current_value": 250000, "arv_base": 350000, "assumptions": "Manual comp review"}

    intelligence_db.save_underwriting("property-1", underwriting)

    assert intelligence_db.get_underwritings()["property-1"] == underwriting


def test_property_lookup_upserts_one_row_per_address(tmp_path, monkeypatch):
    monkeypatch.setattr(intelligence_db, "DB_PATH", tmp_path / "intelligence.db")

    intelligence_db.save_property_lookup("123 Main St", "Harris", hcad_data={"parcel_id": "1"})
    intelligence_db.save_property_lookup("123 Main St", "Harris", rentcast_data={"price": 250000})

    saved = intelligence_db.get_property_lookup("123 Main St", "Harris")
    assert saved["hcad"] == {"parcel_id": "1"}
    assert saved["rentcast"] == {"price": 250000}
    assert len(intelligence_db.list_property_lookups()) == 1


def test_property_lookup_is_scoped_by_address_and_county(tmp_path, monkeypatch):
    monkeypatch.setattr(intelligence_db, "DB_PATH", tmp_path / "intelligence.db")

    intelligence_db.save_property_lookup("123 Main St", "Harris", hcad_data={"parcel_id": "1"})

    assert intelligence_db.get_property_lookup("123 Main Street", "Harris") is not None
    assert intelligence_db.get_property_lookup("123 Main St", "Nacogdoches") is None


def test_property_lookup_requires_address_and_county(tmp_path, monkeypatch):
    monkeypatch.setattr(intelligence_db, "DB_PATH", tmp_path / "intelligence.db")

    try:
        intelligence_db.save_property_lookup("", "Harris")
        assert False, "expected ValueError"
    except ValueError:
        pass