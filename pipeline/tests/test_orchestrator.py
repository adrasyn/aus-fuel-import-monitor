from datetime import datetime, timezone

from pipeline.orchestrator import rebucket_monthly_from_arrivals, update_monthly_estimates, migrate_coastal_on_arrivals


def test_update_monthly_estimates_sums_en_route_from_roster():
    monthly = {"months": {}}
    vessel_db = {
        "9000001": {
            "name": "Crude One", "vessel_class": "VLCC", "dwt": 300000,
            "length": 333, "beam": 60, "ship_type": "crude",
            "first_seen": "2026-04-01T00:00:00Z",
            "last_seen": "2026-04-14T12:00:00Z",
            "arrival_count": 0,
            "in_transit": {
                "mmsi": "636011111", "lat": -10.0, "lon": 110.0,
                "speed": 12.0, "course": 180.0, "heading": 180.0, "draught": 22.0,
                "destination": "AU FRE", "destination_parsed": "Fremantle",
                "region": "AU_APPROACH",
                "cargo_litres": 320_000_000, "cargo_tonnes": 280_000,
                "load_factor": 0.95, "is_ballast": False, "draught_missing": False,
                "last_position_update": "2026-04-14T12:00:00Z",
            },
        },
        "9000002": {
            "name": "Product One", "vessel_class": "MR", "dwt": 50000,
            "length": 180, "beam": 32, "ship_type": "product",
            "first_seen": "2026-04-01T00:00:00Z",
            "last_seen": "2026-04-14T12:00:00Z",
            "arrival_count": 0,
            "in_transit": {
                "mmsi": "636022222", "lat": -25.0, "lon": 130.0,
                "speed": 11.0, "course": 200.0, "heading": 200.0, "draught": 12.0,
                "destination": "AU MEL", "destination_parsed": "Melbourne",
                "region": "AU_APPROACH",
                "cargo_litres": 60_000_000, "cargo_tonnes": 50_000,
                "load_factor": 0.9, "is_ballast": False, "draught_missing": False,
                "last_position_update": "2026-04-14T12:00:00Z",
            },
        },
        "9000003": {
            # Ballast — must not contribute to en-route totals
            "name": "Ballast One", "vessel_class": "Aframax", "dwt": 100000,
            "length": 245, "beam": 44, "ship_type": "crude",
            "first_seen": "2026-04-01T00:00:00Z",
            "last_seen": "2026-04-14T12:00:00Z",
            "arrival_count": 0,
            "in_transit": {
                "mmsi": "636033333", "lat": -20.0, "lon": 120.0,
                "speed": 10.0, "course": 90.0, "heading": 90.0, "draught": 7.0,
                "destination": "", "destination_parsed": None,
                "region": "AU_APPROACH",
                "cargo_litres": 0, "cargo_tonnes": 0,
                "load_factor": 0.0, "is_ballast": True, "draught_missing": False,
                "last_position_update": "2026-04-14T12:00:00Z",
            },
        },
        "9000004": {
            # Arrived (in_transit = None) — must not contribute to en-route
            "name": "Arrived One", "vessel_class": "Aframax", "dwt": 100000,
            "length": 245, "beam": 44, "ship_type": "crude",
            "first_seen": "2026-03-01T00:00:00Z",
            "last_seen": "2026-04-13T22:00:00Z",
            "arrival_count": 1,
            "in_transit": None,
        },
    }
    updated = update_monthly_estimates(monthly, [], vessel_db)
    months = updated["months"]
    assert len(months) == 1
    month = next(iter(months.values()))
    assert month["en_route_crude_litres"] == 320_000_000
    assert month["en_route_product_litres"] == 60_000_000


def test_update_monthly_estimates_excludes_coastal_arrivals_from_totals():
    monthly = {"months": {}}
    new_arrivals = [
        {
            "imo": "9000001", "ship_type": "crude",
            "cargo_litres": 100_000_000, "cargo_tonnes": 90_000,
            "coastal": False,
        },
        {
            "imo": "9000002", "ship_type": "product",
            "cargo_litres": 40_000_000, "cargo_tonnes": 35_000,
            "coastal": True,  # must not bump counters
        },
    ]
    updated = update_monthly_estimates(monthly, new_arrivals, {})
    month = next(iter(updated["months"].values()))
    assert month["arrival_count"] == 1
    assert month["arrived_crude_litres"] == 100_000_000
    assert month["arrived_product_litres"] == 0


