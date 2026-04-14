# Workflow Split + Revalidate + Chart + Cron Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship four bundled follow-ups: (a) split the CI workflow so code pushes deploy in ~1 min without running the AIS pipeline, (b) shift the cron to 3am UK, (c) add a `revalidate_in_transit` pass that self-heals stale region classifications (fixes Indonesia ships), (d) hide the pipeline's starting incomplete month on the historical chart.

**Architecture:** Two independent workflow files with aligned concurrency groups. A new pure-Python helper `revalidate_in_transit(db)` called by the orchestrator on every run. A small chart-filter rule that drops the earliest AIS-estimate month when it equals the current month, plus a conditional legend entry.

**Tech Stack:** GitHub Actions YAML, Python 3.12 + pytest, Next.js + TypeScript + Tailwind, recharts.

---

## File Structure

- **Modify** `.github/workflows/nightly-update.yml` — strip Node/build/upload/deploy steps; change cron to `0 2 * * *`.
- **Create** `.github/workflows/deploy.yml` — push- and dispatch-triggered build + GH Pages deploy.
- **Modify** `pipeline/vessels.py` — add `revalidate_in_transit()`.
- **Modify** `pipeline/tests/test_vessels.py` — tests for `revalidate_in_transit`.
- **Modify** `pipeline/orchestrator.py` — call `revalidate_in_transit` after `migrate_missing_in_transit`.
- **Modify** `src/components/HistoricalChart.tsx` — hide starting month; conditional dashed legend.

---

## Task 1: Add `revalidate_in_transit` to vessels.py

**Files:**
- Modify: `pipeline/vessels.py`
- Modify: `pipeline/tests/test_vessels.py`

### Step 1: Write failing tests

Append to `pipeline/tests/test_vessels.py`:

```python
# ---------- revalidate_in_transit ----------
from pipeline.vessels import revalidate_in_transit


def _record_with_in_transit(lat: float, lon: float, destination_parsed, region: str = "STALE") -> dict:
    return {
        "name": "Test Tanker", "vessel_class": "Aframax", "dwt": 100000,
        "length": 245, "beam": 44, "ship_type": "crude",
        "first_seen": "2026-04-13T00:00:00Z",
        "last_seen": "2026-04-14T12:00:00Z",
        "arrival_count": 0,
        "in_transit": {
            "mmsi": "636000000",
            "lat": lat, "lon": lon,
            "speed": 12.0, "course": 180.0, "heading": 180.0, "draught": 14.0,
            "destination": "", "destination_parsed": destination_parsed,
            "region": region,
            "cargo_litres": 80_000_000, "cargo_tonnes": 70_000,
            "load_factor": 0.9, "is_ballast": False, "draught_missing": False,
            "last_position_update": "2026-04-14T12:00:00Z",
        },
    }


def test_revalidate_clears_java_sea_record_with_no_au_destination():
    # Java Sea coordinates, no AU destination — should be dropped under current rules.
    # Simulates the Indonesia bug: data from an era where the record was tagged
    # AU_APPROACH, now reclassifies as JAVA_SEA which requires AU destination.
    db = {
        "9000001": _record_with_in_transit(-6.85, 112.44, destination_parsed=None, region="AU_APPROACH"),
    }
    cleared = revalidate_in_transit(db)
    assert cleared == 1
    assert db["9000001"]["in_transit"] is None


def test_revalidate_keeps_au_approach_record_without_destination():
    # Deep inside AU_APPROACH with no destination is still valid — AU_APPROACH
    # keeps unconditionally.
    db = {
        "9000002": _record_with_in_transit(-32.0, 115.0, destination_parsed=None, region="AU_APPROACH"),
    }
    cleared = revalidate_in_transit(db)
    assert cleared == 0
    assert db["9000002"]["in_transit"] is not None


def test_revalidate_updates_stored_region_to_current_classification():
    # A record previously stored as AU_APPROACH but whose coordinates now
    # classify as JAVA_SEA — retention still passes (it has an AU destination)
    # but the stored region should be refreshed to JAVA_SEA.
    db = {
        "9000003": _record_with_in_transit(-6.85, 112.44, destination_parsed="Fremantle", region="AU_APPROACH"),
    }
    cleared = revalidate_in_transit(db)
    assert cleared == 0
    assert db["9000003"]["in_transit"]["region"] == "JAVA_SEA"


def test_revalidate_skips_records_without_in_transit():
    db = {
        "9000004": {
            "name": "Arrived Tanker", "vessel_class": "Aframax", "dwt": 100000,
            "length": 245, "beam": 44, "ship_type": "crude",
            "first_seen": "2026-04-01T00:00:00Z",
            "last_seen": "2026-04-13T00:00:00Z",
            "arrival_count": 1,
            # no in_transit key
        },
        "9000005": {
            "name": "Arrived Tanker 2", "vessel_class": "Aframax", "dwt": 100000,
            "length": 245, "beam": 44, "ship_type": "crude",
            "first_seen": "2026-04-01T00:00:00Z",
            "last_seen": "2026-04-13T00:00:00Z",
            "arrival_count": 1,
            "in_transit": None,  # explicit None
        },
    }
    cleared = revalidate_in_transit(db)
    assert cleared == 0
    assert "in_transit" not in db["9000004"]
    assert db["9000005"]["in_transit"] is None


def test_revalidate_multiple_records_mixed():
    db = {
        "9000001": _record_with_in_transit(-6.85, 112.44, destination_parsed=None),       # Java Sea, no AU dest → clear
        "9000002": _record_with_in_transit(-32.0, 115.0, destination_parsed=None),        # AU_APPROACH → keep
        "9000003": _record_with_in_transit(-6.85, 112.44, destination_parsed="Fremantle"), # Java Sea with AU dest → keep (region updated)
        "9000004": _record_with_in_transit(0.0, -30.0, destination_parsed=None),           # mid-Atlantic → classify_region returns None → clear
    }
    cleared = revalidate_in_transit(db)
    assert cleared == 2
    assert db["9000001"]["in_transit"] is None
    assert db["9000002"]["in_transit"] is not None
    assert db["9000003"]["in_transit"]["region"] == "JAVA_SEA"
    assert db["9000004"]["in_transit"] is None
```

