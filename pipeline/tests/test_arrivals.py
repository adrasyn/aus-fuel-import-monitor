from pipeline.arrivals import haversine_km, is_within_port, detect_arrivals

def test_haversine_known_distance():
    dist = haversine_km(-33.87, 151.21, -37.81, 144.96)
    assert 700 < dist < 730

def test_haversine_same_point():
    dist = haversine_km(-33.87, 151.21, -33.87, 151.21)
    assert dist == 0.0

def test_is_within_port_true():
    ports = [{"name": "Melbourne", "lat": -37.84, "lon": 144.92, "radius_km": 5}]
    result = is_within_port(-37.84, 144.92, ports)
    assert result == "Melbourne"

def test_is_within_port_false():
    ports = [{"name": "Melbourne", "lat": -37.84, "lon": 144.92, "radius_km": 5}]
    result = is_within_port(-33.87, 151.21, ports)
    assert result is None

def test_is_within_port_edge():
    ports = [{"name": "Melbourne", "lat": -37.84, "lon": 144.92, "radius_km": 5}]
    result = is_within_port(-37.785, 144.92, ports)
    assert result is None

def test_detect_arrivals_vessel_arrived():
    ports = [{"name": "Geelong", "lat": -38.15, "lon": 144.36, "radius_km": 5}]
    previous_snapshot = {
        "vessels": [
            {"imo": "1234567", "name": "Test Tanker", "lat": -36.0, "lon": 144.0,
             "speed": 12.0, "ship_type": "crude", "length": 245, "beam": 44,
             "draught": 14.5, "destination": "GEELONG"}
        ]
    }
    current_snapshot = {
        "vessels": [
            {"imo": "1234567", "name": "Test Tanker", "lat": -38.15, "lon": 144.36,
             "speed": 0.3, "ship_type": "crude", "length": 245, "beam": 44,
             "draught": 14.5, "destination": "GEELONG"}
        ]
    }
    existing_arrivals = []
    new_arrivals = detect_arrivals(current_snapshot, previous_snapshot, ports, existing_arrivals)
    assert len(new_arrivals) == 1
    assert new_arrivals[0]["port"] == "Geelong"
    assert new_arrivals[0]["imo"] == "1234567"

def test_detect_arrivals_vessel_still_at_sea():
    ports = [{"name": "Geelong", "lat": -38.15, "lon": 144.36, "radius_km": 5}]
    previous_snapshot = {
        "vessels": [
            {"imo": "1234567", "name": "Test Tanker", "lat": -36.0, "lon": 144.0,
             "speed": 12.0, "ship_type": "crude", "length": 245, "beam": 44,
             "draught": 14.5, "destination": "GEELONG"}
        ]
    }
    current_snapshot = {
        "vessels": [
            {"imo": "1234567", "name": "Test Tanker", "lat": -37.0, "lon": 144.2,
             "speed": 11.5, "ship_type": "crude", "length": 245, "beam": 44,
             "draught": 14.5, "destination": "GEELONG"}
        ]
    }
    existing_arrivals = []
    new_arrivals = detect_arrivals(current_snapshot, previous_snapshot, ports, existing_arrivals)
    assert len(new_arrivals) == 0

def test_detect_arrivals_no_duplicate():
    ports = [{"name": "Geelong", "lat": -38.15, "lon": 144.36, "radius_km": 5}]
    previous_snapshot = {
        "vessels": [
            {"imo": "1234567", "name": "Test Tanker", "lat": -38.15, "lon": 144.36,
             "speed": 0.3, "ship_type": "crude", "length": 245, "beam": 44,
             "draught": 14.5, "destination": "GEELONG"}
        ]
    }
    current_snapshot = previous_snapshot
    existing_arrivals = [{"imo": "1234567", "port": "Geelong", "timestamp": "2026-04-12T02:00:00Z"}]
    new_arrivals = detect_arrivals(current_snapshot, previous_snapshot, ports, existing_arrivals)
    assert len(new_arrivals) == 0
