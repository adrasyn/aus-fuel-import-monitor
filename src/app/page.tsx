import { loadDashboardData } from "@/lib/data";
import Header from "@/components/Header";
import StatBar from "@/components/StatBar";

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
      <Header
        snapshot={data.snapshot}
        totalLitres={totalLitres}
        vesselCount={laden.length}
      />
      <StatBar
        vessels={data.snapshot.vessels}
        latestConsumptionCover={latestConsumption}
      />
      {/* Map + Table will go here */}
      {/* Historical chart will go here */}
    </main>
  );
}
