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

  const latestConsumption =
    data.imports.consumption_cover.length > 0
      ? data.imports.consumption_cover[data.imports.consumption_cover.length - 1]
      : null;

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
        latestConsumptionCover={latestConsumption}
      />
      <DashboardGrid vessels={data.snapshot.vessels} />
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
    </main>
  );
}
