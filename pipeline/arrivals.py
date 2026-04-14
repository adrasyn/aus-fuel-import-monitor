"""Port arrival detection using geofencing."""

import json
import math
from datetime import datetime, timezone
from pipeline.cargo import estimate_cargo


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def load_ports(ports_path: str = "data/ports.json") -> list[dict]:
    with open(ports_path) as f:
        return json.load(f)["ports"]


def is_within_port(lat: float, lon: float, ports: list[dict]) -> str | None:
    for port in ports:
        dist = haversine_km(lat, lon, port["lat"], port["lon"])
        if dist <= port["radius_km"]:
            return port["name"]
    return None


def detect_arrivals(
    current_snapshot: dict,
    vessel_db: dict,
    ports: list[dict],
    existing_arrivals: list[dict],
) -> list[dict]:
    """Detect new port arrivals.

    A vessel counts as a new arrival when:
    - it appears in the current snapshot at speed < 1.0 inside a port radius
    - the roster has it as in_transit (we previously knew it was on a trip)
    - the (imo, port) pair has not already been recorded
    """
    arrived_imos = {(a["imo"], a["port"]) for a in existing_arrivals}
    in_transit_imos = {
        imo for imo, record in vessel_db.items()
        if record.get("in_transit") is not None
    }
    new_arrivals = []
    now = datetime.now(timezone.utc).isoformat()

    for vessel in current_snapshot.get("vessels", []):
        imo = vessel["imo"]
        speed = vessel.get("speed", 99)
        lat = vessel["lat"]
        lon = vessel["lon"]

        if speed >= 1.0:
            continue
        port_name = is_within_port(lat, lon, ports)
        if port_name is None:
            continue
        if imo not in in_transit_imos:
            continue
        if (imo, port_name) in arrived_imos:
            continue

        cargo = estimate_cargo(
            length=vessel.get("length", 0),
            beam=vessel.get("beam", 0),
            draught=vessel.get("draught", 0),
            ship_type=vessel.get("ship_type", "product"),
        )

        new_arrivals.append({
            "imo": imo,
            "name": vessel.get("name", "Unknown"),
            "port": port_name,
            "timestamp": now,
            "ship_type": vessel.get("ship_type", "product"),
            "vessel_class": cargo["vessel_class"],
            "cargo_tonnes": cargo["cargo_tonnes"],
            "cargo_litres": cargo["cargo_litres"],
            "draught_missing": cargo["draught_missing"],
        })

    return new_arrivals
