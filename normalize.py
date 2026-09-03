"""Deterministic address/owner-name normalization. No AI calls — pure string logic."""
import re

_STREET_SUFFIXES = {
    "STREET": "ST", "AVENUE": "AVE", "DRIVE": "DR", "BOULEVARD": "BLVD",
    "LANE": "LN", "ROAD": "RD", "COURT": "CT", "CIRCLE": "CIR",
    "PLACE": "PL", "TRAIL": "TRL", "PARKWAY": "PKWY", "HIGHWAY": "HWY",
    "SQUARE": "SQ", "TERRACE": "TER", "LOOP": "LOOP", "WAY": "WAY",
    "CROSSING": "XING", "POINT": "PT", "RIDGE": "RDG", "VALLEY": "VLY",
    "MEADOW": "MDW", "MEADOWS": "MDWS", "ESTATES": "EST", "EXTENSION": "EXT",
}

_DIRECTIONALS = {
    "NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W",
    "NORTHEAST": "NE", "NORTHWEST": "NW", "SOUTHEAST": "SE", "SOUTHWEST": "SW",
}

_UNIT_WORDS = {"APT", "APARTMENT", "UNIT", "STE", "SUITE", "#"}

# Whole-phrase boilerplate that prefixes probate "style" text — must be
# stripped as PHRASES, not individual noise tokens, since word-level
# stripping alone leaves connector words ("IN", "THE") behind. Those
# words are common enough that they were previously making unrelated
# probate records fuzzy-match each other (and even unrelated absentee
# owners) at ~85+ WRatio purely from shared boilerplate, not real name
# similarity — confirmed live: "IN THE ESTATE OF: FRANK S. ALEXANDER,
# DECEASED" matched "ROOPNARINE VIJAY S" at 85.5, a false positive.
_OWNER_BOILERPLATE_PHRASES = [
    r"\bIN THE ESTATE OF\b",
    r"\bIN THE GUARDIANSHIP OF\b",
    r"\bIN THE MATTER OF\b",
    r"\bESTATE OF\b",
    r"\bIN RE\b",
]

_OWNER_TRAILING_SUFFIXES = [
    r",?\s*DECEASED\s*$",
    r",?\s*TESTATOR\s*$",
    r",?\s*INCAPACITATED\s*$",
]

_OWNER_NOISE_TOKENS = {
    "ESTATE", "OF", "DECEASED", "ET", "AL", "AND", "&", "TRUST", "TRUSTEE",
}

_OWNER_SUFFIXES = {"JR", "SR", "II", "III", "IV", "V"}


def _strip_punct(s: str) -> str:
    return re.sub(r"[.,#:;]", " ", s)


def normalize_address(raw: str) -> str:
    """Uppercase, strip punctuation, expand/abbreviate street suffixes and
    directionals to USPS-style abbreviations, collapse whitespace.
    Drops unit/apt info so '123 Main St' and '123 Main St Apt 4' both
    normalize to '123 MAIN ST' for property-level matching.
    """
    if not raw:
        return ""
    s = raw.upper()
    s = _strip_punct(s)
    tokens = s.split()

    cleaned = []
    skip_next = False
    for i, tok in enumerate(tokens):
        if skip_next:
            skip_next = False
            continue
        if tok in _UNIT_WORDS:
            # drop the unit word and, if present, the following unit value
            if i + 1 < len(tokens):
                skip_next = True
            continue
        tok = _STREET_SUFFIXES.get(tok, tok)
        tok = _DIRECTIONALS.get(tok, tok)
        cleaned.append(tok)

    return " ".join(cleaned).strip()


def normalize_owner_name(raw: str) -> str:
    """Uppercase, strip probate boilerplate phrases and trailing role
    labels, strip punctuation, drop remaining noise tokens (ET AL,
    generational suffixes), sort remaining words so word order doesn't
    matter (e.g. 'SMITH JOHN' == 'JOHN SMITH').
    """
    if not raw:
        return ""
    s = raw.upper()
    for phrase in _OWNER_BOILERPLATE_PHRASES:
        s = re.sub(phrase, " ", s)
    for suffix in _OWNER_TRAILING_SUFFIXES:
        s = re.sub(suffix, "", s)
    s = _strip_punct(s)
    tokens = [t for t in s.split() if t not in _OWNER_NOISE_TOKENS and t not in _OWNER_SUFFIXES]
    return " ".join(sorted(tokens))


def house_number(normalized_address: str) -> str:
    """First numeric token of a normalized address, used as a coarse
    blocking key so the matcher doesn't compare every record to every
    other record.
    """
    match = re.match(r"^(\d+)", normalized_address)
    return match.group(1) if match else ""
