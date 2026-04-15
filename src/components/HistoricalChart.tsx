"use client";

import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, Cell,
} from "recharts";
import type { ImportRecord, MonthlyEstimates } from "@/lib/types";

interface HistoricalChartProps {
  imports: ImportRecord[];
  monthlyEstimates: MonthlyEstimates;
}

interface ChartRow {
  month: string;
  crude: number;
  gasoline: number;
  diesel: number;
  jet_fuel: number;
  fuel_oil: number;
  lpg: number;
  source: "government" | "ais_estimate" | "current_month";
}

const FUEL_COLORS = {
  crude: "#111827",
  diesel: "#374151",
  gasoline: "#6b7280",
  jet_fuel: "#9ca3af",
  fuel_oil: "#d1d5db",
  lpg: "#e5e7eb",
};

export default function HistoricalChart({ imports, monthlyEstimates }: HistoricalChartProps) {
  const chartData: ChartRow[] = [];

  // Government data (last 24 months)
  const recentImports = imports.slice(-24);
  const lastGovtMonth = recentImports.length > 0
    ? recentImports[recentImports.length - 1].month
    : "";

  for (const record of recentImports) {
    chartData.push({
      month: record.month,
      crude: record.crude_oil_ml,
      gasoline: record.gasoline_ml,
      diesel: record.diesel_ml,
      jet_fuel: record.jet_fuel_ml,
      fuel_oil: record.fuel_oil_ml,
      lpg: record.lpg_ml,
      source: "government",
    });
  }

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

  if (chartData.length === 0) {
    return (
      <div className="border border-border h-[300px] flex items-center justify-center text-label-light text-sm">
        No import data available yet
      </div>
    );
  }

  const formatMonth = (month: string) => {
    const [y, m] = month.split("-");
    const monthLabels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    const label = `${monthLabels[parseInt(m) - 1]} ${y.slice(2)}`;
    return month === currentMonth ? `${label} MTD` : label;
  };

  return (
    <div>
      <ResponsiveContainer width="100%" height={350}>
        <BarChart data={chartData} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="month" tickFormatter={formatMonth} tick={{ fontSize: 10, fill: "#6b7280" }} interval="preserveStartEnd" />
          <YAxis tick={{ fontSize: 10, fill: "#6b7280" }} label={{ value: "Megalitres", angle: -90, position: "insideLeft", style: { fontSize: 10, fill: "#6b7280" } }} />
          <Tooltip formatter={(value) => [`${value} ML`]} labelFormatter={(label) => formatMonth(String(label))} />
          <Legend wrapperStyle={{ fontSize: 10, color: "#000" }} />
          <Bar dataKey="crude" name="Crude oil" stackId="fuel" fill={FUEL_COLORS.crude}>
            {chartData.map((entry, i) => (
              <Cell key={i} fillOpacity={entry.source === "government" ? 1 : 0.4}
                strokeDasharray={entry.source === "current_month" ? "4 2" : undefined}
                stroke={entry.source === "current_month" ? FUEL_COLORS.crude : undefined} />
            ))}
          </Bar>
          <Bar dataKey="diesel" name="Diesel" stackId="fuel" fill={FUEL_COLORS.diesel}>
            {chartData.map((entry, i) => (<Cell key={i} fillOpacity={entry.source === "government" ? 1 : 0.4} />))}
          </Bar>
          <Bar dataKey="gasoline" name="Gasoline" stackId="fuel" fill={FUEL_COLORS.gasoline}>
            {chartData.map((entry, i) => (<Cell key={i} fillOpacity={entry.source === "government" ? 1 : 0.4} />))}
          </Bar>
          <Bar dataKey="jet_fuel" name="Jet fuel" stackId="fuel" fill={FUEL_COLORS.jet_fuel}>
            {chartData.map((entry, i) => (<Cell key={i} fillOpacity={entry.source === "government" ? 1 : 0.4} />))}
          </Bar>
          <Bar dataKey="fuel_oil" name="Fuel oil" stackId="fuel" fill={FUEL_COLORS.fuel_oil}>
            {chartData.map((entry, i) => (<Cell key={i} fillOpacity={entry.source === "government" ? 1 : 0.4} />))}
          </Bar>
          <Bar dataKey="lpg" name="LPG" stackId="fuel" fill={FUEL_COLORS.lpg}>
            {chartData.map((entry, i) => (<Cell key={i} fillOpacity={entry.source === "government" ? 1 : 0.4} />))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <div className="flex flex-wrap gap-4 mt-2 text-[9px] text-label-light">
        <span><span className="inline-block w-3 h-3 bg-border-heavy mr-1 align-middle" /> Solid = government data</span>
        <span><span className="inline-block w-3 h-3 bg-border-heavy/40 mr-1 align-middle" /> Faded = AIS estimate (provisional)</span>
        {chartData.some((r) => r.source === "current_month") && (
          <span><span className="inline-block w-3 h-3 bg-border-heavy/40 mr-1 align-middle border border-dashed border-border-heavy" /> Dashed = current month (to date)</span>
        )}
      </div>
    </div>
  );
}
