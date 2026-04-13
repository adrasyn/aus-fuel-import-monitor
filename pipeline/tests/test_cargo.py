from pipeline.cargo import classify_vessel, estimate_load_factor, estimate_cargo, TANKER_CLASSES


def test_classify_vlcc():
    result = classify_vessel(length=330, beam=60)
    assert result == "VLCC"

def test_classify_suezmax():
    result = classify_vessel(length=275, beam=50)
    assert result == "Suezmax"

def test_classify_aframax():
    result = classify_vessel(length=245, beam=44)
    assert result == "Aframax"

def test_classify_lr2():
    result = classify_vessel(length=220, beam=32)
    assert result == "LR2/Panamax"

def test_classify_mr():
    result = classify_vessel(length=183, beam=32)
    assert result == "MR"

def test_classify_handysize():
    result = classify_vessel(length=140, beam=22)
    assert result == "Handysize"

def test_load_factor_full():
    factor = estimate_load_factor(draught=16.0, vessel_class="VLCC")
    assert 0.9 < factor <= 1.0

def test_load_factor_ballast():
    factor = estimate_load_factor(draught=8.0, vessel_class="VLCC")
    assert factor < 0.15

def test_load_factor_missing_draught():
    factor = estimate_load_factor(draught=0.0, vessel_class="VLCC")
    assert factor == 0.75

def test_load_factor_clamps_to_zero():
    factor = estimate_load_factor(draught=1.0, vessel_class="VLCC")
    assert factor == 0.0

def test_load_factor_clamps_to_one():
    factor = estimate_load_factor(draught=25.0, vessel_class="VLCC")
    assert factor == 1.0

def test_estimate_cargo_crude():
    result = estimate_cargo(length=330, beam=60, draught=16.0, ship_type="crude")
    assert result["vessel_class"] == "VLCC"
    assert result["cargo_tonnes"] > 200000
    assert result["cargo_litres"] > 0
    assert result["is_ballast"] is False
    assert result["draught_missing"] is False

def test_estimate_cargo_product():
    result = estimate_cargo(length=183, beam=32, draught=10.0, ship_type="product")
    assert result["vessel_class"] == "MR"
    assert result["cargo_litres"] > result["cargo_tonnes"]

def test_estimate_cargo_ballast_detected():
    result = estimate_cargo(length=330, beam=60, draught=8.0, ship_type="crude")
    assert result["is_ballast"] is True

def test_estimate_cargo_missing_draught_flagged():
    result = estimate_cargo(length=245, beam=44, draught=0.0, ship_type="crude")
    assert result["draught_missing"] is True
    assert result["cargo_tonnes"] > 0
