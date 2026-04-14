# Daily En-Route Chart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a stacked-area chart below the monthly import chart showing crude + product volume in transit to Australia for each of the last 30 calendar days, sourced from the in-transit roster once per pipeline run.

**Architecture:** New pure-Python helper `pipeline/daily_estimates.py` sums today's en-route cargo from the roster's `in_transit` records (skipping ballast + arrived), writes to `data/daily-estimates.json` keyed by UTC date. Orchestrator wires it in as a new step. Frontend extends `DashboardData` with the daily series and renders a Recharts `AreaChart` that maps a 30-day window onto the data, showing gaps for missing days.

**Tech Stack:** Python 3.12, pytest, Next.js 14 + TypeScript + Tailwind, recharts.

---

## File Structure

- **Create** `pipeline/daily_estimates.py` — `update_daily_estimates(daily, vessel_db, now)`
- **Create** `pipeline/tests/test_daily_estimates.py` — unit tests
- **Modify** `pipeline/orchestrator.py` — load + update + save `daily-estimates.json` as a new Step 5 between monthly estimates and petroleum stats
- **Modify** `src/lib/types.ts` — `DailyEstimate`, `DailyEstimates`, extend `DashboardData`
- **Modify** `src/lib/data.ts` — read `daily-estimates.json`, include on the returned object
- **Create** `src/components/DailyEnRouteChart.tsx` — the chart component
- **Modify** `src/app/page.tsx` — mount the chart below the existing monthly chart

---

## Task 1: Create `pipeline/daily_estimates.py` with `update_daily_estimates`

**Files:**
- Create: `pipeline/daily_estimates.py`
- Create: `pipeline/tests/test_daily_estimates.py`

### Step 1: Write failing tests

Create `pipeline/tests/test_daily_estimates.py`:

```python
"""Tests for pipeline.daily_estimates."""

from datetime import datetime, timezone

from pipeline.daily_estimates import update_daily_estimates


def _in_transit(cargo_litres: int, is_ballast: bool = False) -> dict:
    return {
        "mmsi": "636000000", "lat": -25.0, "lon": 130.0,
        "speed": 12.0, "course": 180.0, "heading": 180.0, "draught": 14.0,
        "destination": "AU FRE", "destination_parsed": "Fremantle",
        "region": "AU_APPROACH",
        "cargo_litres": cargo_litres, "cargo_tonnes": 0,
        "load_factor": 0.9, "is_ballast": is_ballast, "draught_missing": False,
        "last_position_update": "2026-04-14T12:00:00Z",
    }


def _vessel_record(ship_type: str, in_transit: dict | None) -> dict:
    return {
        "name": "Test Tanker", "vessel_class": "Aframax", "dwt": 100000,
        "length": 245, "beam": 44, "ship_type": ship_type,
        "first_seen": "2026-04-01T00:00:00Z",
        "last_seen": "2026-04-14T12:00:00Z",
        "arrival_count": 0,
        "in_transit": in_transit,
    }


def test_update_daily_estimates_sums_laden_crude_and_product():
    daily = {"days": {}}
    vessel_db = {
        "9000001": _vessel_record("crude", _in_transit(320_000_000)),
        "9000002": _vessel_record("product", _in_transit(60_000_000)),
    }
    now = datetime(2026, 4, 14, 12, 30, tzinfo=timezone.utc)
    updated = update_daily_estimates(daily, vessel_db, now)

    assert "2026-04-14" in updated["days"]
    entry = updated["days"]["2026-04-14"]
    assert entry["en_route_crude_litres"] == 320_000_000
    assert entry["en_route_product_litres"] == 60_000_000
    assert entry["captured_at"] == "2026-04-14T12:30:00+00:00"


def test_update_daily_estimates_skips_ballast():
    daily = {"days": {}}
    vessel_db = {
        "9000001": _vessel_record("crude", _in_transit(320_000_000)),
        "9000002": _vessel_record("crude", _in_transit(0, is_ballast=True)),
    }
    now = datetime(2026, 4, 14, 12, 30, tzinfo=timezone.utc)
    updated = update_daily_estimates(daily, vessel_db, now)

    assert updated["days"]["2026-04-14"]["en_route_crude_litres"] == 320_000_000


def test_update_daily_estimates_skips_arrived_records():
    daily = {"days": {}}
    vessel_db = {
        "9000001": _vessel_record("crude", _in_transit(320_000_000)),
        # Arrived — in_transit is None — must not contribute
        "9000002": _vessel_record("crude", None),
    }
    now = datetime(2026, 4, 14, 12, 30, tzinfo=timezone.utc)
    updated = update_daily_estimates(daily, vessel_db, now)

    assert updated["days"]["2026-04-14"]["en_route_crude_litres"] == 320_000_000


def test_update_daily_estimates_same_day_rerun_overwrites():
    daily = {
        "days": {
            "2026-04-14": {
                "en_route_crude_litres": 1,
                "en_route_product_litres": 1,
                "captured_at": "2026-04-14T01:00:00+00:00",
            }
        }
    }
    vessel_db = {
        "9000001": _vessel_record("crude", _in_transit(500_000_000)),
    }
    now = datetime(2026, 4, 14, 23, 30, tzinfo=timezone.utc)
    updated = update_daily_estimates(daily, vessel_db, now)

    entry = updated["days"]["2026-04-14"]
    assert entry["en_route_crude_litres"] == 500_000_000
    assert entry["en_route_product_litres"] == 0
    assert entry["captured_at"] == "2026-04-14T23:30:00+00:00"
    assert len(updated["days"]) == 1


def test_update_daily_estimates_preserves_prior_days():
    daily = {
        "days": {
            "2026-04-13": {
                "en_route_crude_litres": 100_000_000,
                "en_route_product_litres": 50_000_000,
                "captured_at": "2026-04-13T12:00:00+00:00",
            }
        }
    }
    vessel_db = {
        "9000001": _vessel_record("crude", _in_transit(200_000_000)),
    }
    now = datetime(2026, 4, 14, 12, 0, tzinfo=timezone.utc)
    updated = update_daily_estimates(daily, vessel_db, now)

    # Prior day untouched
    assert updated["days"]["2026-04-13"]["en_route_crude_litres"] == 100_000_000
    # Today added
    assert updated["days"]["2026-04-14"]["en_route_crude_litres"] == 200_000_000
    assert len(updated["days"]) == 2
```

