from normalize import normalize_address, normalize_owner_name, house_number


def test_address_suffix_abbreviation():
    assert normalize_address("123 Main Street") == "123 MAIN ST"
    assert normalize_address("123 MAIN ST") == "123 MAIN ST"


def test_address_drops_unit():
    assert normalize_address("456 Oak Ave Apt 4") == "456 OAK AVE"
    assert normalize_address("456 Oak Ave") == "456 OAK AVE"


def test_address_directional():
    assert normalize_address("789 N. Elm Dr.") == "789 N ELM DR"


def test_owner_name_order_independent():
    assert normalize_owner_name("Smith, John") == normalize_owner_name("John Smith")


def test_owner_name_strips_probate_noise():
    assert normalize_owner_name("Estate of John Smith") == normalize_owner_name("John Smith")


def test_house_number():
    assert house_number("123 MAIN ST") == "123"
    assert house_number("MAIN ST") == ""
