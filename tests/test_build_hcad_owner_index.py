"""Joint-deed splitting. HCAD writes two owners on one line, surname
first, with the second reduced to a given name -- keeping that structure
is what lets a probate filing reach either person.
"""
from scripts.build_hcad_owner_index import split_joint_owners


def test_bare_given_name_inherits_the_surname():
    assert split_joint_owners("GIACONE JOSEPH W & BEVERLY") == [
        "GIACONE JOSEPH W", "GIACONE BEVERLY",
    ]


def test_second_owner_keeps_a_middle_initial():
    assert split_joint_owners("SMITH JOHN & MARY A") == ["SMITH JOHN", "SMITH MARY A"]


def test_generational_suffix_stays_with_the_first_owner():
    assert split_joint_owners("SMOKE JAMES FRANKLIN JR & MARY O") == [
        "SMOKE JAMES FRANKLIN JR", "SMOKE MARY O",
    ]


def test_the_word_and_splits_too():
    assert split_joint_owners("SMITH JOHN AND MARY") == ["SMITH JOHN", "SMITH MARY"]


def test_repeated_surname_is_not_doubled():
    assert split_joint_owners("SMITH JOHN & SMITH MARY") == ["SMITH JOHN", "SMITH MARY"]


def test_single_owner_produces_no_split():
    assert split_joint_owners("JONES NORMAN E") == []
    assert split_joint_owners("") == []


def test_three_owners_all_inherit_the_surname():
    assert split_joint_owners("NGUYEN AN & BINH & CHI") == [
        "NGUYEN AN", "NGUYEN BINH", "NGUYEN CHI",
    ]
