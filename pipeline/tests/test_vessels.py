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
