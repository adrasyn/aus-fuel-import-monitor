"""Pipeline orchestrator — runs the full nightly data collection and processing."""

import json
import os
import sys
from datetime import datetime, timezone

from pipeline.collector import run_collector
from pipeline.arrivals import detect_arrivals, load_ports
from pipeline.vessels import update_vessel_db
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


def update_monthly_estimates(monthly: dict, new_arrivals: list[dict], vessel_db: dict) -> dict:
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

    arrivals_data = load_json(f"{DATA_DIR}/arrivals.json", {"arrivals": []})
    vessel_db = load_json(f"{DATA_DIR}/vessels.json", {})
    monthly = load_json(f"{DATA_DIR}/monthly-estimates.json", {"months": {}})
    ports = load_ports(f"{DATA_DIR}/ports.json")

    print("Step 1: Collecting from AISStream...")
    current_snapshot = run_collector(api_key, duration_seconds)
    save_json(f"{DATA_DIR}/snapshot.json", current_snapshot)

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
    monthly = update_monthly_estimates(monthly, new_arrivals, vessel_db)
    save_json(f"{DATA_DIR}/monthly-estimates.json", monthly)

    print("Step 5: Checking petroleum statistics...")
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
