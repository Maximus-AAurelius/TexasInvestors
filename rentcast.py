"""RentCast API connector — one function, one address in, RentCast's own
JSON back out. No scraping and no browser here at all, just a plain HTTPS
GET to a documented API endpoint. Reuse get_comps() for every property you
evaluate instead of writing a new call each time.

Get a free API key at https://app.rentcast.io/app/api and set it as an
environment variable rather than pasting it into code (never commit a key):

    PowerShell (this session only):
        $env:RENTCAST_API_KEY = "your-key-here"
    PowerShell (persists across sessions):
        setx RENTCAST_API_KEY "your-key-here"

See RentCast's Value Estimate docs for the full field reference:
https://developers.rentcast.io/reference/value-estimate
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

API_URL = "https://api.rentcast.io/v1/avm/value"
TIMEOUT_SECONDS = 20
VALID_PROPERTY_TYPES = {
    "Single Family", "Condo", "Townhouse", "Manufactured", "Multi-Family", "Apartment", "Land",
}


class RentCastError(RuntimeError):
    """Raised for a missing/bad API key, invalid input, or an API/network failure."""


def get_comps(address, api_key=None, comp_count=15, max_radius=None, days_old=None, property_type=None):
    """Look up one property's estimated value and comparable sales/listings
    from RentCast's AVM (automated valuation model) endpoint.

    address: full street address, e.g. "1234 Main St, Houston, TX 77002".
        RentCast geocodes this itself; a ZIP/state helps accuracy but isn't
        required.
    api_key: RentCast API key. Defaults to the RENTCAST_API_KEY environment
        variable when not passed explicitly.
    comp_count: how many comparables RentCast should return (5-25).
    max_radius: optional search radius in miles.
    days_old: optional cap on how old a comparable listing may be, in days.
    property_type: optional RentCast property type filter — one of
        VALID_PROPERTY_TYPES above.

    Returns the parsed JSON response unchanged: top-level "price",
    "priceRangeLow", "priceRangeHigh", "subjectProperty", and a
    "comparables" list (each with formattedAddress, price, correlation,
    distance, daysOld, etc). This is an automated estimate, not an
    appraisal — treat it as a starting point, not a verified value.

    Raises RentCastError for a missing/blank address, a missing API key,
    an invalid parameter, or any HTTP/network failure (including RentCast
    finding no record for the address, a bad key, or a rate limit).
    """
    if not isinstance(address, str) or not address.strip():
        raise RentCastError("address is required")
    key = api_key or os.environ.get("RENTCAST_API_KEY")
    if not key:
        raise RentCastError(
            "No RentCast API key found. Set the RENTCAST_API_KEY environment "
            "variable or pass api_key= explicitly."
        )
    if not isinstance(comp_count, int) or not 5 <= comp_count <= 25:
        raise RentCastError("comp_count must be an integer between 5 and 25")
    if property_type is not None and property_type not in VALID_PROPERTY_TYPES:
        raise RentCastError(f"property_type must be one of {sorted(VALID_PROPERTY_TYPES)}")

    params = {"address": address.strip(), "compCount": comp_count}
    if max_radius is not None:
        params["maxRadius"] = max_radius
    if days_old is not None:
        params["daysOld"] = days_old
    if property_type is not None:
        params["propertyType"] = property_type

    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"X-Api-Key": key, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        if exc.code == 401:
            raise RentCastError("RentCast rejected the API key (401 Unauthorized)") from exc
        if exc.code == 404:
            raise RentCastError(f"RentCast found no property record for: {address}") from exc
        if exc.code == 429:
            raise RentCastError("RentCast rate limit or monthly quota reached (429)") from exc
        raise RentCastError(f"RentCast API error {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RentCastError(f"Could not reach RentCast API: {exc.reason}") from exc
    except TimeoutError as exc:
        raise RentCastError("RentCast API request timed out") from exc

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise RentCastError("RentCast returned a response that was not valid JSON") from exc


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        raise SystemExit('Usage: python rentcast.py "1234 Main St, Houston, TX 77002"')
    try:
        result = get_comps(" ".join(sys.argv[1:]))
    except RentCastError as exc:
        raise SystemExit(f"RentCast lookup failed: {exc}")
    print(json.dumps(result, indent=2))
