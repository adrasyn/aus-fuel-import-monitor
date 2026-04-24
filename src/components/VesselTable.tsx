"use client";

import { useState } from "react";
import type { Vessel } from "@/lib/types";

interface VesselTableProps {
  vessels: Vessel[];
  selectedImo: string | null;
  onSelectVessel: (imo: string | null) => void;
  snapshotTimestamp: string;
}

type SortKey = "name" | "ship_type" | "destination" | "cargo_litres" | "vessel_class" | "last_update";
type SortDir = "asc" | "desc";

const STALE_THRESHOLD_DAYS = 7;
const MS_PER_DAY = 86_400_000;

function ageDays(lastPing: string, referenceIso: string): number | null {
  if (!lastPing || !referenceIso) return null;
  const last = Date.parse(lastPing);
  const ref = Date.parse(referenceIso);
  if (Number.isNaN(last) || Number.isNaN(ref)) return null;
  return Math.max(0, (ref - last) / MS_PER_DAY);
}

function formatAge(days: number | null): string {
  if (days === null) return "—";
  if (days < 1) return "today";
  const whole = Math.round(days);
  return `${whole}d ago`;
}

export default function VesselTable({ vessels, selectedImo, onSelectVessel, snapshotTimestamp }: VesselTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("cargo_litres");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const handleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  };

  const sorted = [...vessels].sort((a, b) => {
    if (sortKey === "last_update") {
      // Sort by raw timestamp (lexicographic ISO compare = chronological)
      const cmp = String(a.last_position_update).localeCompare(String(b.last_position_update));
      return sortDir === "asc" ? cmp : -cmp;
    }
    const aVal = a[sortKey] ?? "";
    const bVal = b[sortKey] ?? "";
    const cmp = typeof aVal === "number" && typeof bVal === "number"
      ? aVal - bVal
      : String(aVal).localeCompare(String(bVal));
    return sortDir === "asc" ? cmp : -cmp;
  });

  const arrow = (key: SortKey) =>
    sortKey === key ? (sortDir === "asc" ? " \u25B2" : " \u25BC") : "";

  const marineTrafficUrl = (imo: string) =>
    imo ? `https://www.marinetraffic.com/en/ais/details/ships/imo:${imo}` : "#";

  return (
    <div className="border border-border overflow-x-auto h-[420px] md:h-[520px] min-h-[300px] overflow-y-auto">
      <table className="w-full text-[11px] min-w-[500px]">
        <thead>
          <tr className="bg-panel border-b border-border text-[9px] uppercase tracking-label text-label font-semibold">
            <th className="text-left px-3 py-2 cursor-pointer" onClick={() => handleSort("name")}>Vessel{arrow("name")}</th>
            <th className="text-left px-3 py-2 cursor-pointer" onClick={() => handleSort("ship_type")}>Type{arrow("ship_type")}</th>
            <th className="text-left px-3 py-2 cursor-pointer" onClick={() => handleSort("destination")}>Dest.{arrow("destination")}</th>
            <th className="text-right px-3 py-2 cursor-pointer" onClick={() => handleSort("cargo_litres")}>Est. cargo{arrow("cargo_litres")}</th>
            <th className="text-left px-3 py-2 cursor-pointer" onClick={() => handleSort("vessel_class")}>Class{arrow("vessel_class")}</th>
            <th className="text-right px-3 py-2 cursor-pointer" onClick={() => handleSort("last_update")}>Last seen{arrow("last_update")}</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((v) => {
            const days = ageDays(v.last_position_update, snapshotTimestamp);
            const isStale = days !== null && days > STALE_THRESHOLD_DAYS;
            const staleTitle = isStale
              ? `Position last reported ${Math.round(days)} days ago — vessel may have arrived undetected.`
              : undefined;
            return (
            <tr
              key={v.mmsi}
              className={`border-b border-border/50 cursor-pointer hover:bg-panel/50 transition-colors ${
                v.imo === selectedImo ? "bg-panel" : ""
              } ${v.is_ballast ? "opacity-40" : ""}`}
              onClick={() => onSelectVessel(v.imo === selectedImo ? null : v.imo)}
            >
              <td className="px-3 py-1 font-medium">
                {v.imo ? (
                  <a href={marineTrafficUrl(v.imo)} target="_blank" rel="noopener noreferrer"
                    className="hover:underline" onClick={(e) => e.stopPropagation()}>
                    {v.name || "Unknown"}
                  </a>
                ) : (v.name || "Unknown")}
              </td>
              <td className={`px-3 py-1 ${v.ship_type === "crude" ? "text-crude" : "text-product"}`}>
                {v.is_ballast ? "Ballast (empty)" : v.ship_type === "crude" ? "Crude" : "Product"}
              </td>
              <td className="px-3 py-1">{v.destination || "—"}</td>
              <td className="px-3 py-1 text-right whitespace-nowrap">
                {(v.cargo_litres / 1_000_000).toFixed(0)}M L
                {v.draught_missing && <span className="text-label-light" title="Draught data unavailable"> *</span>}
              </td>
              <td className="px-3 py-1">{v.vessel_class}</td>
              <td
                className={`px-3 py-1 text-right whitespace-nowrap ${
                  isStale ? "italic text-label-light" : "text-label"
                }`}
                title={staleTitle}
              >
                {formatAge(days)}
              </td>
            </tr>
            );
          })}
          {sorted.length === 0 && (
            <tr>
              <td colSpan={6} className="px-3 py-8 text-center text-label-light">
                No vessels currently tracked
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