### Step 2: Run tests, verify they fail

Run: `python -m pytest pipeline/tests/test_daily_estimates.py -v`
Expected: `ModuleNotFoundError: No module named 'pipeline.daily_estimates'`.

### Step 3: Implement `update_daily_estimates`

Create `pipeline/daily_estimates.py`:

```python
"""Daily en-route volume aggregation from the in-transit roster."""

from __future__ import annotations

from datetime import datetime


def update_daily_estimates(daily: dict, vessel_db: dict, now: datetime) -> dict:
    """Write today's en-route totals into daily["days"][YYYY-MM-DD].

    Sums cargo_litres from each record's in_transit block, grouped by
    ship_type. Skips ballast vessels and arrived records (in_transit=None).
    Overwrites any prior entry for today's UTC date.
    """
    day_key = now.strftime("%Y-%m-%d")

    crude = 0
    product = 0
    for record in vessel_db.values():
        in_transit = record.get("in_transit")
        if not in_transit:
            continue
        if in_transit.get("is_ballast"):
            continue
        cargo = in_transit.get("cargo_litres", 0)
        if record.get("ship_type") == "crude":
            crude += cargo
        else:
            product += cargo

    daily.setdefault("days", {})[day_key] = {
        "en_route_crude_litres": crude,
        "en_route_product_litres": product,
        "captured_at": now.isoformat(),
    }

    return daily
```

### Step 4: Run tests, verify pass

Run: `python -m pytest pipeline/tests/test_daily_estimates.py -v`
Expected: 5 passed.

### Step 5: Run full suite to confirm no other regressions

Run: `python -m pytest pipeline/tests/ -v`
Expected: **105 passed** (100 baseline + 5 new).

### Step 6: Commit

