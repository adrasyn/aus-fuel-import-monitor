from pipeline.orchestrator import update_monthly_estimates


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
