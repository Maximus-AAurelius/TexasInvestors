"""Shared helpers for scraping the ASP.NET results grids used by the
cclerk.hctx.net search apps.

These render as a Telerik-style grid: clean, consistent tab-separated
text via `page.inner_text("body")`, but a tangled DOM underneath —
confirmed live 2026-09-02 that the real data table is interleaved with
many tiny single-column "header fragment" sub-tables, which fooled a
naive <table>-walking scraper into picking the wrong rows. Prefer
parse_grid_text() (works directly off the rendered text) over
scrape_grid() (DOM-table based, kept for sites that render a normal
<table>) for anything on cclerk.hctx.net.
"""
import re
from typing import Dict, List, Optional


def parse_grid_text(body_text: str, field_count: int, date_field_index: int) -> List[List[str]]:
    """Split the page's rendered body text into row-blocks (separated by
    blank lines) and tab-split each into a fixed-width field list. Only
    keeps blocks that have a MM/DD/YYYY-looking date in the expected
    position, which filters out non-data text (nav links, disclaimers,
    the "N Record(s) Found" banner, etc.) without needing DOM access.
    """
    blocks = re.split(r"\n\s*\n", body_text)
    rows = []
    for block in blocks:
        fields = block.strip("\t\n ").split("\t")
        if len(fields) < field_count:
            continue
        fields = fields[:field_count]
        if date_field_index < len(fields) and re.match(r"^\d{2}/\d{2}/\d{4}$", fields[date_field_index]):
            rows.append(fields)
    return rows


def _find_results_table(page, column_map: Dict[str, str]):
    tables = page.query_selector_all("table")
    best_table, best_score, best_row_count = None, 0, 0
    for table in tables:
        header_cells = table.query_selector_all("tr:first-child th, tr:first-child td")
        headers = [h.inner_text().strip().lower() for h in header_cells]
        if not headers:
            continue
        score = sum(1 for substr in column_map if any(substr.lower() in h for h in headers))
        row_count = len(table.query_selector_all("tr")) - 1
        if score > best_score or (score == best_score and row_count > best_row_count):
            best_table, best_score, best_row_count = table, score, row_count
    return best_table


_RP_FILE_NO = re.compile(r"(RP-\d{4}-\d+)")
_RP_DATE_TYPE = re.compile(r"(\d{2}/\d{2}/\d{4})\s*\n?\s*([A-Z][A-Z/&\- ]{0,10}?)\s*\n")


def parse_rp_records(body_text: str) -> List[dict]:
    """Parse cclerk.hctx.net/.../RP.aspx results text. This grid renders
    each record as a labeled multi-line block (Grantor:/Grantee:/Trustee:/
    Desc:/Lot:/Block:) rather than a flat tab-delimited row, and repeats
    the File Number both at the start of a record and again at its end
    (apparently reused as the "Film Code" column) — so splitting on every
    File Number occurrence yields real-content chunks interleaved with
    tiny throwaway ones; only chunks containing a Grantor:/Grantee: line
    are kept.
    """
    parts = _RP_FILE_NO.split(body_text)
    records = []
    for i in range(1, len(parts) - 1, 2):
        file_no, chunk = parts[i], parts[i + 1]
        if "Grantor:" not in chunk and "Grantee:" not in chunk:
            continue
        date_type = _RP_DATE_TYPE.search(chunk)
        if not date_type:
            continue
        file_date, doc_type = date_type.group(1), date_type.group(2).strip()

        grantors = re.findall(r"Grantor:\s*([^\n\t]+)", chunk)
        grantees = re.findall(r"Grantee:\s*([^\n\t]+)", chunk)
        trustees = re.findall(r"Trustee:\s*([^\n\t]+)", chunk)
        desc = re.search(r"Desc:\s*([^\n\t]+)", chunk)
        lot = re.search(r"Lot:\s*([^\n\t]+)", chunk)
        block = re.search(r"Block:\s*([^\n\t]+)", chunk)

        legal = " ".join(filter(None, [
            desc.group(1).strip() if desc else None,
            f"LOT {lot.group(1).strip()}" if lot else None,
            f"BLOCK {block.group(1).strip()}" if block else None,
        ]))
        names = "; ".join(g.strip() for g in (grantors + trustees or grantees))

        records.append({
            "case_no": file_no,
            "date_recorded": file_date,
            "doc_type": doc_type,
            "owner_name": names,
            "address": legal,
            "has_trustee": bool(trustees),
        })
    return records


def scrape_grid(page, column_map: Dict[str, str], table_selector: Optional[str] = None) -> List[dict]:
    """Extract rows from the results table into dicts keyed by the
    logical field names in column_map's values.

    column_map: {substring-of-header-text (case-insensitive): logical_field_name}
    table_selector: skip auto-detection and use this CSS selector instead.
    """
    table = page.query_selector(table_selector) if table_selector else _find_results_table(page, column_map)
    if table is None:
        return []

    header_cells = table.query_selector_all("tr:first-child th, tr:first-child td")
    headers = [h.inner_text().strip() for h in header_cells]

    field_by_col_index = {}
    for idx, header_text in enumerate(headers):
        for substr, field in column_map.items():
            if substr.lower() in header_text.lower():
                field_by_col_index[idx] = field
                break

    rows = table.query_selector_all("tr")[1:]
    results = []
    for row in rows:
        cells = row.query_selector_all("td")
        if not cells or len(cells) < 2:
            continue
        record = {}
        for idx, cell in enumerate(cells):
            field = field_by_col_index.get(idx)
            if field:
                record[field] = cell.inner_text().strip()
        if any(record.values()):
            results.append(record)
    return results