```bash
git add pipeline/daily_estimates.py pipeline/tests/test_daily_estimates.py
git commit -m "$(cat <<'EOF'
feat(daily): add update_daily_estimates helper

Sums en-route cargo litres from the in-transit roster grouped by
ship_type, writes to daily["days"][YYYY-MM-DD]. Skips ballast and
arrived vessels. Same-day reruns overwrite.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Wire the orchestrator to call `update_daily_estimates`

**Files:**
- Modify: `pipeline/orchestrator.py`

### Step 1: Add the import

At the top of `pipeline/orchestrator.py`, change:

```python
from pipeline.collector import run_collector
from pipeline.arrivals import detect_arrivals, load_ports
from pipeline.vessels import update_vessel_db
from pipeline.petroleum_stats import download_latest_excel, build_imports_json
```

to:

```python
from pipeline.collector import run_collector
from pipeline.arrivals import detect_arrivals, load_ports
from pipeline.vessels import update_vessel_db
from pipeline.daily_estimates import update_daily_estimates
from pipeline.petroleum_stats import download_latest_excel, build_imports_json
```

### Step 2: Load the daily file near the other state loads

In `run_pipeline`, find the block that loads prior state (currently near the top of the function, just below `os.makedirs(DATA_DIR, exist_ok=True)`). It already loads `arrivals.json`, `vessels.json`, and `monthly-estimates.json`. Add a line for the daily file:

```python
    arrivals_data = load_json(f"{DATA_DIR}/arrivals.json", {"arrivals": []})
    vessel_db = load_json(f"{DATA_DIR}/vessels.json", {})
    monthly = load_json(f"{DATA_DIR}/monthly-estimates.json", {"months": {}})
    daily = load_json(f"{DATA_DIR}/daily-estimates.json", {"days": {}})
    ports = load_ports(f"{DATA_DIR}/ports.json")
```

### Step 3: Add the new pipeline step between monthly estimates and petroleum stats

Find the block that ends the current Step 4 and starts Step 5. The existing orchestrator currently looks like this (numbering approximate — read the file to confirm):

```python
    print("Step 4: Updating monthly estimates...")
    monthly = update_monthly_estimates(monthly, new_arrivals, vessel_db)
    save_json(f"{DATA_DIR}/monthly-estimates.json", monthly)

    print("Step 5: Checking petroleum statistics...")
```

Replace with:

```python
    print("Step 4: Updating monthly estimates...")
    monthly = update_monthly_estimates(monthly, new_arrivals, vessel_db)
    save_json(f"{DATA_DIR}/monthly-estimates.json", monthly)

    print("Step 5: Updating daily estimates...")
    daily = update_daily_estimates(daily, vessel_db, datetime.now(timezone.utc))
    save_json(f"{DATA_DIR}/daily-estimates.json", daily)

    print("Step 6: Checking petroleum statistics...")
```

Note the "Step 5" label that was on the petroleum stats step is renumbered to "Step 6".

### Step 4: Run the full suite to confirm no regressions

Run: `python -m pytest pipeline/tests/ -v`
Expected: **105 passed** (same as end of Task 1 — no new tests, no regressions).

### Step 5: Smoke-import the orchestrator

Run: `python -c "from pipeline.orchestrator import run_pipeline; from pipeline.daily_estimates import update_daily_estimates; print('ok')"`
Expected: `ok`.

### Step 6: Commit

```bash
git add pipeline/orchestrator.py
git commit -m "$(cat <<'EOF'
feat(orchestrator): wire update_daily_estimates as Step 5

Writes data/daily-estimates.json each run using the post-refresh
roster. Renumbers petroleum stats to Step 6.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Extend frontend types and data layer

**Files:**
- Modify: `src/lib/types.ts`
- Modify: `src/lib/data.ts`

### Step 1: Add `DailyEstimate`, `DailyEstimates` types and extend `DashboardData`

In `src/lib/types.ts`, add the two new interfaces near the other chart-related types (e.g., just after `MonthlyEstimates`):

Find:

```typescript
export interface MonthlyEstimates {
  months: Record<string, MonthEstimate>;
}
```

Append immediately below:

```typescript
export interface DailyEstimate {
  en_route_crude_litres: number;
  en_route_product_litres: number;
  captured_at: string;
}

export interface DailyEstimates {
  days: Record<string, DailyEstimate>;
}
```

Then find `DashboardData`:

```typescript
export interface DashboardData {
  snapshot: Snapshot;
  arrivals: Arrival[];
  monthlyEstimates: MonthlyEstimates;
  imports: ImportsData;
}
```

Replace with:

```typescript
export interface DashboardData {
  snapshot: Snapshot;
  arrivals: Arrival[];
  monthlyEstimates: MonthlyEstimates;
  dailyEstimates: DailyEstimates;
  imports: ImportsData;
}
```

### Step 2: Update `loadDashboardData` to read `daily-estimates.json`

In `src/lib/data.ts`, find the import block and add `DailyEstimates` alongside the other type imports:

```typescript
import type {
  Snapshot,
  Vessel,
  VesselDb,
  Arrival,
  MonthlyEstimates,
  ImportsData,
  DashboardData,
} from "./types";
```

Replace with:

```typescript
import type {
  Snapshot,
  Vessel,
  VesselDb,
  Arrival,
  MonthlyEstimates,
  DailyEstimates,
  ImportsData,
  DashboardData,
} from "./types";
```

