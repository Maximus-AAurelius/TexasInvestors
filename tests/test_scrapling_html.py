import pytest

pytest.importorskip("scrapling")
from site_adapters.scrapling_html import extract_table


def test_extracts_nested_text_and_ignores_unrelated_tables():
    html = '<table><tr><th>Menu</th></tr><tr><td>Home</td></tr></table><table id="records"><tr><th>Address</th><th>Owner</th></tr><tr><td>123 <b>Main</b> St</td><td>A &amp; B</td></tr></table>'
    assert extract_table(html, {"address": "address", "owner": "owner_name"}) == [{"address": "123  Main  St", "owner_name": "A & B"}]


def test_schema_drift_and_ambiguous_tables_fail_closed():
    table = '<table><tr><th>Address</th></tr><tr><td>123 Main</td></tr></table>'
    with pytest.raises(ValueError, match="Multiple"):
        extract_table(table * 2, {"address": "address"})
    with pytest.raises(ValueError, match="No table"):
        extract_table(table, {"owner": "owner_name"})
