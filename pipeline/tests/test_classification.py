"""Tests for pipeline.classification."""

import json

from pipeline.classification import (
    classify_ship_type,
    is_lng_carrier,
    load_overrides,
)


# ---------- is_lng_carrier ----------

def test_is_lng_carrier_methane_prefix():
    # Real-world: METHANE NILE EAGLE slipped through AIS type 80
    assert is_lng_carrier("METHANE NILE EAGLE") is True


def test_is_lng_carrier_lng_word():
    assert is_lng_carrier("LNG ARIES") is True


def test_is_lng_carrier_gas_carrier():
    assert is_lng_carrier("PACIFIC GAS CARRIER") is True


def test_is_lng_carrier_case_insensitive():
    assert is_lng_carrier("methane nile eagle") is True


def test_is_lng_carrier_oil_tanker_is_not_lng():
    assert is_lng_carrier("HAFNIA MIKALA") is False


def test_is_lng_carrier_empty():
    assert is_lng_carrier("") is False
    assert is_lng_carrier(None) is False


def test_is_lng_carrier_methane_substring_is_not_match():
    # "METHANE" must be a word on its own, not embedded
    assert is_lng_carrier("AMETHANEE TANKER") is False


def test_is_lng_carrier_does_not_exclude_lpg():
    # Scope is "all liquid fuels excluding LNG" — LPG stays
    assert is_lng_carrier("GASCHEM ODYSSEY") is False


# ---------- classify_ship_type: operator hints ----------

def test_classify_hafnia_is_product():
    # Hafnia Limited fleet = product tankers
    assert classify_ship_type("HAFNIA MIKALA", "MR") == "product"


def test_classify_sti_is_product():
    # Scorpio Tankers = product tankers
    assert classify_ship_type("STI MAGISTER", "MR") == "product"


def test_classify_torm_is_product():
    assert classify_ship_type("TORM GERTRUD", "MR") == "product"


def test_classify_euronav_is_crude():
    assert classify_ship_type("EURONAV SOVEREIGN", "Aframax") == "crude"


def test_classify_frontline_is_crude():
    assert classify_ship_type("FRONTLINE ARIES", "Suezmax") == "crude"


# ---------- classify_ship_type: size fallback ----------

def test_classify_mr_defaults_to_product():
    # No operator hint — size fallback: MR is product
    assert classify_ship_type("CHAMPION ENDURANCE", "MR") == "product"


def test_classify_handysize_defaults_to_product():
    assert classify_ship_type("ROSTELLA", "Handysize") == "product"


def test_classify_lr2_panamax_defaults_to_product():
    # LR2 literally stands for "Long Range 2 product tanker"
    assert classify_ship_type("BALLARD", "LR2/Panamax") == "product"


def test_classify_aframax_defaults_to_crude():
    assert classify_ship_type("UNKNOWN SHIP", "Aframax") == "crude"


def test_classify_suezmax_defaults_to_crude():
    assert classify_ship_type("UNKNOWN SHIP", "Suezmax") == "crude"


def test_classify_vlcc_defaults_to_crude():
    assert classify_ship_type("UNKNOWN SHIP", "VLCC") == "crude"


def test_classify_unknown_class_defaults_to_product():
    # Last-resort fallback
    assert classify_ship_type("MYSTERY SHIP", "MysteryClass") == "product"


# ---------- classify_ship_type: overrides ----------

def test_classify_override_beats_size_heuristic():
    # Hand-maintained override: this Handysize is actually crude
    overrides = {"1234567": "crude"}
    assert classify_ship_type("MYSTERY", "Handysize", imo="1234567", overrides=overrides) == "crude"


def test_classify_override_beats_operator_hint():
    # Override even trumps operator hint — the hand-maintained file is truth
    overrides = {"9999999": "crude"}
    assert classify_ship_type("HAFNIA MIKALA", "MR", imo="9999999", overrides=overrides) == "crude"


def test_classify_missing_imo_falls_through_to_heuristic():
    overrides = {"1234567": "crude"}
    assert classify_ship_type("HAFNIA MIKALA", "MR", imo="7654321", overrides=overrides) == "product"


def test_classify_invalid_override_value_is_ignored():
    # Override must be crude or product — anything else falls through
    overrides = {"1234567": "wibble"}
    assert classify_ship_type("UNKNOWN", "Aframax", imo="1234567", overrides=overrides) == "crude"


def test_classify_overrides_none_same_as_empty():
    assert classify_ship_type("UNKNOWN", "MR", imo="1234567", overrides=None) == "product"


def test_classify_empty_name_falls_through_to_class():
    assert classify_ship_type("", "MR") == "product"
    assert classify_ship_type(None, "Aframax") == "crude"


# ---------- load_overrides ----------

def test_load_overrides_missing_file_returns_empty(tmp_path):
    path = str(tmp_path / "vessel-overrides.json")
    assert load_overrides(path) == {}


def test_load_overrides_well_formed_file(tmp_path):
    path = tmp_path / "vessel-overrides.json"
    path.write_text(json.dumps({"1234567": "crude", "7654321": "product"}))
    assert load_overrides(str(path)) == {"1234567": "crude", "7654321": "product"}


def test_load_overrides_malformed_json_returns_empty(tmp_path):
    path = tmp_path / "vessel-overrides.json"
    path.write_text("{not json")
    assert load_overrides(str(path)) == {}


def test_load_overrides_non_dict_returns_empty(tmp_path):
    path = tmp_path / "vessel-overrides.json"
    path.write_text(json.dumps(["not a dict"]))
    assert load_overrides(str(path)) == {}


def test_load_overrides_normalises_values_to_lowercase(tmp_path):
    path = tmp_path / "vessel-overrides.json"
    path.write_text(json.dumps({"1234567": "Crude", "7654321": "PRODUCT"}))
    assert load_overrides(str(path)) == {"1234567": "crude", "7654321": "product"}
