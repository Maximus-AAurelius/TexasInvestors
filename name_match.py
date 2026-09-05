"""Person-name similarity that understands middle initials.

Plain fuzz.ratio on a whole normalized name is the right call in match.py,
where both sides come from filings that spell names out. It is the wrong
call against the HCAD roll, which abbreviates aggressively: the appraisal
district records "FREEMAN ROWLAND C" where a probate filing says "ROWLAND
CLYDE FREEMAN". Those are the same person and fuzz.ratio scores them 89.5
-- below any threshold safe enough to invent an address from -- purely
because five characters of a middle name are missing.

Confirmed live against the 2026 roll, the same way:
  GIACONE JOSEPH WADE  vs  GIACONE JOSEPH W & BEVERLY   ratio 74.4
  EUGENE JONES NORMAN  vs  JONES NORMAN E               ratio 84.8
Both correct matches; both unreachable by whole-string ratio. Meanwhile
the same scoring happily rated wrong answers higher: "WADE JOSEPH A JR"
beat the real "GIACONE JOSEPH W" at 81.2 vs 74.4, because it shares two
whole words.

So compare token-to-token instead:
  - identical tokens score 100
  - a single letter against a word scores INITIAL_SCORE if it is that
    word's first letter, and 0 otherwise (an initial is weak evidence,
    never a free pass -- "GEAN" vs "C" must not match)
  - anything else falls back to fuzz.ratio on the pair

Pairing is greedy over ALL token pairs by descending score, not in token
order. Token order matters because normalize_owner_name() sorts
alphabetically, so "BARBARA GEAN TURNER" vs "BARBARA TURNER" would
otherwise pair GEAN<->TURNER and leave the real TURNER<->TURNER match
unpaired.
"""
from dataclasses import dataclass
from typing import List

from rapidfuzz import fuzz

# An initial agreeing with a first letter is real evidence, but weaker
# than a spelled-out match: it must not on its own carry a name over the
# acceptance threshold.
INITIAL_SCORE = 90.0

# Tokens the candidate has and the query does not. Length decides how much
# they matter, because an unpaired WHOLE WORD is a different-person signal
# while an unpaired initial is not.
#
# Confirmed live against the 2026 roll, at a flat 3-point penalty:
#   ADELAIDA GOMEZ PEREZ  matched  GOMEZ GUSTAVO A PEREZ    at 93.7
#   DAVID RODRIGUEZ LOPEZ matched  RODRIGUEZ DARWIN DAVID LOPEZ at 97.0
# Both wrong. In the first, "ADELAIDA" paired with the initial "A" by
# coincidence while the real given name "GUSTAVO" sat unpaired; in the
# second the extra given name "DARWIN" was the whole difference between two
# people. An unpaired full word has to cost more than a rounding error.
#
# The spouse case this used to protect ("GIACONE JOSEPH W & BEVERLY") is
# handled properly now: build_hcad_owner_index.py splits joint deeds on
# "&" into one row per person, so BEVERLY is her own indexed name rather
# than an extra token hanging off her husband's.
EXTRA_FULL_TOKEN_PENALTY = 12.0
EXTRA_INITIAL_PENALTY = 0.0
MAX_EXTRA_TOKEN_PENALTY = 24.0

# A pair at or above this counts as a "strong" agreement. Requiring two of
# them means surname AND given name both landed, which is what stops two
# strangers sharing one common surname from matching.
STRONG_PAIR_SCORE = 90.0
MIN_STRONG_PAIRS = 2


@dataclass
class NameScore:
    score: float
    strong_pairs: int

    @property
    def is_confident(self) -> bool:
        return self.strong_pairs >= MIN_STRONG_PAIRS


def token_similarity(a: str, b: str) -> float:
    if a == b:
        return 100.0
    if len(a) == 1 or len(b) == 1:
        return INITIAL_SCORE if a[0] == b[0] else 0.0
    return float(fuzz.ratio(a, b))


def score_names(query_norm: str, candidate_norm: str) -> NameScore:
    """Compare two ALREADY-normalized names (normalize_owner_name output)."""
    query_tokens: List[str] = query_norm.split()
    cand_tokens: List[str] = candidate_norm.split()
    if not query_tokens or not cand_tokens:
        return NameScore(0.0, 0)
    if query_norm == candidate_norm:
        return NameScore(100.0, len(query_tokens))

    pairs = sorted(
        (
            (token_similarity(q, c), qi, ci)
            for qi, q in enumerate(query_tokens)
            for ci, c in enumerate(cand_tokens)
        ),
        key=lambda p: (-p[0], p[1], p[2]),  # deterministic on ties
    )

    used_q, used_c, matched = set(), set(), []
    for score, qi, ci in pairs:
        if qi in used_q or ci in used_c:
            continue
        used_q.add(qi)
        used_c.add(ci)
        matched.append(score)

    # Query tokens with no partner left count as misses, not as absent.
    matched += [0.0] * (len(query_tokens) - len(matched))
    base = sum(matched) / len(matched)

    penalty = min(
        sum(
            EXTRA_INITIAL_PENALTY if len(token) == 1 else EXTRA_FULL_TOKEN_PENALTY
            for ci, token in enumerate(cand_tokens)
            if ci not in used_c
        ),
        MAX_EXTRA_TOKEN_PENALTY,
    )
    strong = sum(1 for s in matched if s >= STRONG_PAIR_SCORE)
    return NameScore(max(0.0, round(base - penalty, 1)), strong)
