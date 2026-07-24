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

const SYDNEY_TZ = "Australia/Sydney";
const sydneyDateFmt = new Intl.DateTimeFormat("en-CA", {
  timeZone: SYDNEY_TZ,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

function sydneyDateKey(d: Date): string {
  return sydneyDateFmt.format(d); // en-CA gives YYYY-MM-DD
}

// Earliest Sydney date with stable readings. Captures from 16–19 Apr Sydney
// were excluded because the vessel roster was still warming up (crude
// readings hadn't reached their baseline).
const CHART_START_DATE = "2026-04-20";

function buildChartData(daily: DailyEstimates): ChartRow[] {
  // Re-bucket entries by Sydney local date derived from captured_at,
  // so a run at 07:14 AEST falls into today rather than yesterday-UTC.
  const localByDate: Record<string, { crude: number; product: number }> = {};
  for (const entry of Object.values(daily.days)) {
    const capturedAt = entry.captured_at;
    if (!capturedAt) continue;
    const key = sydneyDateKey(new Date(capturedAt));
    localByDate[key] = {
      crude: entry.en_route_crude_litres,
      product: entry.en_route_product_litres,
    };
  }

  const [sy, sm, sd] = CHART_START_DATE.split("-").map(Number);
  const startMs = Date.UTC(sy, sm - 1, sd);
  const todayKey = sydneyDateKey(new Date());
  const [ty, tm, td] = todayKey.split("-").map(Number);
  const endMs = Date.UTC(ty, tm - 1, td);
  const dayCount = Math.round((endMs - startMs) / 86_400_000) + 1;

  const rows: ChartRow[] = [];
  for (let i = 0; i < dayCount; i++) {
    const d = new Date(startMs + i * 86_400_000);
    const key = sydneyDateKey(d);
    const entry = localByDate[key];
    rows.push({
      date: key,
      crude: entry ? entry.crude / 1_000_000 : null,
      product: entry ? entry.product / 1_000_000 : null,
    });
  }
  return rows;
}

const formatDate = (key: string) => {
  const parts = key.split("-");
  const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  return `${parts[2]} ${months[parseInt(parts[1]) - 1]}`;
};

const SERIES_ORDER = ["crude", "product"] as const;
const SERIES_LABELS: Record<string, string> = {
  crude: "Crude oil",
  product: "Product",
};

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ payload?: ChartRow }>;
  label?: string | number;
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;
  const row = payload[0]?.payload;
  if (!row) return null;

  const hasData = SERIES_ORDER.some((k) => row[k] !== null && (row[k] ?? 0) > 0);

  return (
    <div style={{
      background: "#fff", border: "1px solid #d1d5db", padding: "4px 6px",
      fontSize: 10, lineHeight: 1.4, color: "#111827",
    }}>
      <div style={{ fontWeight: 600, marginBottom: 2 }}>{formatDate(String(label))}</div>
      {!hasData ? (
        <div style={{ color: "#6b7280" }}>No data available</div>
      ) : (
        SERIES_ORDER.filter((k) => row[k] !== null && (row[k] ?? 0) > 0).map((k) => (
          <div key={k} style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span style={{
              display: "inline-block", width: 8, height: 8,
              background: COLORS[k as keyof typeof COLORS],
              border: "1px solid #6b7280",
            }} />
            <span>{SERIES_LABELS[k]}: {Math.round(row[k] as number)} ML</span>
          </div>
        ))
      )}
    </div>
  );
}

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
          interval={6}
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
        <Tooltip content={<CustomTooltip />} />
        <Legend
          wrapperStyle={{ fontSize: 10 }}
          formatter={(value) => <span style={{ color: "#000" }}>{value}</span>}
        />
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
