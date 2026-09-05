"""Deterministic cross-source matching. No AI calls — rapidfuzz string
scoring only.

Two passes, because not every source carries a property address:
  1. Cluster records that DO have an address (tax_delinquent,
     trustee_sale, absentee_owner) by fuzzy address match.
  2. Probate filings only identify a deceased owner, not a property, so
     they're joined onto an existing cluster by fuzzy owner-name match
     within the same county. A probate record with no confident owner
     match becomes its own "address unknown" lead rather than being
     dropped — it's still an actionable lead, just missing an address
     the investor would need to look up manually.

distress_score = count of distinct source_types in the final cluster.
"""
from dataclasses import dataclass, field
from typing import List, Optional

from rapidfuzz import fuzz

from models import LeadRecord, SOURCE_PROBATE
from normalize import normalize_address, normalize_owner_name, house_number

ADDRESS_MATCH_THRESHOLD = 90

# Deliberately fuzz.ratio, not fuzz.WRatio, for the owner-name join below.
# Confirmed live 2026-09-02: WRatio's token-set-style scoring gives a big
# credit for ANY shared word, which is fine for addresses (street names
# rarely collide) but wrong for person names — "DAVIS FARRAR M" vs
# "MARGARET ELIZABETH DAVIS MEYERS" (unrelated people, share only
# "DAVIS") scored 85.5 under WRatio, well above the old 85 threshold,
# while fuzz.ratio scored it 53.3. Since normalize_owner_name() already
# sorts tokens (making word order irrelevant), plain fuzz.ratio on the
# pre-sorted strings is the right comparison — it rewards whole-name
# similarity instead of crediting single-word overlap. Biased toward
# precision over recall on purpose: a wrong join here means telling the
# investor a stranger's estate belongs to someone else's property, which
# is worse than a real match landing in the "address unknown" bucket.
OWNER_MATCH_THRESHOLD = 90

UNKNOWN_ADDRESS_LABEL = "(address unknown — see case_no)"


# How the Address column got filled, so the investor can tell a
# county-filed address from one this pipeline inferred.
ADDRESS_SOURCE_FILED = "filed"          # came straight off the source record
ADDRESS_SOURCE_HCAD = "hcad_owner"      # recovered from the HCAD roll by owner name
ADDRESS_SOURCE_UNKNOWN = "unknown"      # still not recoverable


@dataclass
class MatchedLead:
    address: str
    owner_name: str
    county: str
    distress_score: int
    sources_hit: List[str]
    records: List[LeadRecord] = field(default_factory=list)

    # Filled by enrich.py after clustering; defaults keep every existing
    # caller (and every test that builds a MatchedLead positionally)
    # working unchanged.
    address_source: str = ADDRESS_SOURCE_FILED
    address_confidence: Optional[float] = None
    parcel_id: Optional[str] = None
    mailing_address: Optional[str] = None
    market_value: Optional[float] = None
    year_built: Optional[int] = None
    building_sqft: Optional[int] = None
    hcad_matched_owner: Optional[str] = None

    @property
    def case_numbers(self) -> str:
        """Every case_no in the cluster, comma-joined. The report used to
        tell the reader to "see case_no" without carrying a case_no
        column; this is what that column reads from.
        """
        seen = []
        for rec in self.records:
            if rec.case_no and rec.case_no not in seen:
                seen.append(rec.case_no)
        return ", ".join(seen)

    @property
    def source_urls(self) -> str:
        seen = []
        for rec in self.records:
            if rec.source_url and rec.source_url not in seen:
                seen.append(rec.source_url)
        return ", ".join(seen)


