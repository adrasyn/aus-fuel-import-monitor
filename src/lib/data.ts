import fs from "fs";
import path from "path";
import type {
  Snapshot,
  Arrival,
  MonthlyEstimates,
  ImportsData,
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

export function loadDashboardData(): DashboardData {
  const snapshot = readJson<Snapshot>("snapshot.json", {
    timestamp: "",
    vessels: [],
  });
  const arrivalsData = readJson<{ arrivals: Arrival[] }>("arrivals.json", {
    arrivals: [],
  });
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
}

export function formatLitres(litres: number): string {
  if (litres >= 1_000_000_000) return `${(litres / 1_000_000_000).toFixed(1)}B L`;
  if (litres >= 1_000_000) return `${(litres / 1_000_000).toFixed(0)}M L`;
  return `${litres.toLocaleString()} L`;
}
