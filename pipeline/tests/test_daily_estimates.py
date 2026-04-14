"""Tests for pipeline.daily_estimates."""

from datetime import datetime, timezone

from pipeline.daily_estimates import update_daily_estimates


def _in_transit(cargo_litres: int, is_ballast: bool = False) -> dict:
    return {
        "mmsi": "636000000", "lat": -25.0, "lon": 130.0,
        "speed": 12.0, "course": 180.0, "heading": 180.0, "draught": 14.0,
        "destination": "AU FRE", "destination_parsed": "Fremantle",
        "region": "AU_APPROACH",
        "cargo_litres": cargo_litres, "cargo_tonnes": 0,
        "load_factor": 0.9, "is_ballast": is_ballast, "draught_missing": False,
        "last_position_update": "2026-04-14T12:00:00Z",
    }


def _vessel_record(ship_type: str, in_transit: dict | None) -> dict:
    return {
        "name": "Test Tanker", "vessel_class": "Aframax", "dwt": 100000,
        "length": 245, "beam": 44, "ship_type": ship_type,
        "first_seen": "2026-04-01T00:00:00Z",
        "last_seen": "2026-04-14T12:00:00Z",
        "arrival_count": 0,
        "in_transit": in_transit,
    }


def test_update_daily_estimates_sums_laden_crude_and_product():
    daily = {"days": {}}
    vessel_db = {
        "9000001": _vessel_record("crude", _in_transit(320_000_000)),
        "9000002": _vessel_record("product", _in_transit(60_000_000)),
    }
    now = datetime(2026, 4, 14, 12, 30, tzinfo=timezone.utc)
    updated = update_daily_estimates(daily, vessel_db, now)

    assert "2026-04-14" in updated["days"]
    entry = updated["days"]["2026-04-14"]
    assert entry["en_route_crude_litres"] == 320_000_000
    assert entry["en_route_product_litres"] == 60_000_000
    assert entry["captured_at"] == "2026-04-14T12:30:00+00:00"


def test_update_daily_estimates_skips_ballast():
    daily = {"days": {}}
    vessel_db = {
        "9000001": _vessel_record("crude", _in_transit(320_000_000)),
        "9000002": _vessel_record("crude", _in_transit(0, is_ballast=True)),
    }
    now = datetime(2026, 4, 14, 12, 30, tzinfo=timezone.utc)
    updated = update_daily_estimates(daily, vessel_db, now)

    assert updated["days"]["2026-04-14"]["en_route_crude_litres"] == 320_000_000


def test_update_daily_estimates_skips_arrived_records():
    daily = {"days": {}}
    vessel_db = {
        "9000001": _vessel_record("crude", _in_transit(320_000_000)),
        # Arrived — in_transit is None — must not contribute
        "9000002": _vessel_record("crude", None),
    }
    now = datetime(2026, 4, 14, 12, 30, tzinfo=timezone.utc)
    updated = update_daily_estimates(daily, vessel_db, now)

    assert updated["days"]["2026-04-14"]["en_route_crude_litres"] == 320_000_000


def test_update_daily_estimates_same_day_rerun_overwrites():
    daily = {
        "days": {
            "2026-04-14": {
                "en_route_crude_litres": 1,
                "en_route_product_litres": 1,
                "captured_at": "2026-04-14T01:00:00+00:00",
            }
        }
    }
    vessel_db = {
        "9000001": _vessel_record("crude", _in_transit(500_000_000)),
    }
    now = datetime(2026, 4, 14, 23, 30, tzinfo=timezone.utc)
    updated = update_daily_estimates(daily, vessel_db, now)

    entry = updated["days"]["2026-04-14"]
    assert entry["en_route_crude_litres"] == 500_000_000
    assert entry["en_route_product_litres"] == 0
    assert entry["captured_at"] == "2026-04-14T23:30:00+00:00"
    assert len(updated["days"]) == 1


def test_update_daily_estimates_preserves_prior_days():
    daily = {
        "days": {
            "2026-04-13": {
                "en_route_crude_litres": 100_000_000,
                "en_route_product_litres": 50_000_000,
                "captured_at": "2026-04-13T12:00:00+00:00",
            }
        }
    }
    vessel_db = {
        "9000001": _vessel_record("crude", _in_transit(200_000_000)),
    }
    now = datetime(2026, 4, 14, 12, 0, tzinfo=timezone.utc)
    updated = update_daily_estimates(daily, vessel_db, now)

    # Prior day untouched
    assert updated["days"]["2026-04-13"]["en_route_crude_litres"] == 100_000_000
    # Today added
    assert updated["days"]["2026-04-14"]["en_route_crude_litres"] == 200_000_000
    assert len(updated["days"]) == 2
