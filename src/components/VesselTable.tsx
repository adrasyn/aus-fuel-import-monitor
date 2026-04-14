"use client";

import { useState } from "react";
import type { Vessel } from "@/lib/types";

interface VesselTableProps {
  vessels: Vessel[];
  selectedImo: string | null;
  onSelectVessel: (imo: string | null) => void;
}

type SortKey = "name" | "ship_type" | "destination_parsed" | "cargo_litres" | "vessel_class" | "last_update";
type SortDir = "asc" | "desc";

export default function VesselTable({ vessels, selectedImo, onSelectVessel }: VesselTableProps) {
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
            <th className="text-left px-3 py-2 cursor-pointer" onClick={() => handleSort("destination_parsed")}>Dest.{arrow("destination_parsed")}</th>
            <th className="text-right px-3 py-2 cursor-pointer" onClick={() => handleSort("cargo_litres")}>Est. cargo{arrow("cargo_litres")}</th>
            <th className="text-left px-3 py-2 cursor-pointer" onClick={() => handleSort("vessel_class")}>Class{arrow("vessel_class")}</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((v) => (
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
              <td className="px-3 py-1">{v.destination_parsed || v.destination || "Unknown"}</td>
              <td className="px-3 py-1 text-right whitespace-nowrap">
                {(v.cargo_litres / 1_000_000).toFixed(0)}M L
                {v.draught_missing && <span className="text-label-light" title="Draught data unavailable"> *</span>}
              </td>
              <td className="px-3 py-1">{v.vessel_class}</td>
            </tr>
          ))}
          {sorted.length === 0 && (
            <tr>
              <td colSpan={5} className="px-3 py-8 text-center text-label-light">
                No vessels currently tracked
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
