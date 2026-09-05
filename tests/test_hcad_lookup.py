import json

import hcad_lookup


def _write_roll(path, rows):
    import csv
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["acct", "site_addr_1", "state_class", "yr_impr", "bld_ar"], delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def test_finds_an_address_in_the_local_bulk_roll(tmp_path):
    roll = tmp_path / "real_acct.txt"
    _write_roll(roll, [{"acct": "1", "site_addr_1": "123 MAIN ST", "state_class": "A1", "yr_impr": "1990", "bld_ar": "2000"}])

    result = hcad_lookup.lookup_hcad("123 Main St", roll_path=roll)

    assert result["parcel_id"] == "1"
    assert result["building_sqft"] == 2000
    assert result["year_built"] == 1990
    assert result["lookup_method"] == "hcad_bulk_roll_scan"


def test_falls_back_to_live_lookup_when_not_in_local_roll(tmp_path, monkeypatch):
    roll = tmp_path / "real_acct.txt"
    _write_roll(roll, [{"acct": "1", "site_addr_1": "999 OTHER ST", "state_class": "A1", "yr_impr": "1990", "bld_ar": "2000"}])

    def fake_live(target):
        assert target == "123 MAIN ST"
        return {"parcel_id": "live-1", "lookup_method": "hcad_arcgis_live"}

    monkeypatch.setattr(hcad_lookup, "_lookup_live_arcgis", fake_live)
    result = hcad_lookup.lookup_hcad("123 Main St", roll_path=roll)

    assert result == {"parcel_id": "live-1", "lookup_method": "hcad_arcgis_live"}


def test_missing_roll_file_falls_back_to_live(tmp_path, monkeypatch):
    monkeypatch.setattr(hcad_lookup, "_lookup_live_arcgis", lambda target: {"lookup_method": "hcad_arcgis_live"})
    result = hcad_lookup.lookup_hcad("123 Main St", roll_path=tmp_path / "missing.txt")
    assert result["lookup_method"] == "hcad_arcgis_live"


def test_rejects_blank_address():
    try:
        hcad_lookup.lookup_hcad("   ")
        assert False, "expected HcadLookupError"
    except hcad_lookup.HcadLookupError:
        pass


def test_live_arcgis_parses_a_feature_response(monkeypatch):
    class _FakeResponse:
        def __init__(self, payload):
            self._body = json.dumps(payload).encode("utf-8")

        def read(self):
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    payload = {"features": [{"attributes": {
        "HCAD_NUM": "42", "owner": "OWNER NAME", "state_class": "A1",
        "land_val": 10000, "impr_val": 90000, "appr_val": 100000, "mkt_val": 100000,
        "subdivision": "SOME SUB",
    }}]}

    def fake_urlopen(request, timeout):
        return _FakeResponse(payload)

    monkeypatch.setattr(hcad_lookup.urllib.request, "urlopen", fake_urlopen)
    result = hcad_lookup._lookup_live_arcgis("123 MAIN ST")

    assert result["parcel_id"] == "42"
    assert result["owner_name"] == "OWNER NAME"
    assert result["hcad_market_value"] == 100000
    assert result["lookup_method"] == "hcad_arcgis_live"


def test_live_arcgis_returns_none_with_no_features(monkeypatch):
    class _FakeResponse:
        def read(self):
            return b'{"features": []}'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(hcad_lookup.urllib.request, "urlopen", lambda request, timeout: _FakeResponse())
    assert hcad_lookup._lookup_live_arcgis("123 MAIN ST") is None
