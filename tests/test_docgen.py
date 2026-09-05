import os

from docgen import write_csv, write_docx, COL_WIDTHS_DXA, USABLE_WIDTH_DXA
from match import MatchedLead


def test_column_widths_sum_to_usable_page_width():
    assert sum(COL_WIDTHS_DXA.values()) == USABLE_WIDTH_DXA


def test_writes_valid_docx(tmp_path):
    leads = [
        MatchedLead("123 Main St", "John Smith", "Harris", 3,
                    ["tax_delinquent", "probate", "trustee_sale"]),
        MatchedLead("999 Oak Ave", "Jane Doe", "Nacogdoches", 1, ["tax_delinquent"]),
    ]
    out = tmp_path / "test.docx"
    write_docx(leads, str(out))
    assert out.exists()
    assert out.stat().st_size > 0
