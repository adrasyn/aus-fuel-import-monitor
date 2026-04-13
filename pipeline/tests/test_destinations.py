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
