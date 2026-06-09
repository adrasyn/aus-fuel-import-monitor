"""Vessel database management, keyed by IMO number."""

from datetime import datetime, timedelta, timezone
from pipeline.cargo import classify_vessel, TANKER_CLASSES
from pipeline.classification import classify_ship_type, is_lng_carrier, load_overrides
from pipeline.destinations import parse_destination
from pipeline.regions import classify_region, should_keep_vessel

STALENESS_DAYS = 14

# Window after which a silent vessel is assumed to have left AU_APPROACH,
# so its next reappearance is treated as a fresh international leg rather
# than a coastal continuation. Matches STALENESS_DAYS by design — if we'd
# have pruned the in_transit block by now, we assume a new trip is starting.
GAP_THRESHOLD_DAYS = 14

# Dynamic fields copied from a snapshot row into the in_transit block.
# Static fields (name, length, beam, ship_type, vessel_class, dwt) stay on
# the parent vessel record and must not be duplicated here.
_IN_TRANSIT_FIELDS = (
    "mmsi", "lat", "lon", "speed", "course", "draught",
    "destination", "destination_parsed", "region",
    "cargo_litres", "cargo_tonnes", "load_factor",
    "is_ballast", "draught_missing",
)


def build_in_transit(snapshot_row: dict, now: str) -> dict:
    """Build an in_transit block from a vessel's row in the latest snapshot."""
    in_transit = {field: snapshot_row.get(field) for field in _IN_TRANSIT_FIELDS}
    in_transit["last_position_update"] = now
    return in_transit


def _record_lost(record: dict, imo: str, reason: str, now: str, log: list | None) -> None:
    """Capture a snapshot of an in_transit record before it's cleared without
    a corresponding arrival. Drives `data/lost-vessels.json`, which exists so
    we can audit how often the en-route bar drains into nothing — silent
    undercount on the MTD imports figure.

    Reason codes:
      - "stale_prune_14d": last AIS ping is older than STALENESS_DAYS
      - "destination_disqualified": destination/region no longer parses to AU
      - "lng_excluded": vessel reclassified as LNG carrier (not in scope)
    """
    if log is None:
        return
    in_transit = record.get("in_transit") or {}
    log.append({
        "imo": imo,
        "name": record.get("name", "Unknown"),
        "ship_type": record.get("ship_type", "product"),
        "vessel_class": record.get("vessel_class"),
        "cargo_litres": in_transit.get("cargo_litres", 0),
        "cargo_tonnes": in_transit.get("cargo_tonnes", 0),
        "is_ballast": in_transit.get("is_ballast", False),
        "last_lat": in_transit.get("lat"),
        "last_lon": in_transit.get("lon"),
        "last_destination": in_transit.get("destination"),
        "last_destination_parsed": in_transit.get("destination_parsed"),
        "last_position_update": in_transit.get("last_position_update"),
        "cleared_at": now,
        "reason": reason,
    })


def update_vessel_db(db: dict, vessels: list[dict], new_arrivals: list[dict] | None = None, lost_log: list | None = None) -> dict:
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
            # Refresh ship_type from the current classifier output — lets
            # classifier changes or override-file edits propagate to records
            # that were first ingested under older rules.
            db[imo]["ship_type"] = vessel.get("ship_type", db[imo]["ship_type"])
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
                # New vessels have no prior AU arrival, so their next arrival
                # is a genuine import until proven otherwise.
                "departed_au_since_arrival": True,
            }

        # Rebuild in_transit from this fresh ping
        db[imo]["in_transit"] = build_in_transit(vessel, now=now)

    if new_arrivals:
        for arrival in new_arrivals:
            imo = arrival.get("imo", "")
            if imo in db:
                db[imo]["arrival_count"] += 1
                db[imo]["in_transit"] = None  # arrived → no longer in transit
                # Vessel is now parked in AU — must be observed offshore or go
                # silent > GAP_THRESHOLD_DAYS before we'll count it again.
                db[imo]["departed_au_since_arrival"] = False

    prune_stale_in_transit(db, now=now, lost_log=lost_log)

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