Then in `loadDashboardData`, add the daily read between the monthly read and the imports read. The existing function reads monthly-estimates.json then imports.json; insert daily-estimates.json between them.

Find:

```typescript
  const monthlyEstimates = readJson<MonthlyEstimates>(
    "monthly-estimates.json",
    { months: {} }
  );
  const imports = readJson<ImportsData>("imports.json", {
    imports_by_month: [],
    consumption_cover: [],
  });
  return {
    snapshot,
    arrivals: arrivalsData.arrivals,
    monthlyEstimates,
    imports,
  };
```

Replace with:

```typescript
  const monthlyEstimates = readJson<MonthlyEstimates>(
    "monthly-estimates.json",
    { months: {} }
  );
  const dailyEstimates = readJson<DailyEstimates>(
    "daily-estimates.json",
    { days: {} }
  );
  const imports = readJson<ImportsData>("imports.json", {
    imports_by_month: [],
    consumption_cover: [],
  });
  return {
    snapshot,
    arrivals: arrivalsData.arrivals,
    monthlyEstimates,
    dailyEstimates,
    imports,
  };
```

### Step 3: Build to verify TypeScript compiles

Run: `npm run build`
Expected: clean build.

### Step 4: Commit

```bash
git add src/lib/types.ts src/lib/data.ts
git commit -m "$(cat <<'EOF'
feat(frontend): read daily-estimates.json into DashboardData

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Create the `DailyEnRouteChart` component

**Files:**
- Create: `src/components/DailyEnRouteChart.tsx`

### Step 1: Write the component

Create `src/components/DailyEnRouteChart.tsx`:

```tsx
"use client";

import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer,
} from "recharts";
import type { DailyEstimates } from "@/lib/types";

interface DailyEnRouteChartProps {
  dailyEstimates: DailyEstimates;
}

interface ChartRow {
  date: string; // YYYY-MM-DD
  crude: number | null; // megalitres (null = gap day)
  product: number | null;
}

const COLORS = {
  crude: "#111827",   // matches HistoricalChart FUEL_COLORS.crude
  product: "#374151", // matches HistoricalChart FUEL_COLORS.diesel
};

