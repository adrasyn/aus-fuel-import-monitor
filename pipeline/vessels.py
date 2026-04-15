"""Vessel database management, keyed by IMO number."""

from datetime import datetime, timedelta, timezone
from pipeline.cargo import classify_vessel, TANKER_CLASSES
from pipeline.destinations import parse_destination
from pipeline.regions import classify_region, should_keep_vessel

STALENESS_DAYS = 14

# Dynamic fields copied from a snapshot row into the in_transit block.
# Static fields (name, length, beam, ship_type, vessel_class, dwt) stay on
# the parent vessel record and must not be duplicated here.
_IN_TRANSIT_FIELDS = (
    "mmsi", "lat", "lon", "speed", "course", "heading", "draught",
    "destination", "destination_parsed", "region",
    "cargo_litres", "cargo_tonnes", "load_factor",
    "is_ballast", "draught_missing",
)


def build_in_transit(snapshot_row: dict, now: str) -> dict:
    """Build an in_transit block from a vessel's row in the latest snapshot."""
    in_transit = {field: snapshot_row.get(field) for field in _IN_TRANSIT_FIELDS}
    in_transit["last_position_update"] = now
    return in_transit


def update_vessel_db(db: dict, vessels: list[dict], new_arrivals: list[dict] | None = None) -> dict:
    now = datetime.now(timezone.utc).isoformat()

    pinged_imos = set()
    for vessel in vessels:
        imo = vessel.get("imo", "")
        if not imo:
            continue
        pinged_imos.add(imo)

        vessel_class = classify_vessel(vessel.get("length", 0), vessel.get("beam", 0))
        dwt = TANKER_CLASSES[vessel_class]["dwt"]

        if imo in db:
            db[imo]["last_seen"] = now
            db[imo]["name"] = vessel.get("name", db[imo]["name"])
        else:
            db[imo] = {
                "name": vessel.get("name", "Unknown"),
                "vessel_class": vessel_class,
                "dwt": dwt,
                "length": vessel.get("length", 0),
                "beam": vessel.get("beam", 0),
                "ship_type": vessel.get("ship_type", "product"),
                "first_seen": now,
                "last_seen": now,
                "arrival_count": 0,
            }

        # Rebuild in_transit from this fresh ping
        db[imo]["in_transit"] = build_in_transit(vessel, now=now)

    if new_arrivals:
        for arrival in new_arrivals:
            imo = arrival.get("imo", "")
            if imo in db:
                db[imo]["arrival_count"] += 1
                db[imo]["in_transit"] = None  # arrived → no longer in transit

    prune_stale_in_transit(db, now=now)

    return db


def migrate_missing_in_transit(db: dict, snapshot: dict) -> int:
    """Backfill in_transit on records that don't have it yet, using snapshot data.

    One-off migration to heal the schema gap between pre- and post-in-transit
    vessel records. For each record in db that has no in_transit key, looks up
    the vessel by IMO in snapshot["vessels"]; if found, builds in_transit using
    the snapshot's timestamp as last_position_update so staleness is honest.

    Idempotent: after every record has in_transit, becomes a no-op.
    Returns the number of records migrated.
    """
    snapshot_by_imo = {
        v.get("imo"): v
        for v in snapshot.get("vessels", [])
        if v.get("imo")
    }
    timestamp = snapshot.get("timestamp") or datetime.now(timezone.utc).isoformat()
    count = 0
    for imo, record in db.items():
        if "in_transit" in record:
            continue
        snap_row = snapshot_by_imo.get(imo)
        if not snap_row:
            continue
        record["in_transit"] = build_in_transit(snap_row, now=timestamp)
        count += 1
    return count


def revalidate_in_transit(db: dict) -> int:
    """Re-apply current region classification, destination parsing, and
    retention rule to every in_transit block. Clears in_transit on records
    that no longer qualify; refreshes stored region and destination_parsed
    on records that still do.

    Re-parsing the destination here matters: stored destination_parsed is
    a cached output of a function that's been fixed since (e.g. word-boundary
    bug that mis-mapped "PORT EVERGLADES" → "Gladstone"). Trusting the cache
    would let those vessels survive forever.

    Returns the number of records whose in_transit was cleared.
    """
    cleared = 0
    for record in db.values():
        in_transit = record.get("in_transit")
        if not in_transit:
            continue
        lat = in_transit.get("lat", 0.0)
        lon = in_transit.get("lon", 0.0)
        raw_destination = in_transit.get("destination")
        region = classify_region(lat, lon)
        destination_parsed = parse_destination(raw_destination)
        in_transit["destination_parsed"] = destination_parsed
        if not should_keep_vessel(region, destination_parsed, raw_destination):
            record["in_transit"] = None
            cleared += 1
            continue
        in_transit["region"] = region or ""
    return cleared


def prune_stale_in_transit(db: dict, now: str) -> None:
    """Clear in_transit on any vessel last pinged > STALENESS_DAYS ago.

    Mutates db in place. No-op for records without an in_transit block.
    """
    cutoff = datetime.fromisoformat(now.replace("Z", "+00:00")) - timedelta(days=STALENESS_DAYS)
    for record in db.values():
        in_transit = record.get("in_transit")
        if not in_transit:
            continue
        last = in_transit.get("last_position_update")
        if not last:
            continue
        last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
        if last_dt < cutoff:
            record["in_transit"] = None
