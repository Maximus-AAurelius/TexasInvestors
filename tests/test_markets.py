import pytest
from markets import COUNTIES, normalize_county, market_catalog
from models import LeadRecord
from site_adapters.manual_import import load_manual_csv
from buyers import validate_buyer, match_buyers


@pytest.mark.parametrize("county", COUNTIES)
def test_target_counties_import_and_match_only_same_county(tmp_path, county):
    path = tmp_path / "leads.csv"
    path.write_text(f"address,owner_name,source_type,county\n123 Main,Test Owner,absentee_owner,{county.lower()} County\n")
    record = load_manual_csv(path)[0]
    assert record.county == county
    buyer = validate_buyer({"name": "Test buyer", "county": county.lower()})
    assert match_buyers({"county": county}, [buyer])
    different = next(name for name in COUNTIES if name != county)
    assert not match_buyers({"county": different}, [buyer])


def test_scope_and_coverage_are_explicit():
    assert len(COUNTIES) == 9
    assert normalize_county("Nacogadoches County") == "Nacogdoches"
    assert market_catalog()[0]["priority"] == "Primary"
    assert all("no connected" in row["coverage"] for row in market_catalog()[1:])
    with pytest.raises(ValueError):
        LeadRecord("123 Main", "Test Owner", "absentee_owner", "Dallas")
