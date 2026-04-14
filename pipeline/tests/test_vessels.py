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


from pipeline.vessels import prune_stale_in_transit, STALENESS_DAYS


def test_prune_clears_in_transit_older_than_threshold():
    db = {
        "9000001": {
            "name": "Old Tanker", "vessel_class": "Aframax", "dwt": 100000,
            "length": 245, "beam": 44, "ship_type": "crude",
            "first_seen": "2026-03-01T00:00:00Z",
            "last_seen": "2026-03-31T00:00:00Z",
            "arrival_count": 0,
            "in_transit": {
                "lat": -10.0, "lon": 110.0, "speed": 12.0,
                "course": 180.0, "heading": 180.0, "draught": 14.5,
                "destination": "AU FRE", "destination_parsed": "Fremantle",
                "region": "AU_APPROACH",
                "cargo_litres": 80_000_000, "cargo_tonnes": 70_000,
                "load_factor": 0.9, "is_ballast": False, "draught_missing": False,
                "mmsi": "100000001",
                "last_position_update": "2026-03-31T00:00:00Z",  # 14+ days old
            },
        }
    }
    prune_stale_in_transit(db, now="2026-04-14T12:00:00Z")
    assert db["9000001"]["in_transit"] is None


def test_prune_keeps_in_transit_within_threshold():
    db = {
        "9000002": {
            "name": "Recent Tanker", "vessel_class": "Aframax", "dwt": 100000,
            "length": 245, "beam": 44, "ship_type": "crude",
            "first_seen": "2026-04-01T00:00:00Z",
            "last_seen": "2026-04-13T00:00:00Z",
            "arrival_count": 0,
            "in_transit": {
                "lat": -10.0, "lon": 110.0, "speed": 12.0,
                "course": 180.0, "heading": 180.0, "draught": 14.5,
                "destination": "AU FRE", "destination_parsed": "Fremantle",
                "region": "AU_APPROACH",
                "cargo_litres": 80_000_000, "cargo_tonnes": 70_000,
                "load_factor": 0.9, "is_ballast": False, "draught_missing": False,
                "mmsi": "100000002",
                "last_position_update": "2026-04-13T00:00:00Z",  # 1 day old
            },
        }
    }
    prune_stale_in_transit(db, now="2026-04-14T12:00:00Z")
    assert db["9000002"]["in_transit"] is not None


def test_prune_skips_records_without_in_transit():
    # Already-arrived (or migration) records have no in_transit. No mutation.
    db = {
        "9000003": {
            "name": "Arrived Tanker", "vessel_class": "Aframax", "dwt": 100000,
            "length": 245, "beam": 44, "ship_type": "crude",
            "first_seen": "2026-03-01T00:00:00Z",
            "last_seen": "2026-04-13T00:00:00Z",
            "arrival_count": 1,
            # no in_transit key at all
        }
    }
    prune_stale_in_transit(db, now="2026-04-14T12:00:00Z")
    assert "in_transit" not in db["9000003"]


def test_update_vessel_db_populates_in_transit_for_pinged_vessels():
    db = {}
    vessels = [
        {
            "imo": "9876543", "mmsi": "636019825", "name": "Test Tanker",
            "length": 245, "beam": 44, "draught": 14.5,
            "ship_type": "crude",
            "lat": -25.5, "lon": 130.2,
            "speed": 12.4, "course": 180.0, "heading": 180.0,
            "destination": "AU GLT", "destination_parsed": "Gladstone",
            "region": "AU_APPROACH",
            "cargo_litres": 95_000_000, "cargo_tonnes": 80_000,
            "load_factor": 0.95, "is_ballast": False, "draught_missing": False,
        }
    ]
    updated = update_vessel_db(db, vessels)
    assert updated["9876543"]["in_transit"] is not None
    assert updated["9876543"]["in_transit"]["destination_parsed"] == "Gladstone"
    assert updated["9876543"]["in_transit"]["lat"] == -25.5


def test_update_vessel_db_preserves_in_transit_for_unseen_vessel():
    # Vessel was in the roster yesterday with in_transit set; not pinged today.
    # Today's snapshot is empty for this IMO — in_transit must persist.
    yesterday_in_transit = {
        "mmsi": "636019825", "lat": -10.0, "lon": 100.0,
        "speed": 12.0, "course": 90.0, "heading": 90.0, "draught": 14.5,
        "destination": "AU FRE", "destination_parsed": "Fremantle",
        "region": "AU_APPROACH",
        "cargo_litres": 80_000_000, "cargo_tonnes": 70_000,
        "load_factor": 0.9, "is_ballast": False, "draught_missing": False,
        "last_position_update": "2026-04-13T00:00:00Z",
    }
    db = {
        "9876543": {
            "name": "Test Tanker", "vessel_class": "Aframax", "dwt": 100000,
            "length": 245, "beam": 44, "ship_type": "crude",
            "first_seen": "2026-04-01T00:00:00Z",
            "last_seen": "2026-04-13T00:00:00Z",
            "arrival_count": 0,
            "in_transit": yesterday_in_transit,
        }
    }
    updated = update_vessel_db(db, [])  # empty snapshot
    assert updated["9876543"]["in_transit"] == yesterday_in_transit


def test_update_vessel_db_clears_in_transit_on_arrival():
    db = {
        "9876543": {
            "name": "Test Tanker", "vessel_class": "Aframax", "dwt": 100000,
            "length": 245, "beam": 44, "ship_type": "crude",
            "first_seen": "2026-04-01T00:00:00Z",
            "last_seen": "2026-04-13T00:00:00Z",
            "arrival_count": 0,
            "in_transit": {
                "mmsi": "636019825", "lat": -38.0, "lon": 144.4,
                "speed": 0.5, "course": 0.0, "heading": 0.0, "draught": 14.5,
                "destination": "AU GEE", "destination_parsed": "Geelong",
                "region": "AU_APPROACH",
                "cargo_litres": 80_000_000, "cargo_tonnes": 70_000,
                "load_factor": 0.9, "is_ballast": False, "draught_missing": False,
                "last_position_update": "2026-04-13T22:00:00Z",
            },
        }
    }
    new_arrivals = [{"imo": "9876543", "port": "Geelong"}]
    updated = update_vessel_db(db, [], new_arrivals=new_arrivals)
    assert updated["9876543"]["in_transit"] is None
    assert updated["9876543"]["arrival_count"] == 1


def test_update_vessel_db_prunes_stale_in_transit():
    # Vessel last pinged 20 days ago — must be cleared.
    db = {
        "9876543": {
            "name": "Old Tanker", "vessel_class": "Aframax", "dwt": 100000,
            "length": 245, "beam": 44, "ship_type": "crude",
            "first_seen": "2026-03-01T00:00:00Z",
            "last_seen": "2026-03-25T00:00:00Z",
            "arrival_count": 0,
            "in_transit": {
                "mmsi": "636019825", "lat": -10.0, "lon": 110.0,
                "speed": 12.0, "course": 180.0, "heading": 180.0, "draught": 14.5,
                "destination": "AU FRE", "destination_parsed": "Fremantle",
                "region": "AU_APPROACH",
                "cargo_litres": 80_000_000, "cargo_tonnes": 70_000,
                "load_factor": 0.9, "is_ballast": False, "draught_missing": False,
                "last_position_update": "2026-03-25T00:00:00Z",
            },
        }
    }
    updated = update_vessel_db(db, [])  # no fresh ping
    assert updated["9876543"]["in_transit"] is None