def _block_key(county: str, normalized_addr: str) -> str:
    # Same county + same leading house number = candidate block. Keeps the
    # O(n^2) fuzzy comparison scoped to a small bucket instead of the whole
    # dataset, without sacrificing determinism.
    #
    # Some sources (e.g. Harris trustee-sale filings) carry a subdivision/
    # lot/block legal description instead of a street address — those never
    # have a leading house number. Falling back to house_number()=="" for
    # all of them would dump every such record into one giant bucket and
    # let shared boilerplate words ("DESC", "LOT", "BLOCK") fuzzy-match
    # unrelated properties together. Fall back to the full normalized
    # string instead: only records that are already identical after
    # normalization share a block, which is conservative (won't force
    # incorrect merges) even though it means near-duplicates with no house
    # number won't get merged either — legal descriptions need real parcel
    # matching to do that safely, which is out of scope here.
    num = house_number(normalized_addr)
    return f"{county}|{num}" if num else f"{county}|noaddr|{normalized_addr}"


def _cluster_addressed(records: List[LeadRecord]) -> List[List[int]]:
    n = len(records)
    normed = [normalize_address(r.address) for r in records]

    blocks = {}
    for i in range(n):
        blocks.setdefault(_block_key(records[i].county, normed[i]), []).append(i)

    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            if ra < rb:
                parent[rb] = ra
            else:
                parent[ra] = rb

    for indices in blocks.values():
        for a in range(len(indices)):
            for b in range(a + 1, len(indices)):
                i, j = indices[a], indices[b]
                if fuzz.WRatio(normed[i], normed[j]) >= ADDRESS_MATCH_THRESHOLD:
                    union(i, j)

    clusters = {}
    for i in range(n):
        clusters.setdefault(find(i), []).append(i)
    return [clusters[root] for root in sorted(clusters.keys())]


def cluster_records(records: List[LeadRecord]) -> List[MatchedLead]:
    addressed = [r for r in records if r.address and r.address.strip()]
    unaddressed = [r for r in records if not (r.address and r.address.strip())]

    groups_idx = _cluster_addressed(addressed) if addressed else []
    groups = [[addressed[i] for i in idxs] for idxs in groups_idx]

    # cache one normalized-owner-name-set per group for the join pass
    group_owner_norms = [
        {normalize_owner_name(r.owner_name) for r in g if r.owner_name} for g in groups
    ]

    leftover_probate = []
    for probate_rec in unaddressed:
        probate_norm = normalize_owner_name(probate_rec.owner_name)
        best_group_i, best_score = None, 0
        tied_groups = set()
        for gi, group in enumerate(groups):
            if group[0].county != probate_rec.county:
                continue
            for owner_norm in group_owner_norms[gi]:
                if not owner_norm:
                    continue
                score = fuzz.ratio(probate_norm, owner_norm)
                if score > best_score:
                    best_score, best_group_i = score, gi
                    tied_groups = {gi}
                elif score == best_score:
                    tied_groups.add(gi)
        if best_score >= OWNER_MATCH_THRESHOLD and len(tied_groups) == 1:
            groups[best_group_i].append(probate_rec)
        else:
            leftover_probate.append(probate_rec)

    results = []
    for group in groups:
        sources = sorted(set(r.source_type for r in group))
        best = max(group, key=lambda r: len(r.address or ""))
        best_owner = max(group, key=lambda r: len(r.owner_name or ""))
        results.append(MatchedLead(
            address=best.address,
            owner_name=best_owner.owner_name,
            county=best.county,
            distress_score=len(sources),
            sources_hit=sources,
            records=group,
        ))

    # each unmatched probate case is still a lead, just without a known address
    for rec in leftover_probate:
        results.append(MatchedLead(
            address=UNKNOWN_ADDRESS_LABEL,
            owner_name=rec.owner_name,
            county=rec.county,
            distress_score=1,
            sources_hit=[rec.source_type],
            records=[rec],
            address_source=ADDRESS_SOURCE_UNKNOWN,
        ))

    # stable sort: distress_score desc, then address asc for deterministic tie-breaking
    results.sort(key=lambda m: (-m.distress_score, m.address))
    return results
