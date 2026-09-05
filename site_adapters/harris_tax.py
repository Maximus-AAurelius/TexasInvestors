"""Harris County tax-delinquent accounts — Harris County Attorney's Office
delinquent-collection portal (NOT hcad.org, which doesn't publish this
data, and NOT hctax.net, whose robots.txt disallows /Property/TaxSales/
and /Tax/).

Source: https://caopay.harriscountytx.gov/  ("Search Delinquent Accounts")
robots.txt there only carries the newer AI-training "content-signals"
block, no classic Disallow — general automated access isn't blocked by
robots.txt.

NOT CURRENTLY WIRED INTO run.py — CONFIRMED reCAPTCHA-GATED.
Direct Playwright inspection on 2026-09-02 found a single search box
(id="txtProperty", name="SearchText") plus a hidden `recaptcha` token
input and a `g-recaptcha-response` textarea on the page. That's Google
reCAPTCHA. This project does not attempt to solve or bypass CAPTCHAs —
that's the site's explicit anti-bot mechanism, not an incidental
obstacle, and automating past it isn't something to script around.

Options if you need this data: look accounts up manually in a browser
and feed them in via `site_adapters/manual_import.py` + `run.py
--manual-csv`, or contact the Harris County Attorney's office about a
bulk/API data-sharing arrangement for delinquent accounts.

The scaffold below is left as-is (untested against the live captcha)
for reference only.
"""
from datetime import datetime
from typing import List

from models import LeadRecord, SOURCE_TAX_DELINQUENT
from site_adapters.base import BaseAdapter
from site_adapters._grid_helpers import scrape_grid

SEARCH_URL = "https://caopay.harriscountytx.gov/"

COLUMN_MAP = {
    "owner": "owner_name",
    "address": "address",
    "mailing": "mailing_address",
    "amount": "amount_owed",
    "year": "tax_year",
}


class HarrisTaxDelinquentAdapter(BaseAdapter):
    source_type = SOURCE_TAX_DELINQUENT
    county = "Harris"
    base_url = SEARCH_URL

    def fetch_raw(self, page) -> List[dict]:
        self._require_allowed(SEARCH_URL)
        page.goto(SEARCH_URL, wait_until="networkidle")
        self._jitter_sleep()

        # --- SEARCH SECTION: UNVERIFIED, replace via playwright codegen ---
        search_box = page.get_by_role("searchbox").first
        if search_box.count() == 0:
            search_box = page.get_by_role("textbox").first
        search_box.click()
        search_box.fill("")  # blank query: broadest result set, adjust if the
        # site requires a non-empty query (e.g. wildcard "%") once verified live
        page.get_by_role("button", name="Search").click()
        page.wait_for_load_state("networkidle")
        # --- END SEARCH SECTION ---

        self._jitter_sleep()
        return scrape_grid(page, COLUMN_MAP, table_selector="table")

    def to_record(self, row: dict) -> LeadRecord:
        amount_owed = None
        raw_amount = row.get("amount_owed", "")
        if raw_amount:
            cleaned = raw_amount.replace("$", "").replace(",", "").strip()
            try:
                amount_owed = float(cleaned)
            except ValueError:
                amount_owed = None

        return LeadRecord(
            address=row.get("address", ""),
            owner_name=row.get("owner_name", ""),
            source_type=self.source_type,
            county=self.county,
            date_recorded=datetime.now().date(),
            amount_owed=amount_owed,
            mailing_address=row.get("mailing_address") or None,
            source_url=SEARCH_URL,
        )
