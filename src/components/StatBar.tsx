import type { Vessel, MsoReserve } from "@/lib/types";
import { formatLitres } from "@/lib/data";

interface StatBarProps {
  vessels: Vessel[];
  msoReserve: MsoReserve | null;
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <div className="font-headline text-3xl font-light">{value}</div>
      <div className="text-[10px] uppercase tracking-label text-label">{label}</div>
    </div>
  );
}

const MONTHS_SHORT = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

function formatAsOf(iso: string): string {
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!m) return iso;
  const day = parseInt(m[3], 10);
  const month = MONTHS_SHORT[parseInt(m[2], 10) - 1];
  const year = m[1];
  return `${day} ${month} ${year}`;
}

export default function StatBar({ vessels, msoReserve }: StatBarProps) {
  const laden = vessels.filter((v) => !v.is_ballast);
  const crude = laden.filter((v) => v.ship_type === "crude");
  const product = laden.filter((v) => v.ship_type === "product");

  const crudeLitres = crude.reduce((sum, v) => sum + v.cargo_litres, 0);
  const productLitres = product.reduce((sum, v) => sum + v.cargo_litres, 0);

  return (
    <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-6 pb-5 mb-6 border-b border-border">
      <div className="flex flex-wrap gap-x-8 gap-y-4">
        <Stat value={String(crude.length)} label="Crude oil tankers" />
        <Stat value={String(product.length)} label="Product tankers" />
        <Stat value={formatLitres(crudeLitres)} label="Crude oil est." />
        <Stat value={formatLitres(productLitres)} label="Refined products est." />
        {msoReserve?.fuels?.map((fuel) => (
          <Stat
            key={fuel.key}
            value={String(fuel.days)}
            label={`Days of ${fuel.label.toLowerCase()} reserves`}
          />
        ))}
      </div>
      <div className="flex flex-col gap-2 max-w-[280px] md:text-right leading-snug">
        <p className="text-[10px] text-label-light">
          Tracking only ships within terrestrial AIS range (~30nm of coastal receivers). Vessels mid-ocean &mdash; e.g. crossing the Pacific &mdash; won&apos;t appear until they&apos;re near a receiver.
        </p>
        {msoReserve && (
          <p className="text-[10px] text-label-light">
            MSO reserve &middot; as of {formatAsOf(msoReserve.as_of)} &middot;{" "}
            <a
              href={msoReserve.source_url}
              target="_blank"
              rel="noopener noreferrer"
              aria-label="DCCEEW Minimum Stockholding Obligation statistics source"
              className="underline hover:text-label"
            >
              source
            </a>
          </p>
        )}
      </div>
    </div>
  );
}
