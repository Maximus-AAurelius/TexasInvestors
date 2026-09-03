"""Shared plumbing for every site adapter: identifiable UA, robots.txt
enforcement, and jittered rate limiting. Each concrete adapter only
needs to implement fetch_raw() and parse() against its own site.
"""
import random
import time
import urllib.robotparser
from abc import ABC, abstractmethod
from typing import List
from urllib.parse import urljoin, urlparse

from playwright.sync_api import sync_playwright

from models import LeadRecord

# Identifiable on purpose — county IT staff should be able to see what
# this is and email someone, not get suspicious of a spoofed browser UA.
USER_AGENT = (
    "TXLeadResearchBot/1.0 (+contact: travispeters226@gmail.com; "
    "public-record lead research; respects robots.txt)"
)

MIN_DELAY_SEC = 2.0
MAX_DELAY_SEC = 5.0


class RobotsDisallowedError(RuntimeError):
    pass


class BaseAdapter(ABC):
    source_type: str
    county: str
    base_url: str

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._robots_cache = {}

    def _robots_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        rp = self._robots_cache.get(origin)
        if rp is None:
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(urljoin(origin, "/robots.txt"))
            try:
                rp.read()
            except Exception:
                # If robots.txt can't be fetched, fail closed — do not scrape.
                self._robots_cache[origin] = False
                return False
            self._robots_cache[origin] = rp
        if rp is False:
            return False
        return rp.can_fetch(USER_AGENT, url)

    def _require_allowed(self, url: str):
        if not self._robots_allowed(url):
            raise RobotsDisallowedError(
                f"robots.txt disallows fetching {url} for this user-agent"
            )

    def _jitter_sleep(self):
        time.sleep(random.uniform(MIN_DELAY_SEC, MAX_DELAY_SEC))

    def _new_context(self, browser):
        return browser.new_context(user_agent=USER_AGENT)

    def run(self) -> List[LeadRecord]:
        """Entry point: launches Playwright, delegates to fetch_raw(),
        returns normalized LeadRecord objects via parse()."""
        self._require_allowed(self.base_url)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = self._new_context(browser)
            page = context.new_page()
            try:
                raw_rows = self.fetch_raw(page)
            finally:
                context.close()
                browser.close()

        records = []
        for row in raw_rows:
            try:
                records.append(self.to_record(row))
            except ValueError as exc:
                print(f"[{self.__class__.__name__}] skipping malformed row {row!r}: {exc}")
        return records

    @abstractmethod
    def fetch_raw(self, page) -> List[dict]:
        """Navigate the site and return a list of raw field dicts, one
        per result row. Must call self._jitter_sleep() between each
        page/search request and self._require_allowed(url) before any
        navigation beyond base_url."""
        raise NotImplementedError

    @abstractmethod
    def to_record(self, row: dict) -> LeadRecord:
        """Map one raw row dict to the common LeadRecord schema."""
        raise NotImplementedError
