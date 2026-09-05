"""Fill in the columns the source records left empty.

Runs after match.py clusters, before the report is written. Two jobs:

  1. Recover a property address for leads that have none. Probate filings
     name a decedent, never a property, and match.py can only attach one
     to a property we already had distress evidence for. Everything else
     used to print "(address unknown - see case_no)". HCAD's bulk roll
     maps county-wide owner names to properties, so most of those are
     recoverable locally -- see hcad_owner_index.py.

  2. Backfill the property facts (mailing address, market value, year
     built, size, parcel id) for every lead, addressed or not, so the
     report has no blank cells where HCAD knows the answer.

Everything here is deterministic and offline. If the HCAD index has not
been built, this is a no-op and the pipeline output is unchanged.
"""
from typing import List, Optional

from hcad_owner_index import DEFAULT_MIN_SCORE, HcadOwnerIndex
from match import (
    ADDRESS_SOURCE_FILED,
    ADDRESS_SOURCE_HCAD,
    ADDRESS_SOURCE_UNKNOWN,
    MatchedLead,
    UNKNOWN_ADDRESS_LABEL,
)
from normalize import normalize_address

# The HCAD roll only covers Harris County. Nacogdoches leads pass through
# untouched rather than being matched against the wrong county's roll.
HCAD_COUNTY = "Harris"

# A name that resolves to more than this many distinct parcels at the same
# confidence is ambiguous -- a landlord with a portfolio, or a common name
# colliding. We record the count and leave the address unknown rather than
# picking one of them arbitrarily and presenting it as fact.
MAX_AMBIGUOUS_PARCELS = 1


def _is_unknown(lead: MatchedLead) -> bool:
    return not lead.address or lead.address == UNKNOWN_ADDRESS_LABEL


def _apply_parcel(lead: MatchedLead, match) -> None:
    lead.parcel_id = match.acct
    lead.mailing_address = match.mail_addr or lead.mailing_address
    lead.market_value = match.market_value
    lead.year_built = match.year_built
    lead.building_sqft = match.building_sqft


def _recover_address(lead: MatchedLead, index: HcadOwnerIndex, min_score: float) -> bool:
    matches = index.lookup(lead.owner_name, min_score=min_score)
    if not matches:
        return False

    best = matches[0]
    # Ambiguity check runs against the parcels tied at the top score, not
    # the whole result list: a clear best match beside weaker ones is
    # still a usable answer.
    tied = [m for m in matches if m.score == best.score]
    if len(tied) > MAX_AMBIGUOUS_PARCELS:
        return False

    lead.address = best.full_address or best.site_addr
    lead.address_source = ADDRESS_SOURCE_HCAD
    lead.address_confidence = best.score
    lead.hcad_matched_owner = best.matched_owner_name
    _apply_parcel(lead, best)
    return True


def _backfill_facts(lead: MatchedLead, index: HcadOwnerIndex) -> None:
    """For an already-addressed lead, attach the HCAD parcel that sits at
    that address so the value/size/mailing columns are populated too.
    """
    if lead.parcel_id:
        return
    target = normalize_address(lead.address)
    if not target:
        return
    for match in index.lookup(lead.owner_name, min_score=DEFAULT_MIN_SCORE, limit=10):
        if normalize_address(match.site_addr) == target:
            _apply_parcel(lead, match)
            return


def enrich_leads(leads: List[MatchedLead], index: Optional[HcadOwnerIndex] = None,
                 min_score: float = DEFAULT_MIN_SCORE) -> dict:
    """Enrich in place. Returns a summary dict for the run log."""
    index = index or HcadOwnerIndex()
    stats = {
        "index_available": index.available,
        "unknown_before": sum(1 for lead in leads if _is_unknown(lead)),
        "addresses_recovered": 0,
        "facts_backfilled": 0,
        "unknown_after": 0,
    }
    if not index.available:
        stats["unknown_after"] = stats["unknown_before"]
        return stats

    for lead in leads:
        if lead.county != HCAD_COUNTY:
            continue
        if _is_unknown(lead):
            if _recover_address(lead, index, min_score):
                stats["addresses_recovered"] += 1
        else:
            if lead.address_source == ADDRESS_SOURCE_UNKNOWN:
                lead.address_source = ADDRESS_SOURCE_FILED
            _backfill_facts(lead, index)
            if lead.parcel_id:
                stats["facts_backfilled"] += 1

    stats["unknown_after"] = sum(1 for lead in leads if _is_unknown(lead))

    # Re-sort so recovered addresses land in the same deterministic order
    # the rest of the pipeline promises.
    leads.sort(key=lambda m: (-m.distress_score, m.address))
    return stats
