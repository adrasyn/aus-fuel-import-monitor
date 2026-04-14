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


def test_locode_aubtb_botany():
    assert parse_destination("AUBTB") == "Sydney / Botany"


def test_locode_aukwi_fremantle():
    # Kwinana is part of the Fremantle metro port complex
    assert parse_destination("AUKWI") == "Fremantle"


def test_locode_aubuy_bunbury():
    assert parse_destination("AUBUY") == "Bunbury"


def test_locode_auglt_gladstone():
    assert parse_destination("AUGLT") == "Gladstone"


def test_locode_aufre_fremantle():
    assert parse_destination("AUFRE") == "Fremantle"


def test_locode_aumel_melbourne():
    assert parse_destination("AUMEL") == "Melbourne"


def test_locode_ausyd_sydney():
    assert parse_destination("AUSYD") == "Sydney / Botany"


def test_locode_audar_darwin():
    assert parse_destination("AUDAR") == "Darwin"


def test_locode_aubne_brisbane():
    assert parse_destination("AUBNE") == "Brisbane"


def test_locode_autsv_townsville():
    assert parse_destination("AUTSV") == "Townsville"


def test_locode_auadl_adelaide():
    assert parse_destination("AUADL") == "Adelaide"


def test_locode_aupkl_port_kembla():
    assert parse_destination("AUPKL") == "Port Kembla"


def test_bunbury_full_name():
    # New port entry added alongside the LOCODE
    assert parse_destination("BUNBURY") == "Bunbury"
