"""Deterministic extraction of saved public-record tables using Scrapling.

This component performs no network requests and never runs page scripts.
Adaptive relocation is disabled: schema drift must be reviewed explicitly.
"""
from scrapling.parser import Selector


def extract_table(html, column_map, table_selector="table"):
    if not isinstance(html, str) or len(html.encode("utf-8")) > 5_000_000:
        raise ValueError("HTML must be text smaller than 5 MB")
    page = Selector(content=html, adaptive=False)
    candidates = []
    for table in page.css(table_selector):
        rows = table.xpath("./tr | ./thead/tr | ./tbody/tr")
        if not rows:
            continue
        headers = [" ".join(cell.xpath(".//text()").getall()).strip().lower()
                   for cell in rows[0].xpath("./th | ./td")]
        mapping = {i: column_map[header] for i, header in enumerate(headers) if header in column_map}
        if not mapping:
            continue
        records = []
        for row in rows[1:]:
            cells = row.xpath("./td")
            if len(cells) != len(headers):
                continue
            record = {field: " ".join(cells[i].xpath(".//text()").getall()).strip()
                      for i, field in mapping.items()}
            if any(record.values()):
                records.append(record)
        candidates.append((len(mapping), records))
    if not candidates:
        raise ValueError("No table matches the configured headers; review the source layout")
    candidates.sort(key=lambda pair: pair[0], reverse=True)
    if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
        raise ValueError("Multiple matching tables; provide a specific CSS table selector")
    if not candidates[0][1]:
        raise ValueError("Matching table contains no usable records")
    return candidates[0][1]
