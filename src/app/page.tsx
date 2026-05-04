import { loadDashboardData } from "@/lib/data";
import Header from "@/components/Header";
import StatBar from "@/components/StatBar";
import DashboardGrid from "@/components/DashboardGrid";
import HistoricalChart from "@/components/HistoricalChart";
import DailyEnRouteChart from "@/components/DailyEnRouteChart";
import Footer from "@/components/Footer";
import StaleBanner from "@/components/StaleBanner";

export default function Home() {
  const data = loadDashboardData();
  const laden = data.snapshot.vessels.filter((v) => !v.is_ballast);
  const totalLitres = laden.reduce((sum, v) => sum + v.cargo_litres, 0);

  // First month with full AIS pipeline coverage = the month AFTER the
  // earliest detected arrival. (The pipeline started part-way through that
  // earliest month, so it doesn't have full coverage of it.)
  const earliestArrivalTs = data.arrivals
    .map((a) => a.timestamp)
    .filter(Boolean)
    .sort()[0];
  let aisCompleteFromMonth: string | undefined;
  if (earliestArrivalTs) {
    const d = new Date(earliestArrivalTs);
    const next = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 1));
    aisCompleteFromMonth = `${next.getUTCFullYear()}-${String(next.getUTCMonth() + 1).padStart(2, "0")}`;
  }

  return (
    <main className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
      <StaleBanner timestamp={data.snapshot.timestamp} />
      <Header
        snapshot={data.snapshot}
        totalLitres={totalLitres}
        vesselCount={laden.length}
      />
      <StatBar
        vessels={data.snapshot.vessels}
        msoReserve={data.msoReserve}
      />
      <DashboardGrid vessels={data.snapshot.vessels} snapshotTimestamp={data.snapshot.timestamp} />
      <div className="mb-6">
        <p className="text-[10px] uppercase tracking-label text-label mb-2">Monthly fuel imports by type</p>
        <HistoricalChart imports={data.imports.imports_by_month} monthlyEstimates={data.monthlyEstimates} aisCompleteFromMonth={aisCompleteFromMonth} />
        <p className="text-[9px] text-label-light mt-2">Source: Australian Petroleum Statistics, Dept of Climate Change, Energy, the Environment and Water</p>
      </div>
      <div className="mb-6">
        <p className="text-[10px] uppercase tracking-label text-label mb-2">Daily volume en route (last 30 days)</p>
        <DailyEnRouteChart dailyEstimates={data.dailyEstimates} />
        <p className="text-[9px] text-label-light mt-2">Each day&apos;s value is the total cargo on tankers en route at the time. A vessel is counted while AIS-active within the last 14 days; it drops out of the daily total once arrived or silent past that window.</p>
      </div>
      <Footer />
    </main>
  );
}
