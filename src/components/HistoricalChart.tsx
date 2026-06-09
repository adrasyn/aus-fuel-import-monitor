"use client";

import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, Cell,
  useXAxisScale, useYAxisScale,
} from "recharts";
import type { ImportRecord, MonthlyEstimates } from "@/lib/types";

interface HistoricalChartProps {
  imports: ImportRecord[];
  monthlyEstimates: MonthlyEstimates;
  // First month from which the AIS pipeline had full coverage. Past months
  // before this remain "no data" placeholders even if they have partial
  // estimate values.
  aisCompleteFromMonth?: string;
}

interface ChartRow {
  month: string;
  crude: number;
  gasoline: number;
  diesel: number;
  jet_fuel: number;
  fuel_oil: number;
  lpg: number;
  product: number;
  probable_crude: number;
  probable_product: number;
  no_data: number;
  source: "government" | "ais_complete" | "current_month" | "no_data";
}

const FUEL_COLORS = {
  crude: "#111827",
  diesel: "#374151",
  gasoline: "#6b7280",
  jet_fuel: "#9ca3af",
  fuel_oil: "#d1d5db",
  lpg: "#e5e7eb",
  product: "#6b7280",
  probable_crude: "#9ca3af",
  probable_product: "#cbd5e1",
};

const FUEL_LABELS: Record<string, string> = {
  crude: "Crude oil",
  diesel: "Diesel",
  gasoline: "Gasoline",
  jet_fuel: "Jet fuel",
  fuel_oil: "Fuel oil",
  lpg: "LPG",
  product: "Product (unspecified)",
  probable_crude: "Crude (probable)",
  probable_product: "Product (probable)",
};

const FUEL_ORDER = ["crude", "diesel", "gasoline", "jet_fuel", "fuel_oil", "lpg", "product"] as const;

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ payload?: ChartRow }>;
  label?: string | number;
  currentMonth: string;
}

function CustomTooltip({ active, payload, label, currentMonth }: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;
  const row = payload[0]?.payload;
  if (!row) return null;

  const formatMonth = (month: string) => {
    const [y, m] = month.split("-");
    const monthLabels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    const lbl = `${monthLabels[parseInt(m) - 1]} ${y.slice(2)}`;
    return month === currentMonth ? `${lbl} MTD` : lbl;
  };

  return (
    <div style={{
      background: "#fff", border: "1px solid #d1d5db", padding: "4px 6px",
      fontSize: 10, lineHeight: 1.4, color: "#111827",
    }}>
      <div style={{ fontWeight: 600, marginBottom: 2 }}>{formatMonth(String(label))}</div>
      {row.source === "no_data" ? (
        <div style={{ color: "#6b7280" }}>No data available</div>
      ) : (
        <>
          {FUEL_ORDER.filter((k) => (row[k] ?? 0) > 0).map((k) => (
            <div key={k} style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <span style={{
                display: "inline-block", width: 8, height: 8,
                background: FUEL_COLORS[k as keyof typeof FUEL_COLORS],
                border: "1px solid #6b7280",
              }} />
              <span>{FUEL_LABELS[k]}: {row[k]} ML</span>
            </div>
          ))}
          {(row.probable_crude + row.probable_product) > 0 && (
            <div style={{ marginTop: 2, paddingTop: 2, borderTop: "1px dashed #d1d5db", color: "#6b7280" }}>
              + probable: {row.probable_crude + row.probable_product} ML
            </div>
          )}
        </>
      )}
    </div>
  );
}

