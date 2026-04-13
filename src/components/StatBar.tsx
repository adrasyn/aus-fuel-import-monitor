import type { Vessel, ConsumptionRecord } from "@/lib/types";

interface StatBarProps {
  vessels: Vessel[];
  latestConsumptionCover: ConsumptionRecord | null;
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <div className="font-headline text-3xl font-light">{value}</div>
      <div className="text-[10px] uppercase tracking-label text-label">{label}</div>
    </div>
  );
}

export default function StatBar({ vessels, latestConsumptionCover }: StatBarProps) {
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

  const reserveDays = latestConsumptionCover?.total_days ?? "\u2014";

  return (
    <div className="flex flex-wrap gap-x-8 gap-y-4 pb-5 mb-6 border-b border-border">
      <Stat value={String(crude.length)} label="Crude oil tankers" />
      <Stat value={String(product.length)} label="Product tankers" />
      <Stat value={formatBL(crudeLitres)} label="Crude oil est." />
      <Stat value={formatBL(productLitres)} label="Refined products est." />
      <Stat value={String(reserveDays)} label="Days reserve (govt)" />
    </div>
  );
}
