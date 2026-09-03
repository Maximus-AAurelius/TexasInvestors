"""Harris County probate case filings — County Clerk case search.

CONFIRMED LIVE 2026-09-02 via direct Playwright inspection (not just a
text fetch): filling the date-range fields and clicking Search returns
real results — e.g. a search for 01/01/2026-09/02/2026 returned "6780
Record(s) Found" with rows like:
  Case=541039 Court=4 FileDate=01/12/2026 Status=Closed
  Type Desc=PROBATE OF WILL (INDEPENDENT ADMINISTRATION)
  Style="IN THE ESTATE OF: BILLIE SUE SMITH, DECEASED"
No login/CAPTCHA encountered. Results paginate (~50-ish/page based on
"6780 Record(s) Found" with Previous/1/2/3/4/5/.../Next controls).
"""
from datetime import datetime, timedelta
from typing import List

from models import LeadRecord, SOURCE_PROBATE
from site_adapters.base import BaseAdapter
from site_adapters._grid_helpers import parse_grid_text

SEARCH_URL = (
    "https://www.cclerk.hctx.net/applications/websearch/"
    "CourtSearch.aspx?CaseType=Probate"
)

DATE_FROM_SELECTOR = "#ctl00_ContentPlaceHolder1_txtFrom"
DATE_TO_SELECTOR = "#ctl00_ContentPlaceHolder1_txtTo"
SEARCH_BTN_SELECTOR = "#ctl00_ContentPlaceHolder1_btnSearchCase"
NEXT_LINK_TEXT = "Next"

# Confirmed live 2026-09-02: each result row renders as this fixed
# tab-separated field layout (blank lines between rows):
#   [case_no, court, file_date, status, type_desc, subtype, style]
# e.g. ["547159", "3", "08/31/2026", "Open",
#       "PROBATE OF WILL (INDEPENDENT ADMINISTRATION)", "",
#       "IN THE ESTATE OF: NANCY BERNICE ZACK BELL, DECEASED"]
FIELD_COUNT = 7
DATE_FIELD_INDEX = 2
CASE_NO_INDEX = 0
STYLE_INDEX = 6

MAX_PAGES = 10  # safety cap; each page is a real request against a live county server


class HarrisProbateAdapter(BaseAdapter):
    source_type = SOURCE_PROBATE
    county = "Harris"
    base_url = SEARCH_URL

    def __init__(self, lookback_days: int = 30, headless: bool = True):
        super().__init__(headless=headless)
        self.lookback_days = lookback_days

    def fetch_raw(self, page) -> List[dict]:
        self._require_allowed(SEARCH_URL)
        page.goto(SEARCH_URL, wait_until="domcontentloaded")
        self._jitter_sleep()

        date_to = datetime.now()
        date_from = date_to - timedelta(days=self.lookback_days)

        page.fill(DATE_FROM_SELECTOR, date_from.strftime("%m/%d/%Y"))
        page.fill(DATE_TO_SELECTOR, date_to.strftime("%m/%d/%Y"))
        self._jitter_sleep()

        page.click(SEARCH_BTN_SELECTOR)
        page.wait_for_load_state("networkidle")
        self._jitter_sleep()

        all_rows = []
        seen_case_nos = set()
        for _ in range(MAX_PAGES):
            body_text = page.inner_text("body")
            page_rows = parse_grid_text(body_text, FIELD_COUNT, DATE_FIELD_INDEX)
            new_rows = [r for r in page_rows if r[CASE_NO_INDEX] not in seen_case_nos]
            if not new_rows:
                # Confirmed live 2026-09-02: clicking "Next" doesn't always
                # advance the grid (this page has two identically-labeled
                # "Next" pager controls, DataPagerLisViewCases1/2, and only
                # one may be bound to the visible results — or there's
                # genuinely only one page). Re-scraping the same rows once
                # is cheap; looping MAX_PAGES times on unchanged content
                # silently produced 10x duplicate records before this check
                # existed, so stop the moment a "next page" isn't new.
                break
            all_rows.extend(new_rows)
            seen_case_nos.update(r[CASE_NO_INDEX] for r in new_rows)

            next_link = page.get_by_role("link", name=NEXT_LINK_TEXT)
            if next_link.count() == 0:
                break
            next_link.first.click()
            page.wait_for_load_state("networkidle")
            self._jitter_sleep()

        return all_rows

    def to_record(self, row: list) -> LeadRecord:
        date_recorded = None
        try:
            date_recorded = datetime.strptime(row[DATE_FIELD_INDEX], "%m/%d/%Y").date()
        except ValueError:
            pass

        return LeadRecord(
            address="",  # probate filings identify an owner, not a property;
            # match.py joins these onto a property by owner-name fuzzy match.
            owner_name=row[STYLE_INDEX],
            source_type=self.source_type,
            county=self.county,
            date_recorded=date_recorded,
            case_no=row[CASE_NO_INDEX],
            source_url=SEARCH_URL,
        )
