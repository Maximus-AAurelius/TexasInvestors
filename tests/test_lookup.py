import intelligence_db
import lookup
from hcad_lookup import HcadLookupError
from rentcast import RentCastError


def test_run_lookup_saves_both_results_and_returns_them(tmp_path, monkeypatch):
    monkeypatch.setattr(intelligence_db, "DB_PATH", tmp_path / "intelligence.db")
    monkeypatch.setattr(lookup, "lookup_hcad", lambda address: {"parcel_id": "1"})
    monkeypatch.setattr(lookup, "get_comps", lambda address, api_key=None: {"price": 250000})

    result = lookup.run_lookup("123 Main St", county="Harris")

    assert result["hcad"] == {"parcel_id": "1"}
    assert result["rentcast"] == {"price": 250000}
    assert result["errors"] == []
    assert intelligence_db.get_property_lookup("123 Main St", "Harris")["hcad"] == {"parcel_id": "1"}


def test_run_lookup_saves_hcad_even_when_rentcast_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(intelligence_db, "DB_PATH", tmp_path / "intelligence.db")
    monkeypatch.setattr(lookup, "lookup_hcad", lambda address: {"parcel_id": "1"})

    def failing_rentcast(address, api_key=None):
        raise RentCastError("no key")

    monkeypatch.setattr(lookup, "get_comps", failing_rentcast)

    result = lookup.run_lookup("123 Main St", county="Harris")

    assert result["hcad"] == {"parcel_id": "1"}
    assert result["rentcast"] is None
    assert any("RentCast" in message for message in result["errors"])


def test_run_lookup_reports_hcad_not_found_without_raising(tmp_path, monkeypatch):
    monkeypatch.setattr(intelligence_db, "DB_PATH", tmp_path / "intelligence.db")
    monkeypatch.setattr(lookup, "lookup_hcad", lambda address: None)
    monkeypatch.setattr(lookup, "get_comps", lambda address, api_key=None: {"price": 1})

    result = lookup.run_lookup("123 Main St", county="Harris", skip_hcad=False)

    assert result["hcad"] is None
    assert any("HCAD" in message for message in result["errors"])


def test_run_lookup_can_skip_either_connector(tmp_path, monkeypatch):
    monkeypatch.setattr(intelligence_db, "DB_PATH", tmp_path / "intelligence.db")
    calls = []
    monkeypatch.setattr(lookup, "lookup_hcad", lambda address: calls.append("hcad") or {"parcel_id": "1"})
    monkeypatch.setattr(lookup, "get_comps", lambda address, api_key=None: calls.append("rentcast") or {"price": 1})

    lookup.run_lookup("123 Main St", county="Harris", skip_rentcast=True)

    assert calls == ["hcad"]


def test_run_lookup_requires_an_address():
    try:
        lookup.run_lookup("   ")
        assert False, "expected ValueError"
    except ValueError:
        pass
