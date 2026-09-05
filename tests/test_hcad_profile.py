import csv
import hcad_profile


def test_cache_tracks_lead_set_and_never_crosses_counties(tmp_path, monkeypatch):
    source = tmp_path / "real_acct.txt"
    with source.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["acct", "site_addr_1"], delimiter="\t")
        writer.writeheader()
        writer.writerows([{"acct": "1", "site_addr_1": "123 MAIN ST"}, {"acct": "2", "site_addr_1": "456 MAIN ST"}])
    monkeypatch.setattr(hcad_profile, "REAL_ACCT_PATH", source)
    monkeypatch.setattr(hcad_profile, "CACHE_PATH", tmp_path / "cache.json")
    lead = {"id": "h1", "address": "123 MAIN ST", "county": "Harris"}
    assert hcad_profile.enrich_leads([lead])["h1"]["parcel_id"] == "1"
    other = {"id": "h2", "address": "456 MAIN ST", "county": "Harris"}
    assert "h2" in hcad_profile.enrich_leads([lead, other])
    assert hcad_profile.enrich_leads([{**lead, "county": "Nacogdoches"}]) == {}


def test_ambiguous_address_does_not_pick_first_parcel(tmp_path, monkeypatch):
    source = tmp_path / "real_acct.txt"
    source.write_text("acct\tsite_addr_1\n1\t123 MAIN ST\n2\t123 MAIN ST\n")
    monkeypatch.setattr(hcad_profile, "REAL_ACCT_PATH", source)
    monkeypatch.setattr(hcad_profile, "CACHE_PATH", tmp_path / "cache.json")
    assert hcad_profile.enrich_leads([{"id": "1", "address": "123 MAIN ST", "county": "Harris"}]) == {}
