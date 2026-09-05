"""Single-address HCAD lookup — the per-property counterpart to the bulk
Real_acct_owner.zip roll that hcad_profile.py joins against the whole lead
list. Call lookup_hcad(address) for one address at a time.

Investigated 2026-09-05 whether a lightweight Playwright script could
submit one address to HCAD's own account-search form, following this
project's usual adapter pattern (site_adapters/base.py). Live inspection
found HCAD retired the old public.hcad.org search page — that host now
serves a static logo page only — and moved the search UI to
search.hcad.org, which sits behind a Cloudflare JS/Turnstile challenge
("Just a moment...") on every request, including a plain request for its
own robots.txt. That is the same category of explicit anti-bot mechanism
as caopay.harriscountytx.gov's reCAPTCHA (see site_adapters/harris_tax.py's
module docstring) — this project does not attempt to solve or bypass those
gates, here or anywhere else.

The practical, *lighter* replacement, found the same day: HCAD's own public
GIS map (arcweb.hcad.org, the "Parcel Viewer") calls a plain, unauthenticated
ArcGIS REST endpoint with no Cloudflare gate and no robots.txt restriction:
    https://arcweb.hcad.org/server/rest/services/public/public_query/MapServer/0
One HTTPS GET, JSON back, no browser to launch and no page layout to break
when HCAD next redesigns their site. Confirmed live against a real address
already in this app's lead set (10303 Greencreek Dr) — the parcel id
(HCAD_NUM) it returned matched the bulk-roll parcel id exactly.

lookup_hcad() tries two things, in order, for one address:
1. A single pass over the already-downloaded bulk roll
   (data/hcad/real_acct.txt — see scripts/fetch_hcad_bulk_data.py) if it's
   present. Fullest field set: building sqft, year improved, lot acreage,
   ownership-change date, neighborhood/market area.
2. If that file isn't present, or has no match (e.g. a very recent parcel
   split, or the file hasn't been re-downloaded lately), the live ArcGIS
   endpoint above. Fewer fields (owner, appraised/market/land/improvement
   value, state class) but always current and needs no download at all.

Both paths are Harris County only, matching the rest of this codebase's
HCAD coverage.
"""
import csv
import json
import urllib.error
import urllib.parse
import urllib.request

from hcad_profile import REAL_ACCT_PATH, _profile
from normalize import normalize_address

ARCGIS_QUERY_URL = "https://arcweb.hcad.org/server/rest/services/public/public_query/MapServer/0/query"
TIMEOUT_SECONDS = 15
USER_AGENT = "TXLeadResearchBot/1.0 (+contact: travispeters226@gmail.com; public-record lead research; respects robots.txt)"


class HcadLookupError(RuntimeError):
    """Raised only for a missing/blank address. A real but not-found address
    returns None instead of raising, same as a dict.get() miss."""


def _lookup_local_roll(target, roll_path):
    if not roll_path.exists():
        return None
    with roll_path.open(encoding="latin-1", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            if normalize_address(row.get("site_addr_1", "")) == target:
                profile = _profile(row)
                profile["lookup_method"] = "hcad_bulk_roll_scan"
                return profile
    return None


def _lookup_live_arcgis(target):
    where = "UPPER(address) = '{}'".format(target.replace("'", "''"))
    params = {"where": where, "outFields": "*", "f": "json", "returnGeometry": "false"}
    url = f"{ARCGIS_QUERY_URL}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    features = body.get("features") or []
    if not features:
        return None
    attrs = features[0].get("attributes", {})
    return {
        "parcel_id": attrs.get("HCAD_NUM"),
        "owner_name": attrs.get("owner"),
        "property_type": attrs.get("state_class"),
        "land_value": attrs.get("land_val"),
        "improvement_value": attrs.get("impr_val"),
        "assessed_value": attrs.get("appr_val"),
        "hcad_market_value": attrs.get("mkt_val"),
        "subdivision": attrs.get("subdivision"),
        "source": "HCAD public ArcGIS map service (live)",
        "lookup_method": "hcad_arcgis_live",
    }


def lookup_hcad(address, roll_path=None):
    """Look up one Harris County address.

    Returns a profile dict — the full hcad_profile._profile() field set
    when the bulk-roll scan finds it, a smaller live field set when only
    the ArcGIS fallback finds it (check the "lookup_method" key to tell
    which), or None if neither path found a match.

    Raises HcadLookupError only for a missing/blank address argument.
    """
    if not isinstance(address, str) or not address.strip():
        raise HcadLookupError("address is required")
    target = normalize_address(address)
    if not target:
        raise HcadLookupError("address did not normalize to anything searchable")
    local = _lookup_local_roll(target, roll_path or REAL_ACCT_PATH)
    if local:
        return local
    return _lookup_live_arcgis(target)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        raise SystemExit('Usage: python hcad_lookup.py "10303 Greencreek Dr"')
    try:
        result = lookup_hcad(" ".join(sys.argv[1:]))
    except HcadLookupError as exc:
        raise SystemExit(f"HCAD lookup failed: {exc}")
    print(json.dumps(result, indent=2) if result else "No HCAD match found for that address.")
