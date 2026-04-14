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
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          formatter={(value: any) =>
            value == null ? "—" : [`${Math.round(value as number)} ML`]
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