### Step 2: Run tests, verify they fail

Run: `python -m pytest pipeline/tests/test_vessels.py -v`
Expected: `ImportError: cannot import name 'revalidate_in_transit' from 'pipeline.vessels'`.

### Step 3: Implement `revalidate_in_transit`

At the top of `pipeline/vessels.py`, add the import (alongside the existing `cargo` import):

```python
from pipeline.cargo import classify_vessel, TANKER_CLASSES
from pipeline.regions import classify_region, should_keep_vessel
```

Append the function (after `prune_stale_in_transit`, at the bottom):

```python
def revalidate_in_transit(db: dict) -> int:
    """Re-apply current region classification and retention rule to every
    in_transit block. Clears in_transit on records that no longer qualify,
    and updates the stored region on records that still do.

    Returns the number of records whose in_transit was cleared.
    """
    cleared = 0
    for record in db.values():
        in_transit = record.get("in_transit")
        if not in_transit:
            continue
        lat = in_transit.get("lat", 0.0)
        lon = in_transit.get("lon", 0.0)
        destination_parsed = in_transit.get("destination_parsed")
        region = classify_region(lat, lon)
        if not should_keep_vessel(region, destination_parsed):
            record["in_transit"] = None
            cleared += 1
            continue
        in_transit["region"] = region or ""
    return cleared
```

### Step 4: Run tests, verify pass

Run: `python -m pytest pipeline/tests/test_vessels.py -v`
Expected: 23 passed (18 pre-existing on this branch + 5 new).

### Step 5: Run full suite

Run: `python -m pytest pipeline/tests/ -v`
Expected: 115 passed (110 baseline + 5 new).

### Step 6: Commit

```bash
git add pipeline/vessels.py pipeline/tests/test_vessels.py
git commit -m "$(cat <<'EOF'
feat(vessels): add revalidate_in_transit for self-healing classifications

Re-applies classify_region + should_keep_vessel to every stored
in_transit block. Clears records that no longer pass the retention
rule (e.g. the Indonesian ships carrying a stale AU_APPROACH region
that now classify as JAVA_SEA with no AU destination), and refreshes
the stored region on records that still qualify.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Call `revalidate_in_transit` from the orchestrator

**Files:**
- Modify: `pipeline/orchestrator.py`

### Step 1: Add the import

In `pipeline/orchestrator.py`, update the existing vessels import:

```python
from pipeline.vessels import update_vessel_db, migrate_missing_in_transit
```

to:

```python
from pipeline.vessels import update_vessel_db, migrate_missing_in_transit, revalidate_in_transit
```

### Step 2: Call it right after migration

Find the migration block in `run_pipeline`:

```python
    migrated = migrate_missing_in_transit(vessel_db, previous_snapshot)
    if migrated:
        print(f"Migration: backfilled in_transit on {migrated} record(s) from previous snapshot")
        save_json(f"{DATA_DIR}/vessels.json", vessel_db)
```

Replace with:

```python
    migrated = migrate_missing_in_transit(vessel_db, previous_snapshot)
    revalidated = revalidate_in_transit(vessel_db)
    if migrated:
        print(f"Migration: backfilled in_transit on {migrated} record(s) from previous snapshot")
    if revalidated:
        print(f"Revalidation: cleared in_transit on {revalidated} record(s) (no longer pass current retention rule)")
    if migrated or revalidated:
        save_json(f"{DATA_DIR}/vessels.json", vessel_db)
