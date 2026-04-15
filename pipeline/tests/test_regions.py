"""Tests for pipeline.regions."""

from pipeline.regions import (
    REGIONS,
    bounding_boxes_for_subscription,
    classify_region,
    should_keep_vessel,
)


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


def test_should_keep_au_approach_without_destination():
    assert should_keep_vessel("AU_APPROACH", None) is True


def test_should_keep_au_approach_with_destination():
    assert should_keep_vessel("AU_APPROACH", "Fremantle") is True


def test_should_keep_origin_region_with_au_destination():
    assert should_keep_vessel("MIDDLE_EAST", "Fremantle") is True


def test_should_keep_origin_region_with_au_unknown_port():
    assert should_keep_vessel("US_GULF", "Australia (port unknown)") is True


def test_drop_origin_region_without_destination():
    assert should_keep_vessel("US_GULF", None) is False


def test_drop_vessel_outside_all_regions():
    # region is None — vessel is not in any subscribed box
    assert should_keep_vessel(None, None) is False


def test_drop_vessel_outside_all_regions_even_with_destination():
    assert should_keep_vessel(None, "Fremantle") is False


def test_bounding_boxes_for_subscription_shape():
    boxes = bounding_boxes_for_subscription()

    # One box per region
    assert len(boxes) == len(REGIONS)

    # Each box is a 2-element list of [lat, lon] pairs (AISStream format)
    for box in boxes:
        assert len(box) == 2
        assert len(box[0]) == 2
        assert len(box[1]) == 2


def test_bounding_boxes_for_subscription_includes_au_approach():
    boxes = bounding_boxes_for_subscription()
    assert [[-50.0, 90.0], [-5.0, 170.0]] in boxes


def test_classify_region_java_sea_off_lamongan():
    # Java Sea cluster observed in real data
    assert classify_region(-6.85, 112.44) == "JAVA_SEA"


def test_classify_region_java_sea_takes_priority_over_au_approach():
    # The carve-out must be listed BEFORE AU_APPROACH so Java Sea wins
    # at lat -6.85 (which is also inside the broad AU_APPROACH box).
    assert classify_region(-6.85, 112.44) == "JAVA_SEA"


def test_classify_region_south_of_java_sea_still_au_approach():
    # South of the Java coast (-7.5 cutoff) → falls through to AU_APPROACH
    assert classify_region(-8.0, 112.0) == "AU_APPROACH"


def test_classify_region_east_of_java_sea_still_au_approach():
    # East of lon 117 (Bali/Flores Sea) → falls through to AU_APPROACH
    assert classify_region(-7.0, 121.0) == "AU_APPROACH"


def test_should_drop_java_sea_vessel_without_au_destination():
    # Java Sea vessel with Indonesian destination — must be dropped
    assert should_keep_vessel("JAVA_SEA", None) is False


def test_should_keep_java_sea_vessel_with_au_destination():
    # Hypothetical: a vessel in the Java Sea with AU destination → keep
    assert should_keep_vessel("JAVA_SEA", "Fremantle") is True


def test_should_drop_au_approach_vessel_with_explicit_foreign_destination():
    # Real-world: SOUTHERN LEADER off SE QLD, raw destination "NZ NPL".
    # AU_APPROACH normally keeps unconditionally — but explicit foreign overrides.
    assert should_keep_vessel("AU_APPROACH", None, destination_raw="NZ NPL") is False


def test_should_drop_au_approach_vessel_with_foreign_locode():
    assert should_keep_vessel("AU_APPROACH", None, destination_raw="USFLL") is False


def test_should_keep_au_approach_vessel_with_au_destination_passed_raw():
    # Backwards-compatible: passing a raw AU destination is fine
    assert should_keep_vessel("AU_APPROACH", "Fremantle", destination_raw="AUKWI") is True


def test_should_keep_au_approach_vessel_when_raw_omitted():
    # Backwards-compatible: caller may omit destination_raw
    assert should_keep_vessel("AU_APPROACH", None) is True
