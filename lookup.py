"""One address in, a saved database row out. This is the glue between the
two connectors (rentcast.py, hcad_lookup.py) and the local database
(intelligence_db.py's property_lookups table): call run_lookup() for every
property you're evaluating, and each call inserts/updates that one row —
subject property plus RentCast comps plus HCAD facts — building the
working deal database incrementally instead of needing a big upfront
import.

Command line:
    .venv\\Scripts\\python.exe lookup.py "10303 Greencreek Dr, Houston, TX 77070"
    .venv\\Scripts\\python.exe lookup.py "10303 Greencreek Dr" --county Harris --no-rentcast
"""
import json

from hcad_lookup import HcadLookupError, lookup_hcad
from intelligence_db import get_property_lookup, save_property_lookup
from rentcast import RentCastError, get_comps


def run_lookup(address, county="Harris", rentcast_api_key=None, skip_rentcast=False, skip_hcad=False):
    """Look up one address, save whatever comes back, and return the
    combined record (same shape as intelligence_db.get_property_lookup,
    plus an "errors" list for any connector that failed this run — a
    RentCast failure doesn't block saving the HCAD half, and vice versa).
    """
    if not isinstance(address, str) or not address.strip():
        raise ValueError("address is required")

    errors = []
    hcad_data = None
    if not skip_hcad:
        try:
            hcad_data = lookup_hcad(address)
            if hcad_data is None:
                errors.append("HCAD: no match found for this address (Harris County only)")
        except HcadLookupError as exc:
            errors.append(f"HCAD: {exc}")

    rentcast_data = None
    if not skip_rentcast:
        try:
            rentcast_data = get_comps(address, api_key=rentcast_api_key)
        except RentCastError as exc:
            errors.append(f"RentCast: {exc}")

    save_property_lookup(address, county, hcad_data=hcad_data, rentcast_data=rentcast_data)
    result = get_property_lookup(address, county)
    result["errors"] = errors
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Look up one address via RentCast + HCAD and save it.")
    parser.add_argument("address")
    parser.add_argument("--county", default="Harris")
    parser.add_argument("--no-rentcast", action="store_true", help="Skip the RentCast API call")
    parser.add_argument("--no-hcad", action="store_true", help="Skip the HCAD lookup")
    args = parser.parse_args()

    outcome = run_lookup(args.address, county=args.county, skip_rentcast=args.no_rentcast, skip_hcad=args.no_hcad)
    print(json.dumps(outcome, indent=2, default=str))
    if outcome["errors"]:
        for message in outcome["errors"]:
            print(f"WARNING: {message}")
