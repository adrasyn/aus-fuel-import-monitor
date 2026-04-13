"use client";

import { useState } from "react";
import type { Vessel } from "@/lib/types";
import VesselMap from "./VesselMap";
interface DashboardGridProps {
  vessels: Vessel[];
}

export default function DashboardGrid({ vessels }: DashboardGridProps) {
  const [selectedImo, setSelectedImo] = useState<string | null>(null);

  return (
    <div className="flex flex-col md:flex-row gap-5 mb-6">
      <div className="md:w-3/5">
        <p className="text-[10px] uppercase tracking-label text-label mb-2">
          Vessels in transit
        </p>
        <VesselMap
          vessels={vessels}
          selectedImo={selectedImo}
          onSelectVessel={setSelectedImo}
        />
      </div>
      <div className="md:w-2/5">
        <p className="text-[10px] uppercase tracking-label text-label mb-2">
          Vessel details
        </p>
        <div className="border border-border h-[400px] md:h-full min-h-[300px] flex items-center justify-center text-label-light text-sm">
          Vessel table placeholder
        </div>
      </div>
    </div>
  );
}
