"""Harris County foreclosure (Notice of Trustee's Sale) postings —
County Clerk's dedicated Foreclosures search module.

Source: https://www.cclerk.hctx.net/Applications/WebSearch/FRCL_R.aspx
robots.txt on cclerk.hctx.net only disallows /Forms/ — this path is clear.

CONFIRMED LIVE 2026-09-02: this is a much better fit than RP.aspx (the
general real-property search) — it's pre-scoped to foreclosure postings
specifically, so there's no instrument-type code to guess (RP.aspx's
"Instrument Type" code for trustee sales was never found; this sidesteps
that whole problem). Real test: October 2026 sale date returned "553
Row(s) Found" — Doc ID / Sale Date / File Date / page count, e.g.
    FRCL-2026-4656   10/06/2026   06/29/2026   2
10/06/2026 is the first Tuesday of October, matching Tex. Prop. Code
§51.002's required foreclosure-sale day. That's a strong sign this is
the right data.

The search form is quirky: the Year dropdown doesn't populate the Month
dropdown with real options until AFTER a first Search click (which
returns a "Please provide a date or Doc ID" validation message as a
side effect — that's expected, not an error). The real search is the
second click, once Month has real options. See fetch_raw() below.

SCOPE LIMIT — this does NOT produce LeadRecords. The results index only
has Doc ID / Sale Date / File Date, no address or owner name — clicking
a Doc ID explicitly says "Select Document ID to View Image," i.e. the
actual notice is a scanned document image, not searchable text. Getting
address/owner out of that would need OCR (and the site's "LOG IN / NEW
USER" prompt suggests image viewing may require a paid account) — real
scope beyond a free pipeline. Rather than invent a fake address/owner
to force these into match.py's schema (which needs a real join key),
this adapter writes its own flat CSV of postings for manual review /
manual document lookup instead. Revisit if OCR becomes worth building.
"""
import csv
import time
from datetime import date
from pathlib import Path
from typing import List

from site_adapters.base import BaseAdapter

SEARCH_URL = "https://www.cclerk.hctx.net/Applications/WebSearch/FRCL_R.aspx"

YEAR_SELECTOR = "#ctl00_ContentPlaceHolder1_ddlYear"
MONTH_SELECTOR = "#ctl00_ContentPlaceHolder1_ddlMonth"
SEARCH_BTN_SELECTOR = "#ctl00_ContentPlaceHolder1_btnSearch"

MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July",
               "August", "September", "October", "November", "December"]

MAX_PAGES = 20  # 553 rows / ~38 per page ≈ 15 pages for a busy month; leaves headroom


class HarrisForeclosurePostingsAdapter(BaseAdapter):
    """Not a LeadRecord source — see module docstring. Call fetch_postings()
    directly rather than run(), and write results with save_postings_csv().
    """
    source_type = "trustee_sale_postings"  # not a models.py constant on purpose
    county = "Harris"
    base_url = SEARCH_URL

    def __init__(self, year: int, month: int, headless: bool = True):
        super().__init__(headless=headless)
        self.year = year
        self.month = month

    def fetch_postings(self) -> List[dict]:
        self._require_allowed(SEARCH_URL)
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = self._new_context(browser)
            page = context.new_page()
            try:
                rows = self._search(page)
            finally:
                context.close()
                browser.close()
        return rows

    def _search(self, page) -> List[dict]:
        page.goto(SEARCH_URL, wait_until="networkidle")
        self._jitter_sleep()

        page.select_option(YEAR_SELECTOR, str(self.year))
        time.sleep(1)
        page.click(SEARCH_BTN_SELECTOR)  # side effect: populates Month options
        page.wait_for_load_state("networkidle")
        self._jitter_sleep()

        page.select_option(MONTH_SELECTOR, label=MONTH_NAMES[self.month - 1])
        time.sleep(1)
        page.click(SEARCH_BTN_SELECTOR)
        page.wait_for_load_state("networkidle")
        self._jitter_sleep()

        # KNOWN LIMITATION: this results grid paginates via numbered links
        # (javascript:__doPostBack('...GridView1','Page$N')) — no "Next"
        # text link like the probate/RP.aspx grids. Confirmed live that
        # clicking these page-number links (via Playwright .click(), a
        # native el.click() via evaluate, and calling __doPostBack
        # directly) fires ZERO network requests — the page-2+ content
        # never changes. Root cause not identified (possibly the postback
        # function is scoped differently on this specific page). Net
        # effect: this only reliably returns page 1 of results (~38 rows)
        # even when the site reports many more ("553 Row(s) Found" for
        # October 2026). Real, correctly-parsed data — just incomplete.
        # Fixing this is a good next task; don't assume full-month
        # coverage from this adapter until it's resolved.
        all_rows = []
        seen_doc_ids = set()
        page_num = 1
        for _ in range(MAX_PAGES):
            page_rows = self._parse_results(page.inner_text("body"))
            new_rows = [r for r in page_rows if r["doc_id"] not in seen_doc_ids]
            if not new_rows:
                break  # see harris_probate.py for why this check exists
            all_rows.extend(new_rows)
            seen_doc_ids.update(r["doc_id"] for r in new_rows)

            page_num += 1
            next_page_link = page.get_by_role("link", name=str(page_num), exact=True)
            if next_page_link.count() == 0:
                break
            next_page_link.first.click()
            page.wait_for_load_state("networkidle")
            self._jitter_sleep()

        return all_rows

    @staticmethod
    def _parse_results(body_text: str) -> List[dict]:
        import re
        rows = []
        for m in re.finditer(
            r"(FRCL-\d{4}-\d+)\s+(\d{2}/\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})\s+(\d+)",
            body_text,
        ):
            doc_id, sale_date, file_date, pages = m.groups()
            rows.append({
                "doc_id": doc_id,
                "sale_date": sale_date,
                "file_date": file_date,
                "pages": pages,
            })
        return rows

    def fetch_raw(self, page):
        raise NotImplementedError("use fetch_postings() instead — see module docstring")

    def to_record(self, row):
        raise NotImplementedError("use fetch_postings() instead — see module docstring")


def save_postings_csv(postings: List[dict], out_path: str) -> str:
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["doc_id", "sale_date", "file_date", "pages"])
        writer.writeheader()
        writer.writerows(postings)
    return out_path
