"""Tests for pipeline.regions."""

from pipeline.regions import classify_region


def test_classify_region_in_au_approach():
    # Off southern WA coast
    assert classify_region(-32.0, 115.0) == "AU_APPROACH"


def test_classify_region_in_middle_east():
    # Strait of Hormuz area
    assert classify_region(26.0, 56.0) == "MIDDLE_EAST"


def test_classify_region_in_us_gulf():
    # Off Houston
    assert classify_region(28.0, -94.0) == "US_GULF"


def test_classify_region_in_us_west_coast():
    # Off Los Angeles
    assert classify_region(33.0, -120.0) == "US_WEST_COAST"


def test_classify_region_in_china():
    # Off Shanghai
    assert classify_region(31.0, 122.0) == "CHINA"


def test_classify_region_in_korea_japan():
    # Tokyo Bay area
    assert classify_region(35.0, 140.0) == "KOREA_JAPAN"


def test_classify_region_in_india():
    # Off Mumbai
    assert classify_region(19.0, 72.0) == "INDIA"


def test_classify_region_in_se_asia():
    # Off Singapore
    assert classify_region(1.3, 103.8) == "SE_ASIA"


def test_classify_region_in_philippines():
    # Off Manila Bay
    assert classify_region(14.5, 120.9) == "PHILIPPINES"


def test_classify_region_outside_all_boxes():
    # Mid-Atlantic, no subscribed box
    assert classify_region(0.0, -30.0) is None


def test_classify_region_boundary_inclusive():
    # Exact lat_min / lon_min of AU_APPROACH is considered inside
    assert classify_region(-50.0, 90.0) == "AU_APPROACH"
