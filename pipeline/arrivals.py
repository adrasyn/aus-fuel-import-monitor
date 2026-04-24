"""Port arrival detection using geofencing."""

import json
import math
from datetime import datetime, timezone
from pipeline.cargo import estimate_cargo

# Speed cap for "the vessel is parked" — slightly looser than the live-ping
# cap (1.0kn) because the roster pass works on a possibly-old position whose
# instantaneous speed may have been a drift reading just before AIS dropped.
_SILENT_ARRIVAL_SPEED_CAP = 1.0


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

        # Coastal = this vessel hasn't left AU_APPROACH since its last arrival.
        # A coastal arrival isn't a fresh import; we record it (so the dedupe
        # key still works for subsequent runs) but tag it so import totals can
        # exclude it.
        record = vessel_db.get(imo, {})
        departed = record.get("departed_au_since_arrival", True)

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
            "coastal": not departed,
        })

    return new_arrivals


def detect_silent_arrivals(
    vessel_db: dict,
    ports: list[dict],
    existing_arrivals: list[dict],
) -> list[dict]:
    """Detect arrivals from the roster's last-known positions.

    Companion to `detect_arrivals`, which only sees vessels in the *current*
    AIS snapshot. Many tankers go AIS-silent the moment they berth, so their
    last broadcast position is parked-at-port but they never re-appear in a
    later snapshot for the live detector to fire on. Without this scan, those
    vessels linger in `in_transit` until the 14-day staleness prune — and pad
    the en-route headline the entire time.

    Trigger: in_transit vessel whose stored lat/lon is inside a port radius
    AND stored speed is at or below the silent-arrival cap. Mutates the
    in_transit block off the record (matching what live detection does in
    `update_vessel_db`'s arrival pass) and returns the new arrival rows.

    Idempotent: a vessel that already has an arrival record at the same port
    is skipped. The expectation is that the orchestrator runs this *before*
    `detect_arrivals` so the live pass sees an up-to-date in_transit set.
    """
    arrived_imos = {(a["imo"], a["port"]) for a in existing_arrivals}
    new_arrivals = []
    now = datetime.now(timezone.utc).isoformat()

    for imo, record in vessel_db.items():
        in_transit = record.get("in_transit")
        if not in_transit:
            continue
        speed = in_transit.get("speed", 99) or 0
        if speed > _SILENT_ARRIVAL_SPEED_CAP:
            continue
        lat = in_transit.get("lat", 0.0)
        lon = in_transit.get("lon", 0.0)
        port_name = is_within_port(lat, lon, ports)
        if port_name is None:
            continue
        if (imo, port_name) in arrived_imos:
            # Already recorded — clear the stale in_transit so it stops
            # showing on the dashboard, but don't add a duplicate row.
            record["in_transit"] = None
            continue

        cargo = estimate_cargo(
            length=record.get("length", 0),
            beam=record.get("beam", 0),
            draught=in_transit.get("draught", 0),
            ship_type=record.get("ship_type", "product"),
        )

        departed = record.get("departed_au_since_arrival", True)
        new_arrivals.append({
            "imo": imo,
            "name": record.get("name", "Unknown"),
            "port": port_name,
            "timestamp": now,
            "ship_type": record.get("ship_type", "product"),
            "vessel_class": cargo["vessel_class"],
            "cargo_tonnes": cargo["cargo_tonnes"],
            "cargo_litres": cargo["cargo_litres"],
            "draught_missing": cargo["draught_missing"],
            "coastal": not departed,
        })
        record["in_transit"] = None
        record["arrival_count"] = record.get("arrival_count", 0) + 1
        record["departed_au_since_arrival"] = False

    return new_arrivals
