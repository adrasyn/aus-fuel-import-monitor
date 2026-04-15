# DCCEEW MSO Reserves Stat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single APS-sourced "Days reserve (govt)" StatBar stat with three DCCEEW-sourced per-fuel stats (Petrol / Kerosene / Diesel) plus an "as of" caption, sourced from a hand-maintained `data/mso-reserves.json` file.

**Architecture:** New static JSON file consumed server-side in `loadDashboardData`. Null-safe through the render path — if the file is missing or malformed, the three stats and caption disappear, the page still renders. No pipeline changes.

**Tech Stack:** Next.js 15 app router (static export), TypeScript, Tailwind. No new dependencies.

Spec: `docs/superpowers/specs/2026-04-15-mso-reserves-stat-design.md`

---

### Task 1: Seed `data/mso-reserves.json`

**Files:**
- Create: `data/mso-reserves.json`

- [ ] **Step 1: Create the file**

Create `data/mso-reserves.json` with this exact content:

```json
{
  "source": "DCCEEW Minimum Stockholding Obligation",
  "source_url": "https://www.dcceew.gov.au/energy/security/australias-fuel-security/minimum-stockholding-obligation/statistics",
  "as_of": "2026-04-07",
  "fuels": [
    { "key": "petrol", "label": "Petrol", "days": 38 },
    { "key": "kerosene", "label": "Kerosene", "days": 28 },
    { "key": "diesel", "label": "Diesel", "days": 31 }
  ]
}
```

- [ ] **Step 2: Verify JSON parses**

Run: `python -c "import json; print(json.load(open('data/mso-reserves.json')))"`
Expected: prints the dict, no error.

- [ ] **Step 3: Commit**

```bash
git add data/mso-reserves.json
git commit -m "data: seed mso-reserves.json with DCCEEW values as of 2026-04-07"
```

---

### Task 2: Add `MsoReserve` types

**Files:**
- Modify: `src/lib/types.ts`

- [ ] **Step 1: Append the new interfaces and extend `DashboardData`**

Add these interfaces at the end of `src/lib/types.ts`, immediately after the existing `ImportsData` interface (so they sit alongside the other data-shape types):

```ts
export interface MsoReserveFuel {
  key: string;
  label: string;
  days: number;
}

export interface MsoReserve {
  source: string;
  source_url: string;
  as_of: string; // ISO YYYY-MM-DD
  fuels: MsoReserveFuel[];
}
```

Then extend the `DashboardData` interface (currently lines 127-133) to add a new field:

```ts
export interface DashboardData {
  snapshot: Snapshot;
  arrivals: Arrival[];
  monthlyEstimates: MonthlyEstimates;
  dailyEstimates: DailyEstimates;
  imports: ImportsData;
  msoReserve: MsoReserve | null;
}
```

- [ ] **Step 2: TypeScript sanity check**

Run: `npx tsc --noEmit`
Expected: FAILS. `src/lib/data.ts` no longer satisfies `DashboardData` because it doesn't return `msoReserve` yet. This confirms the type change is wired. Task 3 fixes it.

---

### Task 3: Load `mso-reserves.json` in `loadDashboardData`

**Files:**
- Modify: `src/lib/data.ts`

- [ ] **Step 1: Update the import list**

Replace the existing import block at the top of `src/lib/data.ts` (lines 1-12):

```ts
import fs from "fs";
import path from "path";
import type {
  Snapshot,
  Vessel,
  VesselDb,
  Arrival,
  MonthlyEstimates,
  DailyEstimates,
  ImportsData,
  MsoReserve,
  DashboardData,
} from "./types";
```

- [ ] **Step 2: Load the file and include it in the returned `DashboardData`**

In `loadDashboardData` (currently lines 67-92), add a new `readJson` call after the `imports` line and include `msoReserve` in the returned object.

The generic `readJson<T>(filename, fallback)` already returns the fallback on read/parse error — so passing `null` as the fallback gives us the graceful-missing behaviour the spec requires.

New body:

```ts
export function loadDashboardData(): DashboardData {
  const db = readJson<VesselDb>("vessels.json", {});
  const snapshot = rosterToSnapshot(db);
  const arrivalsData = readJson<{ arrivals: Arrival[] }>("arrivals.json", {
    arrivals: [],
  });
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
  const msoReserve = readJson<MsoReserve | null>("mso-reserves.json", null);
  return {
    snapshot,
    arrivals: arrivalsData.arrivals,
    monthlyEstimates,
    dailyEstimates,
    imports,
    msoReserve,
  };
}
```

- [ ] **Step 3: TypeScript verification**

Run: `npx tsc --noEmit`
Expected: PASS. `DashboardData` is now fully satisfied.

- [ ] **Step 4: Commit tasks 2 + 3 together**

These two tasks form one atomic type-plus-loader change; commit together so no revision is ever broken.

```bash
git add src/lib/types.ts src/lib/data.ts
git commit -m "feat(types,data): load mso-reserves.json into DashboardData"
```

---

### Task 4: Render three DCCEEW stats + caption in StatBar, drop APS stat

**Files:**
- Modify: `src/components/StatBar.tsx`
- Modify: `src/app/page.tsx`

These two files must change in the same commit — `StatBar`'s props contract changes (drops `latestConsumptionCover`, adds `msoReserve`), so `page.tsx` needs to pass the new prop at the same time or TypeScript compilation breaks.

- [ ] **Step 1: Rewrite `src/components/StatBar.tsx`**

Replace the entire file contents with:

```tsx
import type { Vessel, MsoReserve } from "@/lib/types";

interface StatBarProps {
  vessels: Vessel[];
  msoReserve: MsoReserve | null;
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <div className="font-headline text-3xl font-light">{value}</div>
      <div className="text-[10px] uppercase tracking-label text-label">{label}</div>
    </div>
  );
}

const MONTHS_SHORT = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

function formatAsOf(iso: string): string {
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!m) return iso;
  const day = parseInt(m[3], 10);
  const month = MONTHS_SHORT[parseInt(m[2], 10) - 1];
  const year = m[1];
  return `${day} ${month} ${year}`;
}

export default function StatBar({ vessels, msoReserve }: StatBarProps) {
  const laden = vessels.filter((v) => !v.is_ballast);
  const crude = laden.filter((v) => v.ship_type === "crude");
  const product = laden.filter((v) => v.ship_type === "product");

  const crudeLitres = crude.reduce((sum, v) => sum + v.cargo_litres, 0);
  const productLitres = product.reduce((sum, v) => sum + v.cargo_litres, 0);

  const formatBL = (litres: number) => {
    if (litres >= 1_000_000_000) return `${(litres / 1_000_000_000).toFixed(1)}B L`;
    if (litres >= 1_000_000) return `${(litres / 1_000_000).toFixed(0)}M L`;
    return `${litres.toLocaleString()} L`;
  };

  return (
    <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-6 pb-5 mb-6 border-b border-border">
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap gap-x-8 gap-y-4">
          <Stat value={String(crude.length)} label="Crude oil tankers" />
          <Stat value={String(product.length)} label="Product tankers" />
          <Stat value={formatBL(crudeLitres)} label="Crude oil est." />
          <Stat value={formatBL(productLitres)} label="Refined products est." />
          {msoReserve?.fuels.map((fuel) => (
            <Stat
              key={fuel.key}
              value={String(fuel.days)}
              label={`${fuel.label} days`}
            />
          ))}
        </div>
        {msoReserve && (
          <p className="text-[10px] text-label-light">
            MSO reserve · as of {formatAsOf(msoReserve.as_of)} ·{" "}
            <a
              href={msoReserve.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:text-label"
            >
              source
            </a>
          </p>
        )}
      </div>
      <p className="text-[10px] text-label-light max-w-[280px] md:text-right leading-snug">
        Tracking only ships within terrestrial AIS range (~30nm of coastal receivers). Vessels mid-ocean &mdash; e.g. crossing the Pacific &mdash; won&apos;t appear until they&apos;re near a receiver.
      </p>
    </div>
  );
}
```

Key changes from current:
- Imports `MsoReserve` type, drops `ConsumptionRecord`.
- Prop is `msoReserve: MsoReserve | null` (was `latestConsumptionCover: ConsumptionRecord | null`).
- Removes the single `Days reserve (govt)` stat that read `latestConsumptionCover?.total_days`.
- Renders one `<Stat>` per entry in `msoReserve.fuels` when non-null.
- Adds a caption `<p>` below the stat row (inside a new flex-col wrapper) showing `MSO reserve · as of 7 Apr 2026 · source` (link to `source_url`), hidden when `msoReserve` is null.
- `formatAsOf` helper is a simple regex-based formatter — avoids `Intl.DateTimeFormat` timezone quirks on a date-only string.

- [ ] **Step 2: Update `src/app/page.tsx`**

Replace lines 15-18 (the `latestConsumption` derivation) — delete those four lines entirely.

Then replace the `<StatBar ... />` call (currently lines 28-31) with:

```tsx
      <StatBar
        vessels={data.snapshot.vessels}
        msoReserve={data.msoReserve}
      />
```

No other changes to `page.tsx`.

- [ ] **Step 3: Verify build**

Run: `npx next build`
Expected: PASS. Four static pages exported. The only warnings should be pre-existing (e.g. the custom-font warning in `src/app/layout.tsx`). No new warnings or errors.

- [ ] **Step 4: Commit tasks 4**

```bash
git add src/components/StatBar.tsx src/app/page.tsx
git commit -m "feat(statbar): replace APS days-reserve with DCCEEW per-fuel stats"
```

---

### Task 5: Smoke-test the missing-file fallback

**Files:**
- None modified. Temporary rename only.

- [ ] **Step 1: Temporarily hide the JSON file**

```bash
mv data/mso-reserves.json data/mso-reserves.json.bak
```

- [ ] **Step 2: Rebuild and confirm no crash**

Run: `npx next build`
Expected: PASS. Build succeeds with no new errors — `readJson` catches the ENOENT and returns `null`, `StatBar` omits the three stats + caption.

- [ ] **Step 3: Restore the file**

```bash
mv data/mso-reserves.json.bak data/mso-reserves.json
```

- [ ] **Step 4: Run existing pytest to confirm no pipeline regressions**

Run: `python -m pytest pipeline/tests/ -q`
Expected: `135 passed`.

- [ ] **Step 5: No commit needed**

This task is verification-only. If steps 2-4 all pass, the implementation is complete.

---

## Update workflow (for the user, post-implementation)

To refresh the DCCEEW numbers weekly, edit `data/mso-reserves.json`: bump `as_of` to the new date and update the three `days` values from the DCCEEW site. Commit and push. The deploy workflow rebuilds in ~2 minutes.

Example update:

```bash
# Edit data/mso-reserves.json — bump as_of + three days values
git add data/mso-reserves.json
git commit -m "data: refresh MSO reserves to 14 Apr 2026"
git push
```