def revalidate_in_transit(db: dict, lost_log: list | None = None) -> int:
    """Re-apply current classification and retention rules to every
    in_transit block. Clears in_transit on records that no longer qualify;
    refreshes stored region, destination_parsed, and ship_type on records
    that still do.

    Re-running these here matters because each of them is a cached output
    of a function we may have fixed since the record was written:
    - destination_parsed (word-boundary bug once mis-mapped PORT EVERGLADES
      to "Gladstone")
    - ship_type (originally classified off AIS type codes, now off size +
      name + overrides — mis-tagged product tankers need to self-correct)
    - LNG exclusion (project scope excludes LNG; any LNG carrier that
      slipped in via an older filter gets dropped here)

    Returns the number of records whose in_transit was cleared.
    """
    overrides = load_overrides()
    now = datetime.now(timezone.utc).isoformat()
    cleared = 0
    for imo, record in db.items():
        in_transit = record.get("in_transit")
        if not in_transit:
            continue
        if is_lng_carrier(record.get("name")):
            _record_lost(record, imo, "lng_excluded", now, lost_log)
            record["in_transit"] = None
            cleared += 1
            continue
        lat = in_transit.get("lat", 0.0)
        lon = in_transit.get("lon", 0.0)
        raw_destination = in_transit.get("destination")
        region = classify_region(lat, lon)
        destination_parsed = parse_destination(raw_destination)
        in_transit["destination_parsed"] = destination_parsed
        if not should_keep_vessel(region, destination_parsed, raw_destination):
            _record_lost(record, imo, "destination_disqualified", now, lost_log)
            record["in_transit"] = None
            cleared += 1
            continue
        in_transit["region"] = region or ""
        # Refresh ship_type on the parent record (crude/product affects
        # en_route totals and the table's colour coding).
        record["ship_type"] = classify_ship_type(
            record.get("name"),
            record.get("vessel_class", ""),
            imo=imo,
            overrides=overrides,
        )
    return cleared


def apply_departed_au_rules(db: dict, current_vessels: list[dict], now: str) -> int:
    """Flip departed_au_since_arrival → True for vessels now inferred to be
    on a fresh international leg.

    Two triggers, both keyed on the current ping batch:
    - Region rule: vessel pings with region != "AU_APPROACH" — we've directly
      observed it offshore.
    - Gap rule: vessel pings now but last_seen was > GAP_THRESHOLD_DAYS ago —
      a long silence is evidence of a trip we missed, since an in-AU vessel
      with AIS on would have kept pinging.

    Must be called BEFORE detect_arrivals so that any arrival this run has the
    latest flag available for its coastal stamp. Idempotent: vessels already
    flagged True are left alone.

    Returns the number of records flipped this run.
    """
    now_dt = datetime.fromisoformat(now.replace("Z", "+00:00"))
    gap_cutoff = now_dt - timedelta(days=GAP_THRESHOLD_DAYS)
    pinged_regions: dict[str, str | None] = {
        v.get("imo", ""): v.get("region")
        for v in current_vessels
        if v.get("imo")
    }
    flipped = 0
    for imo, record in db.items():
        if record.get("departed_au_since_arrival", True):
            continue
        if imo not in pinged_regions:
            continue
        region = pinged_regions[imo]

        triggered = False
        if region is not None and region != "AU_APPROACH":
            triggered = True
        else:
            last_seen = record.get("last_seen")
            if last_seen:
                last_seen_dt = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
                if last_seen_dt < gap_cutoff:
                    triggered = True

        if triggered:
            record["departed_au_since_arrival"] = True
            flipped += 1
    return flipped


def migrate_departed_au_flag(db: dict) -> int:
    """Backfill departed_au_since_arrival on records that don't have it yet.

    Conservative policy: a vessel currently inside AU_APPROACH with one or more
    prior arrivals is assumed to be on a coastal leg (flag False) until we see
    it offshore again. Everything else defaults to True. Under-counts slightly
    (a genuine inbound vessel with a prior AU arrival will be flagged False
    until its next offshore ping flips it back) but that's preferable to the
    over-count we're fixing.

    Returns the number of records migrated.
    """
    count = 0
    for record in db.values():
        if "departed_au_since_arrival" in record:
            continue
        arrival_count = record.get("arrival_count", 0)
        in_transit = record.get("in_transit") or {}
        region = in_transit.get("region") if in_transit else None
        if arrival_count > 0 and region == "AU_APPROACH":
            record["departed_au_since_arrival"] = False
        else:
            record["departed_au_since_arrival"] = True
        count += 1
    return count


def prune_stale_in_transit(db: dict, now: str, lost_log: list | None = None) -> None:
    """Clear in_transit on any vessel last pinged > STALENESS_DAYS ago.

    Mutates db in place. No-op for records without an in_transit block.
    """
    cutoff = datetime.fromisoformat(now.replace("Z", "+00:00")) - timedelta(days=STALENESS_DAYS)
    for imo, record in db.items():
        in_transit = record.get("in_transit")
        if not in_transit:
            continue
        last = in_transit.get("last_position_update")
        if not last:
            continue
        last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
        if last_dt < cutoff:
            if record.get("probable_arrival"):
                # Already accounted as a probable arrival — finalize the trip:
                # keep the probable row, drop the marker (so a later reappearance
                # can't reverse it), and don't log it as lost.
                record["probable_arrival"] = None
            else:
                _record_lost(record, imo, "stale_prune_14d", now, lost_log)
            record["in_transit"] = None
