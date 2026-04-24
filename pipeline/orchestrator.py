"""Pipeline orchestrator — runs the full nightly data collection and processing."""

import json
import os
import sys
from datetime import datetime, timezone

from pipeline.collector import run_collector
from pipeline.arrivals import detect_arrivals, detect_silent_arrivals, load_ports
from pipeline.vessels import (
    update_vessel_db,
    migrate_missing_in_transit,
    migrate_departed_au_flag,
    revalidate_in_transit,
    apply_departed_au_rules,
)
from pipeline.daily_estimates import update_daily_estimates
from pipeline.petroleum_stats import download_latest_excel, build_imports_json

DATA_DIR = "data"
EXCEL_CACHE = "data/petroleum_stats_cache.xlsx"


def load_json(path: str, default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default


def save_json(path: str, data) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  Saved {path}")


COASTAL_HEURISTIC_WINDOW_DAYS = 14


def migrate_coastal_on_arrivals(arrivals: list[dict]) -> int:
    """Backfill the coastal flag on arrivals that don't have it yet.

    We have no AIS ping history to replay, so classify heuristically: an
    arrival is coastal if the same vessel's immediately prior arrival was at
    a DIFFERENT AU port within COASTAL_HEURISTIC_WINDOW_DAYS. International
    voyages are longer; intra-AU hops are typically <14 days apart.

    Idempotent: records that already have the field are left alone.
    Returns the number migrated.
    """
    from collections import defaultdict

    by_imo: dict[str, list[dict]] = defaultdict(list)
    for a in arrivals:
        imo = a.get("imo")
        if imo:
            by_imo[imo].append(a)

    migrated = 0
    for arrival_list in by_imo.values():
        arrival_list.sort(key=lambda x: x.get("timestamp", ""))
        for i, arrival in enumerate(arrival_list):
            if "coastal" in arrival:
                continue
            if i == 0:
                arrival["coastal"] = False
                migrated += 1
                continue
            prev = arrival_list[i - 1]
            if prev.get("port") == arrival.get("port"):
                # Same port — already deduped at detection time, but belt-and-
                # braces: not a coastal import signal.
                arrival["coastal"] = False
                migrated += 1
                continue
            try:
                t_prev = datetime.fromisoformat(prev["timestamp"].replace("Z", "+00:00"))
                t_cur = datetime.fromisoformat(arrival["timestamp"].replace("Z", "+00:00"))
            except (KeyError, ValueError):
                arrival["coastal"] = False
                migrated += 1
                continue
            gap_days = (t_cur - t_prev).days
            arrival["coastal"] = gap_days <= COASTAL_HEURISTIC_WINDOW_DAYS
            migrated += 1
    return migrated


def update_monthly_estimates(
    monthly: dict,
    new_arrivals: list[dict],
    vessel_db: dict,
    now: datetime | None = None,
) -> dict:
    if now is None:
        now = datetime.now(timezone.utc)
    month_key = now.strftime("%Y-%m")

    if month_key not in monthly.get("months", {}):
        monthly.setdefault("months", {})[month_key] = {
            "arrived_crude_litres": 0,
            "arrived_product_litres": 0,
            "arrived_crude_tonnes": 0,
            "arrived_product_tonnes": 0,
            "arrival_count": 0,
        }

    month = monthly["months"][month_key]

    for arrival in new_arrivals:
        # Coastal hops (e.g. Brisbane → Westernport) aren't new imports; the
        # cargo was counted on the original international leg.
        if arrival.get("coastal"):
            continue
        month["arrival_count"] += 1
        if arrival["ship_type"] == "crude":
            month["arrived_crude_litres"] += arrival["cargo_litres"]
            month["arrived_crude_tonnes"] += arrival["cargo_tonnes"]
        else:
            month["arrived_product_litres"] += arrival["cargo_litres"]
            month["arrived_product_tonnes"] += arrival["cargo_tonnes"]

    en_route_crude_litres = 0
    en_route_product_litres = 0
    for record in vessel_db.values():
        in_transit = record.get("in_transit")
        if not in_transit:
            continue
        if in_transit.get("is_ballast"):
            continue
        if not record.get("departed_au_since_arrival", True):
            continue
        if record.get("ship_type") == "crude":
            en_route_crude_litres += in_transit.get("cargo_litres", 0)
        else:
            en_route_product_litres += in_transit.get("cargo_litres", 0)

    month["en_route_crude_litres"] = en_route_crude_litres
    month["en_route_product_litres"] = en_route_product_litres
    month["last_updated"] = now.isoformat()

    return monthly


def run_pipeline(api_key: str, duration_seconds: int = 1800) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)

    # One `now` per pipeline run — ensures monthly and daily estimates agree
    # on the date boundary even if the run straddles UTC midnight.
    now = datetime.now(timezone.utc)

    previous_snapshot = load_json(f"{DATA_DIR}/snapshot.json", {"vessels": []})
    arrivals_data = load_json(f"{DATA_DIR}/arrivals.json", {"arrivals": []})
    vessel_db = load_json(f"{DATA_DIR}/vessels.json", {})
    monthly = load_json(f"{DATA_DIR}/monthly-estimates.json", {"months": {}})
    daily = load_json(f"{DATA_DIR}/daily-estimates.json", {"days": {}})
    ports = load_ports(f"{DATA_DIR}/ports.json")

    migrated = migrate_missing_in_transit(vessel_db, previous_snapshot)
    departed_migrated = migrate_departed_au_flag(vessel_db)
    arrivals_migrated = migrate_coastal_on_arrivals(arrivals_data.get("arrivals", []))
    revalidated = revalidate_in_transit(vessel_db)
    if migrated:
        print(f"Migration: backfilled in_transit on {migrated} record(s) from previous snapshot")
    if departed_migrated:
        print(f"Migration: backfilled departed_au_since_arrival on {departed_migrated} record(s)")
    if arrivals_migrated:
        print(f"Migration: backfilled coastal flag on {arrivals_migrated} arrival record(s)")
    if revalidated:
        print(f"Revalidation: cleared in_transit on {revalidated} record(s) (no longer pass current retention rule)")
    if migrated or departed_migrated or revalidated:
        save_json(f"{DATA_DIR}/vessels.json", vessel_db)
    if arrivals_migrated:
        save_json(f"{DATA_DIR}/arrivals.json", arrivals_data)

    print("Step 1: Collecting from AISStream...")
    current_snapshot = run_collector(api_key, duration_seconds)
    if not current_snapshot.get("vessels"):
        print("  WARNING: 0 tankers received. Preserving last-good data; skipping downstream steps.")
        print("Pipeline complete (no-op run).")
        return
    save_json(f"{DATA_DIR}/snapshot.json", current_snapshot)

    flipped = apply_departed_au_rules(
        vessel_db, current_snapshot["vessels"], now=now.isoformat()
    )
    if flipped:
        print(f"  Flipped departed_au_since_arrival=True on {flipped} vessel(s) after fresh ping (offshore or gap > threshold)")

    print("Step 2a: Sweeping roster for silent arrivals...")
    silent_arrivals = detect_silent_arrivals(
        vessel_db, ports, arrivals_data["arrivals"]
    )
    arrivals_data["arrivals"].extend(silent_arrivals)
    if silent_arrivals:
        print(f"  {len(silent_arrivals)} silent arrival(s) caught from stale in-transit positions")

    print("Step 2: Detecting port arrivals...")
    new_arrivals = detect_arrivals(
        current_snapshot, vessel_db, ports, arrivals_data["arrivals"]
    )
    arrivals_data["arrivals"].extend(new_arrivals)
    save_json(f"{DATA_DIR}/arrivals.json", arrivals_data)
    print(f"  {len(new_arrivals)} new arrivals detected")

    print("Step 3: Updating vessel database...")
    vessel_db = update_vessel_db(vessel_db, current_snapshot["vessels"], new_arrivals)
    save_json(f"{DATA_DIR}/vessels.json", vessel_db)
    print(f"  {len(vessel_db)} vessels in database")

    print("Step 4: Updating monthly estimates...")
    monthly = update_monthly_estimates(monthly, new_arrivals, vessel_db, now=now)
    save_json(f"{DATA_DIR}/monthly-estimates.json", monthly)

    print("Step 5: Updating daily estimates...")
    daily = update_daily_estimates(daily, vessel_db, now)
    save_json(f"{DATA_DIR}/daily-estimates.json", daily)

    print("Step 6: Checking petroleum statistics...")
    try:
        download_latest_excel(EXCEL_CACHE)
        imports_data = build_imports_json(EXCEL_CACHE)
        save_json(f"{DATA_DIR}/imports.json", imports_data)
        print("  Updated imports data")
    except Exception as e:
        print(f"  Skipped petroleum stats update: {e}")

    print("Pipeline complete.")


if __name__ == "__main__":
    key = os.environ.get("AISSTREAM_API_KEY", "")
    if not key:
        print("Error: AISSTREAM_API_KEY environment variable not set")
        sys.exit(1)

    duration = int(os.environ.get("COLLECTION_DURATION", "1800"))
    run_pipeline(key, duration)