```

### Step 3: Verify tests still pass

Run: `python -m pytest pipeline/tests/ -v`
Expected: 115 passed (no new tests; revalidation is called but no mocks needed).

### Step 4: Smoke-import

Run: `python -c "from pipeline.orchestrator import run_pipeline; from pipeline.vessels import revalidate_in_transit; print('ok')"`
Expected: `ok`.

### Step 5: Commit

```bash
git add pipeline/orchestrator.py
git commit -m "$(cat <<'EOF'
feat(orchestrator): call revalidate_in_transit after migration each run

Runs before collection so it takes effect even on 0-message runs that
short-circuit before update_vessel_db. Combined with migration, this
self-heals any record whose stored region/retention state has drifted
from current rules.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Hide pipeline's starting (incomplete) month on the historical chart

**Files:**
- Modify: `src/components/HistoricalChart.tsx`

### Step 1: Add the filter + conditional legend

In `src/components/HistoricalChart.tsx`, find the block that builds AIS-estimate rows:

```tsx
  // AIS estimate months
  const estimateMonths = Object.entries(monthlyEstimates.months)
    .filter(([month]) => month > lastGovtMonth)
    .sort(([a], [b]) => a.localeCompare(b));

  const now = new Date();
  const currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;

  for (const [month, est] of estimateMonths) {
    const isCurrent = month === currentMonth;
    const crudeMl = (est.arrived_crude_litres + (isCurrent ? est.en_route_crude_litres : 0)) / 1_000_000;
    const productMl = (est.arrived_product_litres + (isCurrent ? est.en_route_product_litres : 0)) / 1_000_000;

    chartData.push({
      month,
      crude: Math.round(crudeMl),
      gasoline: 0,
      diesel: Math.round(productMl * 0.5),
      jet_fuel: Math.round(productMl * 0.25),
      fuel_oil: Math.round(productMl * 0.15),
      lpg: Math.round(productMl * 0.1),
      source: isCurrent ? "current_month" : "ais_estimate",
    });
  }
```

Replace with:

```tsx
  // AIS estimate months
  const estimateMonths = Object.entries(monthlyEstimates.months)
    .filter(([month]) => month > lastGovtMonth)
    .sort(([a], [b]) => a.localeCompare(b));

  const now = new Date();
  const currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;

  // Hide the pipeline's starting (incomplete) month: if the earliest AIS-estimate
  // month IS the current month, we have no complete historical data for it, just
  // a partial collection since project start. Skip it until the next month begins.
  const earliestEstimateMonth = estimateMonths.length > 0 ? estimateMonths[0][0] : null;
  const hideStartingMonth = earliestEstimateMonth === currentMonth;

  for (const [month, est] of estimateMonths) {
    if (hideStartingMonth && month === currentMonth) {
      continue;
    }
    const isCurrent = month === currentMonth;
    const crudeMl = (est.arrived_crude_litres + (isCurrent ? est.en_route_crude_litres : 0)) / 1_000_000;
    const productMl = (est.arrived_product_litres + (isCurrent ? est.en_route_product_litres : 0)) / 1_000_000;

    chartData.push({
      month,
      crude: Math.round(crudeMl),
      gasoline: 0,
      diesel: Math.round(productMl * 0.5),
      jet_fuel: Math.round(productMl * 0.25),
      fuel_oil: Math.round(productMl * 0.15),
      lpg: Math.round(productMl * 0.1),
      source: isCurrent ? "current_month" : "ais_estimate",
    });
  }
```

### Step 2: Make the "dashed = current month" legend entry conditional

Find the legend block:

```tsx
      <div className="flex flex-wrap gap-4 mt-2 text-[9px] text-label-light">
        <span><span className="inline-block w-3 h-3 bg-border-heavy mr-1 align-middle" /> Solid = government data</span>
        <span><span className="inline-block w-3 h-3 bg-border-heavy/40 mr-1 align-middle" /> Faded = AIS estimate (provisional)</span>
        <span><span className="inline-block w-3 h-3 bg-border-heavy/40 mr-1 align-middle border border-dashed border-border-heavy" /> Dashed = current month (to date)</span>
      </div>
```

Replace with:

```tsx
      <div className="flex flex-wrap gap-4 mt-2 text-[9px] text-label-light">
        <span><span className="inline-block w-3 h-3 bg-border-heavy mr-1 align-middle" /> Solid = government data</span>
        <span><span className="inline-block w-3 h-3 bg-border-heavy/40 mr-1 align-middle" /> Faded = AIS estimate (provisional)</span>
        {chartData.some((r) => r.source === "current_month") && (
          <span><span className="inline-block w-3 h-3 bg-border-heavy/40 mr-1 align-middle border border-dashed border-border-heavy" /> Dashed = current month (to date)</span>
        )}
      </div>
```