function NoDataLabels({ chartData }: { chartData: ChartRow[] }) {
  const xScale = useXAxisScale();
  const yScale = useYAxisScale();
  if (!xScale || !yScale) return null;

  const NO_DATA_BAR_HEIGHT = 5000;
  const yTop = yScale(NO_DATA_BAR_HEIGHT);
  const yBot = yScale(0);
  if (typeof yTop !== "number" || typeof yBot !== "number") return null;
  const cy = (yTop + yBot) / 2;

  return (
    <g pointerEvents="none">
      {chartData.map((d, i) => {
        if (d.source !== "no_data") return null;
        const cx = xScale(d.month, { position: "middle" });
        if (typeof cx !== "number") return null;
        return (
          <text
            key={i}
            x={cx} y={cy}
            transform={`rotate(-90, ${cx}, ${cy})`}
            textAnchor="middle" dominantBaseline="middle"
            fontSize={10} fontWeight={500} fill="#374151"
          >
            No data
          </text>
        );
      })}
    </g>
  );
}

function ExperimentalLabels({ chartData }: { chartData: ChartRow[] }) {
  const xScale = useXAxisScale();
  const yScale = useYAxisScale();
  if (!xScale || !yScale) return null;

  // Anchor the label at the vertical midpoint of the chart's data range,
  // not the midpoint of the partial MTD bar. We compute the max bar height
  // across all rows and place the label at half that value — this puts it
  // visually near the centre of the plotted area regardless of how low
  // the current month's MTD bar sits.
  const maxBar = Math.max(
    ...chartData.map((d) =>
      d.source === "no_data"
        ? d.no_data
        : d.crude + d.gasoline + d.diesel + d.jet_fuel + d.fuel_oil + d.lpg + d.product,
    ),
    1,
  );
  const yMid = yScale(maxBar / 2);
  if (typeof yMid !== "number") return null;

  return (
    <g pointerEvents="none">
      {chartData.map((d, i) => {
        if (d.source !== "current_month") return null;
        const total = d.crude + d.gasoline + d.diesel + d.jet_fuel + d.fuel_oil + d.lpg + d.product;
        if (total <= 0) return null;
        const cx = xScale(d.month, { position: "middle" });
        if (typeof cx !== "number") return null;
        const cy = yMid;
        return (
          <text
            key={i}
            x={cx} y={cy}
            transform={`rotate(-90, ${cx}, ${cy})`}
            textAnchor="middle" dominantBaseline="middle"
            fontSize={10} fontWeight={500} fill="#dc2626"
          >
            Experimental
          </text>
        );
      })}
    </g>
  );
}

