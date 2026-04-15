---
name: enrich-vessel-types
description: Use when the user suspects the dashboard's crude/product classifications are wrong and wants to enrich them against MarineTraffic. Reads the current in-transit roster, cross-references each IMO against marinetraffic.com (no login required), proposes entries for data/vessel-overrides.json, and commits after the user confirms.
---

# Enrich Vessel Types

## When to use

Invoke when any of these are true:
- The user eyeballed the fleet and says "that doesn't look right" (e.g. "why is this clearly-product tanker marked crude?").
- New vessels have appeared in the roster whose classification can't be verified by the heuristic (large IMOs we haven't seen before).
- A periodic accuracy check, e.g. once a month.

Do NOT invoke just because classifications look uncertain — the built-in heuristic in `pipeline/classification.py` (LNG filter → per-IMO override → operator-name hint → size-class default) already hits ~85-90% accuracy. This skill is for the last-mile enrichment.

## Prerequisites

- `data/vessels.json` exists (the vessel database with in-transit records).
- Internet access — we WebFetch against `https://www.marinetraffic.com/en/ais/details/ships/imo:<IMO>` which is publicly accessible.
- The user is present to confirm proposed override entries before they're committed.

## Workflow

### 1. Read the current state

Load `data/vessels.json` and build a list of in-transit vessels with their current classification:

```python
import json
with open("data/vessels.json", encoding="utf-8") as f:
    db = json.load(f)
candidates = [
    (imo, rec["name"], rec.get("vessel_class"), rec.get("ship_type"))
    for imo, rec in db.items()
    if rec.get("in_transit") and rec.get("name")
]
```

Load existing overrides if present (file is optional, absent by default):

```python
import os
overrides = {}
if os.path.exists("data/vessel-overrides.json"):
    with open("data/vessel-overrides.json", encoding="utf-8") as f:
        overrides = json.load(f)
```

Filter `candidates` to those not already in `overrides`. No point re-checking vessels the user has already locked in.

### 2. Look up each vessel on MarineTraffic

For each candidate IMO, fetch:

```
https://www.marinetraffic.com/en/ais/details/ships/imo:<IMO>
```

Use the WebFetch tool with a prompt like:

> "Extract the ship type from this page. The ship-type field appears under the main ship info block. Common values include 'Oil Products Tanker', 'Crude Oil Tanker', 'Chemical/Oil Products Tanker', 'LNG Tanker', 'LPG Tanker', 'Bulk Carrier', etc. Return just the type string, or 'UNKNOWN' if the page didn't load or no type is visible."

Rate-limit yourself — MarineTraffic will block aggressive scraping. One request per 2-3 seconds is a safe cadence. For the typical 10-20 vessel batch this is still under a minute total.

### 3. Map MarineTraffic types to our vocabulary

```
Oil Products Tanker          -> product
Chemical/Oil Products Tanker -> product
Chemical Tanker              -> product
Crude Oil Tanker             -> crude
Crude/Oil Products Tanker    -> crude     (ambiguous; err toward crude since those are typically Aframax+)
Shuttle Tanker               -> crude
LNG Tanker                   -> lng
Bunkering Tanker             -> product
LPG Tanker                   -> product   (LPG is in scope per project definition)
Bulk Carrier / General Cargo -> (not a tanker; record but investigate why it was in the roster)
```

Any value not in this table should be flagged to the user, not silently classified.

### 4. Detect mismatches

Compare MarineTraffic's mapped value against the vessel's current `ship_type` in `vessels.json`. Collect the mismatches as proposed overrides:

```python
proposals = {}  # imo -> mt_ship_type
for imo, name, vclass, current in candidates:
    # ... fetch + map ...
    if mt_mapped in ("crude", "product", "lng") and mt_mapped != current:
        proposals[imo] = mt_mapped
```

For `lng` matches on a vessel already in the roster: this means the LNG name-pattern filter missed it (name didn't contain METHANE/LNG/GAS CARRIER). Flag it separately — the `is_lng_carrier` name patterns may need extending rather than an override per ship.

### 5. Show the user the proposed diff

Before writing anything, print a summary:

```
Proposed overrides (N vessels):
  9698006  GARDEN STATE          currently crude -> product  (Oil Products Tanker)
  9783930  SOUTHERN LEADER       currently crude -> product  (Chemical/Oil Products Tanker)
  ...

LNG carriers to exclude from roster (name filter missed these):
  9876543  MYSTERY GAS SHIP      (LNG Tanker)  — consider extending _LNG_NAME_PATTERNS
```

Ask the user: "Proceed with these overrides?" Wait for confirmation.

### 6. Write and commit

Merge proposals into `data/vessel-overrides.json`:

```python
overrides.update(proposals)
with open("data/vessel-overrides.json", "w", encoding="utf-8") as f:
    json.dump(overrides, f, indent=2, sort_keys=True)
```

Run `revalidate_in_transit` locally against `data/vessels.json` so the newly-overridden classifications propagate, then recompute monthly + daily estimates:

```python
from datetime import datetime, timezone
from pipeline.vessels import revalidate_in_transit
from pipeline.orchestrator import update_monthly_estimates
from pipeline.daily_estimates import update_daily_estimates

revalidate_in_transit(db)  # loads the new overrides via load_overrides()
monthly = update_monthly_estimates(monthly, [], db)
daily = update_daily_estimates(daily, db, datetime.now(timezone.utc))
# save all three files
```

Commit with a message of the form:

```
data: enrich vessel-overrides from MarineTraffic (N entries)

Cross-referenced against marinetraffic.com. Bumped N classifications
to match MarineTraffic's IHS-sourced ship type. Current fleet re-
classified, monthly + daily en_route recomputed.
```

Push to main so the deploy fires.

## Caveats

- **MarineTraffic page structure can change.** If the WebFetch returns nothing useful, try the exact prompt above but inspect the raw page (curl). They occasionally relabel fields.
- **Rate limits.** If you hit a block (empty body, captcha page), wait several minutes before retrying. Consider reducing to 1 request per 5 seconds.
- **Terms of service.** MarineTraffic's ToS discourages automated scraping for commercial redistribution. For periodic manual enrichment (this skill's use case) it's typically fine, but don't wire this into a recurring CI job without re-checking.
- **IHS-adjacent but not IHS.** MarineTraffic enriches AIS with their own ship-type data, which often comes from IHS Ships Register. It's authoritative enough for our purposes (matches what the user sees when they check a ship manually) but isn't the raw IHS registry.

## What NOT to do

- Don't run this as part of the nightly pipeline. It's manual/ad-hoc by design — the nightly pipeline shouldn't depend on MarineTraffic's availability.
- Don't extend the LNG name patterns without discussing with the user first. LNG is a hard exclude; mis-adding a pattern could drop legitimate tankers (e.g. a crude tanker called "GAS LIGHT"). Better to catch them via overrides.
- Don't auto-commit. The user confirms first, always.
