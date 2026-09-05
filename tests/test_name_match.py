"""Cases here are real pairs from the 2026 HCAD roll and the Harris County
probate docket, not invented ones -- each `ratio=` note is what plain
fuzz.ratio scored the same pair, which is why name_match exists.
"""
from rapidfuzz import fuzz

from name_match import MIN_STRONG_PAIRS, score_names
from normalize import normalize_owner_name


def score(probate_name, hcad_name):
    return score_names(normalize_owner_name(probate_name), normalize_owner_name(hcad_name))


def test_identical_names_score_100():
    result = score("KIM VU", "VU KIM")
    assert result.score == 100.0
    assert result.is_confident


def test_middle_name_abbreviated_to_initial_still_matches():
    # ratio=89.5 -- below any threshold safe enough to invent an address
    result = score("IN THE ESTATE OF: ROWLAND CLYDE FREEMAN, DECEASED", "FREEMAN ROWLAND C")
    assert result.score >= 93
    assert result.is_confident


def test_joint_deed_matches_once_split_into_one_person_per_row():
    """The decedent is reachable through the SPLIT half of a joint deed,
    not through the flattened line. build_hcad_owner_index.py does the
    splitting; the scorer's job is to reject the flattened form, because
    an unexplained "BEVERLY" is indistinguishable from the extra given
    name that made GUSTAVO A GOMEZ PEREZ a false positive.
    """
    decedent = "IN THE ESTATE OF: JOSEPH WADE GIACONE, DECEASED"
    # ratio=74.4 on the flattened line, and the WRONG candidate
    # ("WADE JOSEPH A JR") beat it at 81.2 on shared whole words
    assert score(decedent, "GIACONE JOSEPH W & BEVERLY").score < 93
    assert score(decedent, "WADE JOSEPH A JR").score < 93

    split = score(decedent, "GIACONE JOSEPH W")
    assert split.score >= 93
    assert split.is_confident


def test_extra_given_name_in_the_candidate_is_rejected():
    """Real false positives from the 2026 roll, both accepted when an
    unpaired whole word only cost 3 points.
    """
    # "A" pairs with ADELAIDA by coincidence; GUSTAVO is the real given name
    assert score("ADELAIDA GOMEZ PEREZ", "GOMEZ GUSTAVO A PEREZ").score < 93
    assert score("DAVID RODRIGUEZ LOPEZ", "RODRIGUEZ DARWIN DAVID LOPEZ").score < 93
    # a second surname is the same problem
    assert score("PAUL VICENTE CARRENO", "PRIETO PAUL V CARRENO").score < 93


def test_unpaired_initial_in_the_candidate_costs_nothing():
    """HCAD adds middle initials the filing does not have; that must not
    be penalized the way an extra whole name is.
    """
    assert score("STEVEN WAYNE EVANS", "EVANS STEVEN W").score >= 93
    assert score("KATHY WILLIS", "WILLIS KATHY E").strong_pairs == 2


def test_leading_given_name_abbreviated_still_matches():
    # ratio=84.8
    result = score("IN THE ESTATE OF: NORMAN EUGENE JONES, DECEASED", "JONES NORMAN E")
    assert result.score >= 93


def test_initial_must_agree_with_the_first_letter():
    """'GEAN' vs 'C' is not a middle-initial match. Without this the
    initial rule would wave through any name with an initial in it.
    """
    result = score("BARBARA GEAN TURNER", "TURNER BARBARA C")
    assert result.score < 93


def test_missing_middle_name_entirely_is_not_enough():
    result = score("BARBARA GEAN TURNER", "TURNER BARBARA")
    assert result.score < 93


def test_different_middle_surname_does_not_match():
    """'DAVID RODRIGUEZ LOPEZ' and 'RODRIGUEZ DAVID P' share two whole
    tokens but the third disagrees outright.
    """
    result = score("IN THE ESTATE OF: DAVID RODRIGUEZ LOPEZ, DECEASED", "RODRIGUEZ DAVID P")
    assert result.score < 93


def test_shared_surname_alone_is_not_confident():
    result = score("FRANK S. ALEXANDER", "ALEXANDER MARIA G")
    assert not result.is_confident or result.score < 93


def test_unrelated_names_score_low():
    result = score("IN THE ESTATE OF: FRANK S. ALEXANDER, DECEASED", "ROOPNARINE VIJAY S")
    assert result.score < 60


def test_single_shared_token_is_never_confident():
    result = score("JOHN SMITH", "SMITH PATRICIA ANNE")
    assert result.strong_pairs < MIN_STRONG_PAIRS


def test_pairing_is_order_independent():
    """normalize_owner_name sorts tokens alphabetically, so a naive
    left-to-right pairing would match GEAN<->TURNER and leave the real
    TURNER<->TURNER pair unused.
    """
    a = score("BARBARA GEAN TURNER", "TURNER BARBARA")
    b = score("TURNER GEAN BARBARA", "BARBARA TURNER")
    assert a.score == b.score
    assert a.strong_pairs == 2  # BARBARA and TURNER both landed


def test_beats_plain_ratio_on_the_cases_that_motivated_it():
    pairs = [
        ("ROWLAND CLYDE FREEMAN", "FREEMAN ROWLAND C"),
        ("JOSEPH WADE GIACONE", "GIACONE JOSEPH W & BEVERLY"),
        ("NORMAN EUGENE JONES", "JONES NORMAN E"),
    ]
    for probate, hcad in pairs:
        q, c = normalize_owner_name(probate), normalize_owner_name(hcad)
        assert score_names(q, c).score > fuzz.ratio(q, c)


def test_empty_input_is_safe():
    assert score_names("", "SMITH JOHN").score == 0.0
    assert score_names("SMITH JOHN", "").score == 0.0