def test_update_monthly_estimates_excludes_coastal_from_en_route():
    monthly = {"months": {}}
    vessel_db = {
        "9000001": {
            "name": "International", "vessel_class": "Aframax", "dwt": 100000,
            "length": 245, "beam": 44, "ship_type": "crude",
            "first_seen": "2026-04-01T00:00:00Z",
            "last_seen": "2026-04-14T12:00:00Z",
            "arrival_count": 0,
            "departed_au_since_arrival": True,
            "in_transit": {
                "cargo_litres": 200_000_000, "is_ballast": False,
                "lat": -10.0, "lon": 110.0,
                "last_position_update": "2026-04-14T12:00:00Z",
            },
        },
        "9000002": {
            "name": "Coastal Hop", "vessel_class": "Aframax", "dwt": 100000,
            "length": 245, "beam": 44, "ship_type": "crude",
            "first_seen": "2026-04-01T00:00:00Z",
            "last_seen": "2026-04-14T12:00:00Z",
            "arrival_count": 1,
            "departed_au_since_arrival": False,
            "in_transit": {
                "cargo_litres": 50_000_000, "is_ballast": False,
                "lat": -34.0, "lon": 151.0,
                "last_position_update": "2026-04-14T12:00:00Z",
            },
        },
    }
    updated = update_monthly_estimates(monthly, [], vessel_db)
    month = next(iter(updated["months"].values()))
    assert month["en_route_crude_litres"] == 200_000_000


def test_migrate_coastal_on_arrivals_first_arrival_not_coastal():
    arrivals = [{"imo": "A", "port": "Brisbane", "timestamp": "2026-04-01T00:00:00+00:00"}]
    migrated = migrate_coastal_on_arrivals(arrivals)
    assert migrated == 1
    assert arrivals[0]["coastal"] is False


def test_migrate_coastal_on_arrivals_within_window_flagged_coastal():
    arrivals = [
        {"imo": "A", "port": "Brisbane", "timestamp": "2026-04-01T00:00:00+00:00"},
        {"imo": "A", "port": "Westernport", "timestamp": "2026-04-08T00:00:00+00:00"},
    ]
    migrated = migrate_coastal_on_arrivals(arrivals)
    assert migrated == 2
    assert arrivals[0]["coastal"] is False
    assert arrivals[1]["coastal"] is True  # 7-day gap, different port


def test_migrate_coastal_on_arrivals_outside_window_not_coastal():
    arrivals = [
        {"imo": "A", "port": "Brisbane", "timestamp": "2026-03-01T00:00:00+00:00"},
        {"imo": "A", "port": "Westernport", "timestamp": "2026-04-10T00:00:00+00:00"},
    ]
    migrated = migrate_coastal_on_arrivals(arrivals)
    assert migrated == 2
    assert arrivals[1]["coastal"] is False  # 40-day gap → international trip


def test_migrate_coastal_on_arrivals_idempotent():
    arrivals = [
        {"imo": "A", "port": "Brisbane", "timestamp": "2026-04-01T00:00:00+00:00",
         "coastal": True},
    ]
    migrated = migrate_coastal_on_arrivals(arrivals)
    assert migrated == 0
    assert arrivals[0]["coastal"] is True  # preserved


def test_migrate_coastal_on_arrivals_separates_by_imo():
    # Different vessels — arrivals don't influence each other's coastal status.
    arrivals = [
        {"imo": "A", "port": "Brisbane", "timestamp": "2026-04-01T00:00:00+00:00"},
        {"imo": "B", "port": "Westernport", "timestamp": "2026-04-03T00:00:00+00:00"},
    ]
    migrate_coastal_on_arrivals(arrivals)
    assert arrivals[0]["coastal"] is False
    assert arrivals[1]["coastal"] is False


def test_rebucket_splits_confirmed_and_probable():
    arrivals = [
        {"imo": "a", "port": "Geelong", "timestamp": "2026-05-03T00:00:00+00:00",
         "ship_type": "product", "cargo_litres": 100, "cargo_tonnes": 80, "status": "confirmed"},
        {"imo": "b", "port": "Geelong", "timestamp": "2026-05-04T00:00:00+00:00",
         "ship_type": "product", "cargo_litres": 40, "cargo_tonnes": 33, "status": "probable"},
        {"imo": "c", "port": "Brisbane", "timestamp": "2026-05-05T00:00:00+00:00",
         "ship_type": "crude", "cargo_litres": 90, "cargo_tonnes": 77},  # no status → confirmed
    ]
    monthly = rebucket_monthly_from_arrivals({"months": {}}, arrivals)
    m = monthly["months"]["2026-05"]
    assert m["arrived_product_litres"] == 100
    assert m["arrived_crude_litres"] == 90
    assert m["arrival_count"] == 2  # confirmed only
    assert m["probable_product_litres"] == 40
    assert m["probable_count"] == 1


def test_en_route_excludes_probable_marked_records():
    db = {
        "x": {"ship_type": "product", "departed_au_since_arrival": True,
              "in_transit": {"is_ballast": False, "cargo_litres": 500}},
        "y": {"ship_type": "product", "departed_au_since_arrival": True,
              "probable_arrival": {"port": "Geelong", "since": "z"},
              "in_transit": {"is_ballast": False, "cargo_litres": 999}},
    }
    monthly = update_monthly_estimates({"months": {}}, [], db,
                                       now=datetime(2026, 5, 20, tzinfo=timezone.utc))
    m = monthly["months"]["2026-05"]
    assert m["en_route_product_litres"] == 500  # y excluded