function utcDateKey(d: Date): string {
  const yyyy = d.getUTCFullYear();
  const mm = String(d.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(d.getUTCDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function buildChartData(daily: DailyEstimates): ChartRow[] {
  const rows: ChartRow[] = [];
  const today = new Date();
  for (let offset = 29; offset >= 0; offset--) {
    const d = new Date(today);
    d.setUTCDate(today.getUTCDate() - offset);
    const key = utcDateKey(d);
    const entry = daily.days[key];
    rows.push({
      date: key,
      crude: entry ? entry.en_route_crude_litres / 1_000_000 : null,
      product: entry ? entry.en_route_product_litres / 1_000_000 : null,
    });
  }
  return rows;
}

const formatDate = (key: string) => {
  const parts = key.split("-");
  const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  return `${parts[2]} ${months[parseInt(parts[1]) - 1]}`;
};

export default function DailyEnRouteChart({ dailyEstimates }: DailyEnRouteChartProps) {
  const chartData = buildChartData(dailyEstimates);

  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={chartData} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis
          dataKey="date"
          tickFormatter={formatDate}
          tick={{ fontSize: 10, fill: "#6b7280" }}
          interval="preserveStartEnd"
        />
        <YAxis
          tick={{ fontSize: 10, fill: "#6b7280" }}
          label={{
            value: "Megalitres",
            angle: -90,
            position: "insideLeft",
            style: { fontSize: 10, fill: "#6b7280" },
          }}
        />
        <Tooltip
          formatter={(value: number | null) =>
            value === null ? "—" : [`${Math.round(value)} ML`]
          }
          labelFormatter={(label) => formatDate(String(label))}
        />
        <Legend wrapperStyle={{ fontSize: 10 }} />
        <Area
          type="monotone"
          dataKey="product"
          name="Product"
          stackId="fuel"
          stroke={COLORS.product}
          fill={COLORS.product}
          fillOpacity={0.8}
          connectNulls={false}
        />
        <Area
          type="monotone"
          dataKey="crude"
          name="Crude oil"
          stackId="fuel"
          stroke={COLORS.crude}
          fill={COLORS.crude}
          fillOpacity={0.8}
          connectNulls={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
```

Notes on stacking order: in a Recharts stacked `AreaChart`, the **first** `<Area>` stacks at the bottom and the **second** stacks on top. Product below + crude on top reads naturally (crude is typically the larger volume on top of the product base, matching the monthly chart's colour ordering where crude is darkest/topmost).

### Step 2: Build to verify

Run: `npm run build`
Expected: clean build.

### Step 3: Commit

```bash
git add src/components/DailyEnRouteChart.tsx
git commit -m "$(cat <<'EOF'
feat(chart): DailyEnRouteChart — stacked area, 30-day rolling window

Renders crude + product en-route volume for each of the last 30 UTC
calendar days; missing days show as gaps (connectNulls=false).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Mount the chart below the monthly one

**Files:**
- Modify: `src/app/page.tsx`

### Step 1: Import the new chart and render it below the monthly one

Find the existing import block in `src/app/page.tsx`:

```typescript
import { loadDashboardData } from "@/lib/data";
import Header from "@/components/Header";
import StatBar from "@/components/StatBar";
import DashboardGrid from "@/components/DashboardGrid";
import HistoricalChart from "@/components/HistoricalChart";
import Footer from "@/components/Footer";
import StaleBanner from "@/components/StaleBanner";
```

Add one line:

```typescript
import { loadDashboardData } from "@/lib/data";
import Header from "@/components/Header";
import StatBar from "@/components/StatBar";
import DashboardGrid from "@/components/DashboardGrid";
import HistoricalChart from "@/components/HistoricalChart";
import DailyEnRouteChart from "@/components/DailyEnRouteChart";
import Footer from "@/components/Footer";
import StaleBanner from "@/components/StaleBanner";
```

Then find the existing monthly chart block:

```tsx
      <div className="mb-6">
        <p className="text-[10px] uppercase tracking-label text-label mb-2">Monthly fuel imports by type</p>
        <HistoricalChart imports={data.imports.imports_by_month} monthlyEstimates={data.monthlyEstimates} />
        <p className="text-[9px] text-label-light mt-2">Source: Australian Petroleum Statistics, Dept of Climate Change, Energy, the Environment and Water</p>
      </div>
      <Footer />
```

Replace with:

```tsx
      <div className="mb-6">
        <p className="text-[10px] uppercase tracking-label text-label mb-2">Monthly fuel imports by type</p>
        <HistoricalChart imports={data.imports.imports_by_month} monthlyEstimates={data.monthlyEstimates} />
        <p className="text-[9px] text-label-light mt-2">Source: Australian Petroleum Statistics, Dept of Climate Change, Energy, the Environment and Water</p>
      </div>
      <div className="mb-6">
        <p className="text-[10px] uppercase tracking-label text-label mb-2">Daily volume en route (last 30 days)</p>
        <DailyEnRouteChart dailyEstimates={data.dailyEstimates} />
      </div>
      <Footer />
```

### Step 2: Build to verify

Run: `npm run build`
Expected: clean build.

### Step 3: Commit

```bash
git add src/app/page.tsx
git commit -m "$(cat <<'EOF'
feat(page): mount DailyEnRouteChart below the monthly chart

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review Notes

**Spec coverage:**
- §1 Data layer — Task 1 writes the JSON shape spec calls for; Task 2 loads/saves it.
- §2 Pipeline — Tasks 1, 2 (step numbering: monthly stays Step 4; daily becomes Step 5; petroleum stats renumbered to Step 6).
- §3 Frontend types — Task 3. Frontend data layer — Task 3. Chart component — Task 4. Placement — Task 5.
- §4 Backfill (none) — respected (no task adds backfill).
- §5 Edge cases — covered by test cases (same-day overwrite, ballast skip, arrived skip) and by frontend fallback (`{days: {}}`) handling empty data gracefully. Gap rendering via `connectNulls={false}` in Task 4.

**Placeholder scan:** no TBDs, no "handle edge cases" without concrete code, every step has complete code or concrete commands.

**Type consistency:**
- `update_daily_estimates(daily, vessel_db, now: datetime) -> dict` — used consistently in Tasks 1 and 2.
- `DailyEstimate` / `DailyEstimates` — defined in Task 3, used in Task 4 (`DailyEstimates` prop type) and Task 5 (`data.dailyEstimates`).
- JSON field names — `en_route_crude_litres`, `en_route_product_litres`, `captured_at`, `days` — consistent across Python (Task 1), TypeScript types (Task 3), and chart consumption (Task 4).
- Step numbering — Monthly 4, Daily 5, Petroleum 6 — consistent in Task 2's implementation.
