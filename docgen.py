"""Generates an editable .docx lead report from matched leads.

Column widths are fixed DXA values that sum to exactly 9360 DXA
(6.5in), which is the usable width on a US Letter page with 1in
margins on each side (8.5in - 2*1in = 6.5in = 9360 DXA, since
1in = 1440 DXA). Word will not shrink/overflow the table as long as
this sum holds and autofit is disabled.
"""
from datetime import datetime
from typing import List

from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

from match import MatchedLead

# DXA widths — must sum to 9360
COL_WIDTHS_DXA = {
    "Address": 3600,
    "Owner": 2600,
    "Distress Score": 1100,
    "Sources Hit": 2060,
}
assert sum(COL_WIDTHS_DXA.values()) == 9360, "column widths must sum to 9360 DXA"

SOURCE_LABELS = {
    "tax_delinquent": "Tax Delinquent",
    "probate": "Probate",
    "trustee_sale": "Trustee Sale",
    "absentee_owner": "Absentee Owner",
}


def _set_cell_width(cell, dxa: int):
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_w = OxmlElement("w:tcW")
    tc_w.set(qn("w:w"), str(dxa))
    tc_w.set(qn("w:type"), "dxa")
    tc_pr.append(tc_w)


def _disable_autofit(table):
    tbl_pr = table._tbl.tblPr
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tbl_pr.append(layout)


def build_document(leads: List[MatchedLead], generated_at: datetime = None) -> Document:
    generated_at = generated_at or datetime.now()

    doc = Document()
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)

    title = doc.add_heading("Texas Distress-Lead Report", level=1)
    title.alignment = WD_ALIGN_PARAGRAPH.LEFT

    meta = doc.add_paragraph()
    meta.add_run(
        f"Generated {generated_at.strftime('%Y-%m-%d %H:%M')} — "
        f"Harris & Nacogdoches County, TX — {len(leads)} matched properties"
    ).italic = True

    columns = ["Address", "Owner", "Distress Score", "Sources Hit"]
    table = doc.add_table(rows=1, cols=len(columns))
    table.style = "Light Grid Accent 1"
    table.autofit = False
    _disable_autofit(table)

    for i, col in enumerate(table.columns):
        col.width = Inches(COL_WIDTHS_DXA[columns[i]] / 1440)

    header_cells = table.rows[0].cells
    for i, name in enumerate(columns):
        header_cells[i].text = name
        for p in header_cells[i].paragraphs:
            for r in p.runs:
                r.bold = True
        _set_cell_width(header_cells[i], COL_WIDTHS_DXA[name])

    for lead in leads:
        row = table.add_row().cells
        sources_str = ", ".join(SOURCE_LABELS.get(s, s) for s in lead.sources_hit)
        values = [lead.address, lead.owner_name, str(lead.distress_score), sources_str]
        for i, val in enumerate(values):
            row[i].text = val
            _set_cell_width(row[i], COL_WIDTHS_DXA[columns[i]])

    return doc


def write_docx(leads: List[MatchedLead], out_path: str, generated_at: datetime = None) -> str:
    doc = build_document(leads, generated_at)
    doc.save(out_path)
    return out_path
