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

const DATA_DIR = path.join(process.cwd(), "data");

function readJson<T>(filename: string, fallback: T): T {
  const filePath = path.join(DATA_DIR, filename);
  try {
    const raw = fs.readFileSync(filePath, "utf-8");
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function rosterToSnapshot(db: VesselDb): Snapshot {
  const vessels: Vessel[] = [];
  let latest = "";

  for (const [imo, record] of Object.entries(db)) {
    const it = record.in_transit;
    if (!it) continue;
    // Parked in AU after a prior arrival — pipeline knows it hasn't left yet,
    // so it's not "en route" even though its in_transit block keeps refreshing
    // while it pings from the anchorage.
    if (record.departed_au_since_arrival === false) continue;
    // Inferred to have berthed after going AIS-dark. Its in_transit block is
    // retained (for reversal), but it's no longer en route — exclude it from
    // the live roster so the map/headline agree with the en-route totals.
    if (record.probable_arrival) continue;

    vessels.push({
      mmsi: it.mmsi,
      imo,
      name: record.name,
      ship_type: record.ship_type,
      lat: it.lat,
      lon: it.lon,
      speed: it.speed,
      course: it.course,
      draught: it.draught,
      length: record.length,
      beam: record.beam,
      destination: it.destination,
      destination_parsed: it.destination_parsed,
      vessel_class: record.vessel_class,
      dwt: record.dwt,
      load_factor: it.load_factor,
      cargo_tonnes: it.cargo_tonnes,
      cargo_litres: it.cargo_litres,
      is_ballast: it.is_ballast,
      draught_missing: it.draught_missing,
      last_update: it.last_position_update,
      last_position_update: it.last_position_update,
    });

    if (it.last_position_update > latest) {
      latest = it.last_position_update;
    }
  }

  return { timestamp: latest, vessels };
}

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

export function formatLitres(litres: number): string {
  if (litres >= 1_000_000_000) return `${(litres / 1_000_000_000).toFixed(1)}B L`;
  if (litres >= 1_000_000) return `${(litres / 1_000_000).toFixed(0)}M L`;
  return `${litres.toLocaleString()} L`;
}
