from pipeline.vessels import update_vessel_db

def test_new_vessel_added():
    db = {}
    vessels = [
        {"imo": "9876543", "name": "Test Tanker", "length": 245, "beam": 44,
         "draught": 14.5, "ship_type": "crude"}
    ]
    updated = update_vessel_db(db, vessels)
    assert "9876543" in updated
    assert updated["9876543"]["name"] == "Test Tanker"
    assert updated["9876543"]["vessel_class"] == "Aframax"
    assert updated["9876543"]["dwt"] == 100000
    assert updated["9876543"]["arrival_count"] == 0

def test_existing_vessel_updated():
    db = {
        "9876543": {
            "name": "Test Tanker", "vessel_class": "Aframax", "dwt": 100000,
            "length": 245, "beam": 44, "ship_type": "crude",
            "first_seen": "2026-04-01T00:00:00Z",
            "last_seen": "2026-04-10T00:00:00Z",
            "arrival_count": 2,
        }
    }
    vessels = [
        {"imo": "9876543", "name": "Test Tanker", "length": 245, "beam": 44,
         "draught": 14.5, "ship_type": "crude"}
    ]
    updated = update_vessel_db(db, vessels)
    assert updated["9876543"]["arrival_count"] == 2  # unchanged
    assert updated["9876543"]["last_seen"] != "2026-04-10T00:00:00Z"  # updated

def test_vessel_without_imo_skipped():
    db = {}
    vessels = [
        {"imo": "", "name": "No IMO", "length": 100, "beam": 20,
         "draught": 5.0, "ship_type": "product"}
    ]
    updated = update_vessel_db(db, vessels)
    assert len(updated) == 0

def test_increment_arrival_count():
    db = {
        "9876543": {
            "name": "Test Tanker", "vessel_class": "Aframax", "dwt": 100000,
            "length": 245, "beam": 44, "ship_type": "crude",
            "first_seen": "2026-04-01T00:00:00Z",
            "last_seen": "2026-04-10T00:00:00Z",
            "arrival_count": 2,
        }
    }
    new_arrivals = [{"imo": "9876543", "port": "Geelong"}]
    updated = update_vessel_db(db, [], new_arrivals=new_arrivals)
    assert updated["9876543"]["arrival_count"] == 3


from pipeline.vessels import build_in_transit


def test_build_in_transit_copies_dynamic_fields():
    snapshot_row = {
        "imo": "9876543",
        "mmsi": "636019825",
        "name": "Test Tanker",
        "ship_type": "crude",
        "lat": -25.5, "lon": 130.2,
        "speed": 12.4, "course": 180.0, "heading": 180.0,
        "draught": 14.5,
        "destination": "AU GLT",
        "destination_parsed": "Gladstone",
        "region": "AU_APPROACH",
        "cargo_litres": 95_000_000,
        "cargo_tonnes": 80_000,
        "load_factor": 0.95,
        "is_ballast": False,
        "draught_missing": False,
        "vessel_class": "Aframax",
        "dwt": 80_000,
        "length": 250, "beam": 44,
        "last_update": "2026-04-14T12:30:00Z",
    }
    in_transit = build_in_transit(snapshot_row, now="2026-04-14T13:00:00Z")
    assert in_transit["mmsi"] == "636019825"
    assert in_transit["lat"] == -25.5
    assert in_transit["lon"] == 130.2
    assert in_transit["destination_parsed"] == "Gladstone"
    assert in_transit["region"] == "AU_APPROACH"
    assert in_transit["cargo_litres"] == 95_000_000
    assert in_transit["is_ballast"] is False
    assert in_transit["last_position_update"] == "2026-04-14T13:00:00Z"


def test_build_in_transit_omits_static_top_level_fields():
    # Static fields like name/length/beam/ship_type live on the parent
    # vessel record; they must NOT also appear in in_transit.
    snapshot_row = {
        "imo": "9876543", "mmsi": "636019825", "name": "Test Tanker",
        "ship_type": "crude", "length": 250, "beam": 44,
        "vessel_class": "Aframax", "dwt": 80_000,
        "lat": 0.0, "lon": 0.0, "speed": 0.0, "course": 0.0, "heading": 0.0,
        "draught": 0.0, "destination": "", "destination_parsed": None,
        "region": "AU_APPROACH",
        "cargo_litres": 0, "cargo_tonnes": 0, "load_factor": 0.0,
        "is_ballast": True, "draught_missing": True,
        "last_update": "2026-04-14T12:30:00Z",
    }
    in_transit = build_in_transit(snapshot_row, now="2026-04-14T13:00:00Z")
    assert "name" not in in_transit
    assert "length" not in in_transit
    assert "beam" not in in_transit
    assert "ship_type" not in in_transit
    assert "vessel_class" not in in_transit
    assert "dwt" not in in_transit
