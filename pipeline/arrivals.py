"""Port arrival detection using geofencing."""

import json
import math
from datetime import datetime, timezone, timedelta
from pipeline.cargo import estimate_cargo

# Speed cap for "the vessel is parked" — slightly looser than the live-ping
# cap (1.0kn) because the roster pass works on a possibly-old position whose
# instantaneous speed may have been a drift reading just before AIS dropped.
_SILENT_ARRIVAL_SPEED_CAP = 1.0

# Probable-arrival ("approached then vanished") tunables. A laden, AU-bound
# vessel that goes AIS-dark near a port is inferred to have berthed.
DARK_DAYS = 4          # days silent before a probable arrival fires
INNER_KM = 50          # within this of a port → proximity alone (no kinematic check)
APPROACH_KM = 150      # outer max distance from a port for "approached"
SLOW_KN = 1.5          # at/below → treated as anchored/slowing (outer band)
HEADING_TOL = 75.0     # max course deviation from bearing-to-port for "closing" (outer band)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial great-circle bearing from point 1 to point 2, in degrees (0-360, 0=N)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


def angular_diff(a: float, b: float) -> float:
    """Smallest absolute difference between two compass bearings, in degrees (0-180)."""
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


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
    arrived_imos = {
        (a["imo"], a["port"]) for a in existing_arrivals
        if a.get("status") != "probable"
    }
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
    arrived_imos = {
        (a["imo"], a["port"]) for a in existing_arrivals
        if a.get("status") != "probable"
    }
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


def reconcile_probable_arrivals(
    vessel_db: dict,
    current_vessels: list[dict],
    arrivals: list[dict],
) -> int:
    """Resolve probable rows against confirmations and reappearances.

    1. Upgrade: drop any probable row whose (imo, port) now has a confirmed
       arrival (incl. backfilled probables superseded by a real berth).
    2. Reversal: for a record still marked probable that pinged this run but was
       NOT confirmed, the "vanished" inference is void — drop its probable row
       and clear the marker so it returns to normal in-transit tracking.

    Mutates `arrivals` in place. Returns the number of probable rows removed.
    """
    pinged = {v.get("imo", "") for v in current_vessels if v.get("imo")}
    confirmed_keys = {
        (a["imo"], a["port"]) for a in arrivals
        if a.get("status") != "probable"
    }

    removed = 0
    kept = []
    for a in arrivals:
        if a.get("status") == "probable" and (a["imo"], a["port"]) in confirmed_keys:
            removed += 1
            continue
        kept.append(a)
    arrivals[:] = kept

    for imo, record in vessel_db.items():
        pa = record.get("probable_arrival")
        if not pa:
            continue
        port = pa["port"]
        if (imo, port) in confirmed_keys:
            record["probable_arrival"] = None  # upgraded; row already dropped above
            continue
        if imo in pinged:
            before = len(arrivals)
            arrivals[:] = [
                a for a in arrivals
                if not (a.get("status") == "probable" and a["imo"] == imo and a["port"] == port)
            ]
            removed += before - len(arrivals)
            record["probable_arrival"] = None

    return removed


def _resolve_probable_port(in_transit: dict, lat: float, lon: float, ports: list[dict]):
    """Pick the port P a vanished vessel is most likely heading to.

    Prefer the declared destination if it names a known port within
    APPROACH_KM; otherwise the nearest port within APPROACH_KM. Returns
    (port_dict, distance_km) or (None, None) if nothing is in range.
    """
    if not ports:
        return None, None
    dest = in_transit.get("destination_parsed")
    if dest:
        named = [p for p in ports if p["name"] == dest]
        if named:
            p = min(named, key=lambda pt: haversine_km(lat, lon, pt["lat"], pt["lon"]))
            d = haversine_km(lat, lon, p["lat"], p["lon"])
            if d <= APPROACH_KM:
                return p, d
    p = min(ports, key=lambda pt: haversine_km(lat, lon, pt["lat"], pt["lon"]))
    d = haversine_km(lat, lon, p["lat"], p["lon"])
    if d <= APPROACH_KM:
        return p, d
    return None, None


def detect_probable_arrivals(
    vessel_db: dict,
    ports: list[dict],
    current_vessels: list[dict],
    existing_arrivals: list[dict],
    now: str,
) -> list[dict]:
    """Infer arrivals for laden, AU-bound vessels that went AIS-dark near a port.

    Fires on roster records that: are laden, on a fresh international leg, NOT in
    the current ping batch (vanished), dark >= DARK_DAYS, and last seen within
    APPROACH_KM of a port. Within INNER_KM proximity alone qualifies; in the
    50-150km band the vessel must also be anchored/slowing OR on a closing
    heading. Sets record["probable_arrival"] and returns new probable rows.
    Idempotent: skips records already marked or already having a confirmed
    arrival at the resolved port.
    """
    now_dt = datetime.fromisoformat(now.replace("Z", "+00:00"))
    dark_cutoff = now_dt - timedelta(days=DARK_DAYS)
    pinged = {v.get("imo", "") for v in current_vessels if v.get("imo")}
    confirmed_keys = {
        (a["imo"], a["port"]) for a in existing_arrivals
        if a.get("status") != "probable"
    }

    new_rows = []
    for imo, record in vessel_db.items():
        in_transit = record.get("in_transit")
        if not in_transit:
            continue
        if record.get("probable_arrival"):
            continue
        if in_transit.get("is_ballast"):
            continue
        if not record.get("departed_au_since_arrival", True):
            continue
        if imo in pinged:
            continue
        last = in_transit.get("last_position_update")
        if not last:
            continue
        if datetime.fromisoformat(last.replace("Z", "+00:00")) >= dark_cutoff:
            continue
        lat, lon = in_transit.get("lat"), in_transit.get("lon")
        if lat is None or lon is None:
            continue

        port, dist = _resolve_probable_port(in_transit, lat, lon, ports)
        if port is None:
            continue
        port_name = port["name"]
        if (imo, port_name) in confirmed_keys:
            continue

        if dist > INNER_KM:
            speed = in_transit.get("speed", 99) or 0.0
            closing = speed < SLOW_KN
            if not closing:
                course = in_transit.get("course")
                if course is not None:
                    brg = bearing_deg(lat, lon, port["lat"], port["lon"])
                    closing = angular_diff(course, brg) <= HEADING_TOL
            if not closing:
                continue

        cargo = estimate_cargo(
            length=record.get("length", 0),
            beam=record.get("beam", 0),
            draught=in_transit.get("draught", 0),
            ship_type=record.get("ship_type", "product"),
        )
        new_rows.append({
            "imo": imo,
            "name": record.get("name", "Unknown"),
            "port": port_name,
            "timestamp": last,
            "ship_type": record.get("ship_type", "product"),
            "vessel_class": cargo["vessel_class"],
            "cargo_tonnes": cargo["cargo_tonnes"],
            "cargo_litres": cargo["cargo_litres"],
            "draught_missing": cargo["draught_missing"],
            "coastal": False,
            "status": "probable",
        })
        record["probable_arrival"] = {"port": port_name, "since": now}

    return new_rows