export default function HistoricalChart({ imports, monthlyEstimates, aisCompleteFromMonth }: HistoricalChartProps) {
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
      product: 0,
      probable_crude: 0,
      probable_product: 0,
      no_data: 0,
      source: "government",
    });
  }

  const now = new Date();
  const currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;

  // AIS estimate months: only the current month is treated as a partial estimate
  // (with en-route vessels). Past months between the last government month and
  // the current month are rendered as "no data" placeholders — the AIS scrape
  // does not have complete coverage of them.
  const estimateMonths = Object.entries(monthlyEstimates.months)
    .filter(([month]) => month > lastGovtMonth)
    .sort(([a], [b]) => a.localeCompare(b));
  const estimateByMonth = new Map(estimateMonths);

  const addMonths = (ym: string, delta: number) => {
    const [y, m] = ym.split("-").map(Number);
    const d = new Date(Date.UTC(y, m - 1 + delta, 1));
    return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
  };

  if (lastGovtMonth) {
    let cursor = addMonths(lastGovtMonth, 1);
    while (cursor <= currentMonth) {
      const est = estimateByMonth.get(cursor);
      const isCurrent = cursor === currentMonth;
      const hasFullAisCoverage =
        aisCompleteFromMonth !== undefined && cursor >= aisCompleteFromMonth;

      if ((isCurrent || hasFullAisCoverage) && est) {
        // Both branches use arrived_* only — that's an honest cumulative
        // count of cargo discharged at AU ports this month. en_route_* is
        // intentionally excluded: it has no ETA-window filter, so adding it
        // would inflate the bar with vessels that will actually land in the
        // following month, double-counting them on the boundary.
        const crudeMl = est.arrived_crude_litres / 1_000_000;
        const productMl = est.arrived_product_litres / 1_000_000;
        const probCrudeMl = (est.probable_crude_litres ?? 0) / 1_000_000;
        const probProductMl = (est.probable_product_litres ?? 0) / 1_000_000;
        chartData.push({
          month: cursor,
          crude: Math.round(crudeMl),
          gasoline: 0, diesel: 0, jet_fuel: 0, fuel_oil: 0, lpg: 0,
          product: Math.round(productMl),
          probable_crude: Math.round(probCrudeMl),
          probable_product: Math.round(probProductMl),
          no_data: 0,
          source: isCurrent ? "current_month" : "ais_complete",
        });
      } else {
        chartData.push({
          month: cursor,
          crude: 0, gasoline: 0, diesel: 0, jet_fuel: 0, fuel_oil: 0, lpg: 0, product: 0,
          probable_crude: 0, probable_product: 0,
          no_data: 1,
          source: "no_data",
        });
      }
      cursor = addMonths(cursor, 1);
    }
  }

  // No-data placeholder bars: render at a fixed 5000 ML so they're clearly
  // sized as a placeholder (close to a typical full-month total) without
  // pretending to be real data. The bar carries a rotated "No data" label.
  const NO_DATA_BAR_HEIGHT = 5000;
  for (const row of chartData) {
    if (row.source === "no_data") row.no_data = NO_DATA_BAR_HEIGHT;
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

  const cellOpacity = (source: ChartRow["source"]) =>
    source === "government" ? 1 : source === "no_data" ? 0 : 0.4;
  const cellStroke = (source: ChartRow["source"], color: string) =>
    source === "current_month" ? color : undefined;
  const cellDash = (source: ChartRow["source"]) =>
    source === "current_month" ? "4 2" : undefined;

  return (
    <div>
      <ResponsiveContainer width="100%" height={350}>
        <BarChart data={chartData} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="month" tickFormatter={formatMonth} tick={{ fontSize: 10, fill: "#6b7280" }} interval="preserveStartEnd" />
          <YAxis tick={{ fontSize: 10, fill: "#6b7280" }} label={{ value: "Megalitres", angle: -90, position: "insideLeft", style: { fontSize: 10, fill: "#6b7280" } }} />
          <Tooltip content={<CustomTooltip currentMonth={currentMonth} />} />
          <Legend
            wrapperStyle={{ fontSize: 10 }}
            formatter={(value) => <span style={{ color: "#000" }}>{value}</span>}
          />
          <Bar dataKey="crude" name="Crude oil" stackId="fuel" fill={FUEL_COLORS.crude}>
            {chartData.map((entry, i) => (
              <Cell key={i} fillOpacity={cellOpacity(entry.source)}
                strokeDasharray={cellDash(entry.source)} stroke={cellStroke(entry.source, FUEL_COLORS.crude)} />
            ))}
          </Bar>
          <Bar dataKey="diesel" name="Diesel" stackId="fuel" fill={FUEL_COLORS.diesel}>
            {chartData.map((entry, i) => (
              <Cell key={i} fillOpacity={cellOpacity(entry.source)}
                strokeDasharray={cellDash(entry.source)} stroke={cellStroke(entry.source, FUEL_COLORS.diesel)} />
            ))}
          </Bar>
          <Bar dataKey="gasoline" name="Gasoline" stackId="fuel" fill={FUEL_COLORS.gasoline}>
            {chartData.map((entry, i) => (
              <Cell key={i} fillOpacity={cellOpacity(entry.source)}
                strokeDasharray={cellDash(entry.source)} stroke={cellStroke(entry.source, FUEL_COLORS.gasoline)} />
            ))}
          </Bar>
          <Bar dataKey="jet_fuel" name="Jet fuel" stackId="fuel" fill={FUEL_COLORS.jet_fuel}>
            {chartData.map((entry, i) => (
              <Cell key={i} fillOpacity={cellOpacity(entry.source)}
                strokeDasharray={cellDash(entry.source)} stroke={cellStroke(entry.source, FUEL_COLORS.jet_fuel)} />
            ))}
          </Bar>
          <Bar dataKey="fuel_oil" name="Fuel oil" stackId="fuel" fill={FUEL_COLORS.fuel_oil}>
            {chartData.map((entry, i) => (
              <Cell key={i} fillOpacity={cellOpacity(entry.source)}
                strokeDasharray={cellDash(entry.source)} stroke={cellStroke(entry.source, FUEL_COLORS.fuel_oil)} />
            ))}
          </Bar>
          <Bar dataKey="lpg" name="LPG" stackId="fuel" fill={FUEL_COLORS.lpg}>
            {chartData.map((entry, i) => (
              <Cell key={i} fillOpacity={cellOpacity(entry.source)}
                strokeDasharray={cellDash(entry.source)} stroke={cellStroke(entry.source, FUEL_COLORS.lpg)} />
            ))}
          </Bar>
          <Bar dataKey="product" name="Product (unspecified)" stackId="fuel" fill={FUEL_COLORS.product}>
            {chartData.map((entry, i) => (
              <Cell key={i} fillOpacity={cellOpacity(entry.source)}
                strokeDasharray={cellDash(entry.source)} stroke={cellStroke(entry.source, FUEL_COLORS.product)} />
            ))}
          </Bar>
          <Bar dataKey="probable_crude" name="Crude (probable)" stackId="fuel" fill={FUEL_COLORS.probable_crude}>
            {chartData.map((entry, i) => (
              <Cell key={i} fillOpacity={entry.source === "no_data" ? 0 : 0.25}
                strokeDasharray="3 2" stroke={entry.source === "no_data" ? undefined : "#6b7280"} />
            ))}
          </Bar>
          <Bar dataKey="probable_product" name="Product (probable)" stackId="fuel" fill={FUEL_COLORS.probable_product}>
            {chartData.map((entry, i) => (
              <Cell key={i} fillOpacity={entry.source === "no_data" ? 0 : 0.25}
                strokeDasharray="3 2" stroke={entry.source === "no_data" ? undefined : "#6b7280"} />
            ))}
          </Bar>
          <Bar dataKey="no_data" name="No data" stackId="fuel" fill="#e5e7eb" legendType="none" isAnimationActive={false}>
            {chartData.map((entry, i) => (
              <Cell key={i} fillOpacity={entry.source === "no_data" ? 0.35 : 0} />
            ))}
          </Bar>
          <NoDataLabels chartData={chartData} />
          <ExperimentalLabels chartData={chartData} />
        </BarChart>
      </ResponsiveContainer>
      <div className="flex flex-wrap gap-4 mt-2 text-[9px] text-label-light">
        <span><span className="inline-block w-3 h-3 bg-border-heavy mr-1 align-middle" /> Solid = government data</span>
        {chartData.some((r) => r.source === "ais_complete") && (
          <span><span className="inline-block w-3 h-3 bg-border-heavy/40 mr-1 align-middle" /> Faded = AIS arrivals (pre-government)</span>
        )}
        {chartData.some((r) => r.source === "current_month") && (
          <span><span className="inline-block w-3 h-3 bg-border-heavy/40 mr-1 align-middle border border-dashed border-border-heavy" /> Dashed = current month (arrivals to date)</span>
        )}
        {chartData.some((r) => r.source === "no_data") && (
          <span><span className="inline-block w-3 h-3 mr-1 align-middle" style={{ background: "#e5e7eb" }} /> Grey = no data available (placeholder height)</span>
        )}
        {chartData.some((r) => (r.probable_crude + r.probable_product) > 0) && (
          <span><span className="inline-block w-3 h-3 mr-1 align-middle border border-dashed border-border-heavy" style={{ background: "#cbd5e1", opacity: 0.4 }} /> Lighter cap = probable arrivals (AIS-inferred)</span>
        )}
      </div>
    </div>
  );
}
