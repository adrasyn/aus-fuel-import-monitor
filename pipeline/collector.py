"""AISStream WebSocket collector for tanker vessels near Australia."""

import asyncio
import json
import os
import time
from datetime import datetime, timezone

import websockets

from pipeline.cargo import estimate_cargo
from pipeline.destinations import parse_destination
from pipeline.regions import (
    bounding_boxes_for_subscription,
    classify_region,
    should_keep_vessel,
)

AISSTREAM_URL = "wss://stream.aisstream.io/v0/stream"

# AIS ship type codes for tankers (excluding LNG/LPG)
TANKER_TYPE_CODES = set(range(80, 90))

CRUDE_CODES = {80, 81, 82, 83, 84}
PRODUCT_CODES = {85, 86, 87, 88, 89}


def classify_ship_type(ais_type: int) -> str:
    if ais_type in CRUDE_CODES:
        return "crude"
    return "product"


async def collect_vessels(api_key: str, duration_seconds: int = 1800) -> dict:
    vessels: dict[str, dict] = {}  # keyed by MMSI
    start_time = time.time()
    msg_count = 0
    type_counts: dict[str, int] = {}
    non_ais_samples: list[str] = []  # capture a few non-AIS messages for diagnosis

    subscription = {
        "APIKey": api_key,
        "BoundingBoxes": bounding_boxes_for_subscription(),
        "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
    }

    print(f"Connecting to AISStream, collecting for {duration_seconds}s...")

    try:
        async with websockets.connect(AISSTREAM_URL) as ws:
            await ws.send(json.dumps(subscription))

            while (time.time() - start_time) < duration_seconds:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
                except asyncio.TimeoutError:
                    continue

                msg = json.loads(raw)
                msg_type = msg.get("MessageType", "")
                type_counts[msg_type] = type_counts.get(msg_type, 0) + 1

                meta = msg.get("MetaData", {})
                mmsi = str(meta.get("MMSI", ""))

                if not mmsi:
                    # No MMSI → likely an AISStream control/error frame.
                    # Capture the first few for post-run diagnosis.
                    if len(non_ais_samples) < 5:
                        non_ais_samples.append(raw[:500])
                    continue

                msg_count += 1

                # Initialize vessel record if new
                if mmsi not in vessels:
                    vessels[mmsi] = {
                        "mmsi": mmsi,
                        "imo": "",
                        "name": meta.get("ShipName", "").strip(),
                        "ship_type": "product",
                        "ais_type_code": 0,
                        "lat": 0.0,
                        "lon": 0.0,
                        "speed": 0.0,
                        "course": 0.0,
                        "heading": 0.0,
                        "draught": 0.0,
                        "length": 0,
                        "beam": 0,
                        "destination": "",
                        "destination_parsed": None,
                        "region": "",
                        "last_update": "",
                    }

                vessel = vessels[mmsi]

                if msg_type == "PositionReport":
                    report = msg.get("Message", {}).get("PositionReport", {})
                    vessel["lat"] = meta.get("latitude", 0.0)
                    vessel["lon"] = meta.get("longitude", 0.0)
                    vessel["speed"] = report.get("Sog", 0.0)
                    vessel["course"] = report.get("Cog", 0.0)
                    vessel["heading"] = report.get("TrueHeading", 0.0)
                    vessel["last_update"] = meta.get("time_utc", "")

                elif msg_type == "ShipStaticData":
                    static = msg.get("Message", {}).get("ShipStaticData", {})
                    # Ship type is in the static data message, NOT in MetaData
                    ais_type = static.get("Type", 0)
                    vessel["ais_type_code"] = ais_type
                    vessel["ship_type"] = classify_ship_type(ais_type)
                    vessel["imo"] = str(static.get("ImoNumber", ""))
                    vessel["name"] = static.get("Name", vessel["name"]).strip()
                    vessel["draught"] = static.get("MaximumStaticDraught", 0.0)
                    vessel["destination"] = static.get("Destination", "").strip()
                    vessel["destination_parsed"] = parse_destination(vessel["destination"])

                    dimension = static.get("Dimension", {})
                    vessel["length"] = dimension.get("A", 0) + dimension.get("B", 0)
                    vessel["beam"] = dimension.get("C", 0) + dimension.get("D", 0)

    except Exception as e:
        print(f"Collection error: {e}")

    elapsed = time.time() - start_time
    print(f"  Received {msg_count} messages, {len(vessels)} unique vessels")
    if type_counts:
        print(f"  Message type breakdown: {type_counts}")
    print(f"  Elapsed: {elapsed:.0f}s, effective rate: {msg_count / elapsed if elapsed > 0 else 0:.1f} msg/s")
    if non_ais_samples:
        print(f"  Captured {len(non_ais_samples)} non-AIS messages (first {min(3, len(non_ais_samples))} shown):")
        for sample in non_ais_samples[:3]:
            print(f"    {sample}")

    # Post-process: filter to tankers only, add cargo estimates
    result_vessels = []
    for vessel in vessels.values():
        # Skip vessels with no position
        if vessel["lat"] == 0.0 and vessel["lon"] == 0.0:
            continue

        # Only keep tankers (type 80-89) — skip vessels where we never got static data
        if vessel["ais_type_code"] not in TANKER_TYPE_CODES:
            continue

        # Region-based retention: all tankers in AU_APPROACH; elsewhere
        # only vessels whose declared destination parses as Australian.
        region = classify_region(vessel["lat"], vessel["lon"])
        vessel["region"] = region or ""
        if not should_keep_vessel(region, vessel["destination_parsed"], vessel["destination"]):
            continue

        cargo = estimate_cargo(
            length=vessel["length"],
            beam=vessel["beam"],
            draught=vessel["draught"],
            ship_type=vessel["ship_type"],
        )
        vessel.update({
            "vessel_class": cargo["vessel_class"],
            "dwt": cargo["dwt"],
            "load_factor": cargo["load_factor"],
            "cargo_tonnes": cargo["cargo_tonnes"],
            "cargo_litres": cargo["cargo_litres"],
            "is_ballast": cargo["is_ballast"],
            "draught_missing": cargo["draught_missing"],
        })
        result_vessels.append(vessel)

    count = len(result_vessels)
    tanker_count = len([v for v in result_vessels if not v["is_ballast"]])
    print(f"  Filtered to {count} tanker vessels ({tanker_count} laden, {count - tanker_count} ballast)")

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "vessels": result_vessels,
    }


def run_collector(api_key: str, duration_seconds: int = 1800) -> dict:
    return asyncio.run(collect_vessels(api_key, duration_seconds))


if __name__ == "__main__":
    key = os.environ.get("AISSTREAM_API_KEY", "")
    if not key:
        print("Error: AISSTREAM_API_KEY environment variable not set")
        exit(1)
    snapshot = run_collector(key)
    print(json.dumps(snapshot, indent=2)[:2000])
