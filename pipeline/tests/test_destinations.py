from pipeline.destinations import parse_destination

def test_exact_match():
    assert parse_destination("MELBOURNE") == "Melbourne"

def test_abbreviation():
    assert parse_destination("MELB") == "Melbourne"

def test_au_prefix():
    assert parse_destination("AU MEL") == "Melbourne"

def test_au_prefix_geelong():
    assert parse_destination("AU GEE") == "Geelong"

def test_port_kembla():
    assert parse_destination("PORT KEMBLA") == "Port Kembla"

def test_sydney_botany():
    assert parse_destination("BOTANY BAY") == "Sydney / Botany"

def test_case_insensitive():
    assert parse_destination("brisbane") == "Brisbane"

def test_whitespace_stripped():
    assert parse_destination("  FREMANTLE  ") == "Fremantle"

def test_unknown_australian():
    assert parse_destination("AUSTRALIA") == "Australia (port unknown)"

def test_unknown_non_australian():
    assert parse_destination("SINGAPORE") is None

def test_empty_string():
    assert parse_destination("") is None

def test_none_input():
    assert parse_destination(None) is None

def test_darwin():
    assert parse_destination("DARWIN") == "Darwin"

def test_gladstone():
    assert parse_destination("GLADSTONE") == "Gladstone"

def test_adelaide():
    assert parse_destination("ADELAIDE") == "Adelaide"


def test_everglades_does_not_false_match_gladstone():
    # "glad" is a substring of "everglades" but not a word inside it
    assert parse_destination("EVERGLADES") is None


def test_port_everglades_does_not_false_match_gladstone():
    # Real-world false positive observed in first multi-region run
    assert parse_destination("PORT EVERGLADES") is None


def test_bare_glad_still_matches_gladstone():
    # Whitespace-delimited bare abbreviation must still resolve
    assert parse_destination("GLAD") == "Gladstone"


def test_au_glad_still_matches_gladstone():
    # Country-prefixed short form must still resolve
    assert parse_destination("AU GLAD") == "Gladstone"


def test_freeport_does_not_false_match_fremantle():
    # "fre" is a substring of "freeport" but not a word inside it
    assert parse_destination("FREEPORT") is None