### Step 3: Build to verify

Run: `npm run build`
Expected: clean build.

### Step 4: Commit

```bash
git add src/components/HistoricalChart.tsx
git commit -m "$(cat <<'EOF'
feat(chart): hide pipeline's starting (incomplete) month

If the earliest AIS-estimate month equals the current month, the
pipeline started mid-month and has only partial data — don't plot a
misleading tiny bar for it. Rule self-disables once the next calendar
month starts. The dashed-legend entry becomes conditional so it only
appears when there's actually a dashed bar to explain.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Split the workflow and change cron to 3am UK

**Files:**
- Modify: `.github/workflows/nightly-update.yml`
- Create: `.github/workflows/deploy.yml`

### Step 1: Strip deploy steps from `nightly-update.yml` and change cron

Replace the entire contents of `.github/workflows/nightly-update.yml` with:

```yaml
name: Nightly Data Update

on:
  schedule:
    # 02:00 UTC = 03:00 BST (currently) / 02:00 GMT (in winter)
    - cron: "0 2 * * *"
  workflow_dispatch: # Allow manual trigger

permissions:
  contents: write

jobs:
  collect:
    runs-on: ubuntu-latest
    timeout-minutes: 45

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"
          cache-dependency-path: "pipeline/requirements.txt"

      - name: Install Python dependencies
        run: pip install -r pipeline/requirements.txt

      - name: Run data collection pipeline
        env:
          AISSTREAM_API_KEY: ${{ secrets.AISSTREAM_API_KEY }}
          COLLECTION_DURATION: "1800"
        run: python -m pipeline.orchestrator

      - name: Commit updated data
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/
          if git diff --staged --quiet; then
            echo "No data changes to commit"
            exit 0
          fi
          git commit -m "data: nightly update $(date -u +%Y-%m-%d)"
          git pull --rebase origin main
          git push
```

Key changes from the existing file:
- Job renamed `collect-and-deploy` → `collect`.
- Removed `pages: write` and `id-token: write` permissions.
- Removed `concurrency: group: pages` (no longer deploys).
- Removed the Node setup, dependency install, build, upload-pages-artifact, and deploy-pages steps.
- Changed cron from `"0 16 * * *"` to `"0 2 * * *"`.
- Workflow `name` shortened to `Nightly Data Update`.

### Step 2: Create the deploy workflow

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to GitHub Pages

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: "pages"
  cancel-in-progress: false

jobs:
  deploy:
    runs-on: ubuntu-latest
    timeout-minutes: 10

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"

      - name: Install Node dependencies
        run: npm ci

      - name: Build Next.js static site
        run: npm run build

      - name: Upload Pages artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: out

      - name: Deploy to GitHub Pages
        uses: actions/deploy-pages@v4
```

### Step 3: Validate both YAML files parse

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/nightly-update.yml')); yaml.safe_load(open('.github/workflows/deploy.yml')); print('both parse ok')"`
Expected: `both parse ok`.

(If `yaml` isn't installed, try `python -c "import json; json.loads(...)"` won't work for YAML — alternative: `gh workflow list` after push will fail fast on malformed YAML.)

### Step 4: Commit

```bash
git add .github/workflows/nightly-update.yml .github/workflows/deploy.yml
git commit -m "$(cat <<'EOF'
feat(ci): split pipeline + deploy workflows, shift cron to 3am UK

nightly-update.yml: data collection only, triggered by cron + manual
dispatch. Its data commit pushes to main, triggering deploy.yml.

deploy.yml: push-triggered build + GH Pages deploy. Runs in ~1-2 min
so code pushes no longer wait on a 30-min AIS collection.

Cron moved from 16:00 UTC to 02:00 UTC — that's 03:00 BST in summer
and 02:00 GMT in winter. Seasonal drift is unavoidable without
workarounds; 02:00 UTC matches "3am UK" right now.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review Notes

**Spec coverage:**
- §1 Split workflows — Task 4 covers both files + concurrency + permissions + cron change.
- §2 Cron — Task 4, the `0 2 * * *` line.
- §3 Revalidation — Tasks 1 (function + tests) and 2 (orchestrator wiring).
- §4 Chart hide starting month + conditional legend — Task 3.

**Placeholder scan:** no TBDs; every step has full code or full command.

**Type consistency:**
- `revalidate_in_transit(db: dict) -> int` — same signature in Tasks 1 and 2.
- JSON field names match across the Python test fixtures and `revalidate_in_transit` reads (`lat`, `lon`, `destination_parsed`, `region`, `in_transit`, `is_ballast` etc.) — lifted verbatim from existing code.
- Workflow YAML: `actions/checkout@v4`, `actions/setup-python@v5`, `actions/setup-node@v4`, `actions/upload-pages-artifact@v3`, `actions/deploy-pages@v4` — versions match the existing workflow verbatim where reused.
