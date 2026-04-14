"use client";

import { useState } from "react";
import type { Vessel } from "@/lib/types";
import VesselMap from "./VesselMap";
import VesselTable from "./VesselTable";

interface DashboardGridProps {
  vessels: Vessel[];
}

export default function DashboardGrid({ vessels }: DashboardGridProps) {
  const [selectedImo, setSelectedImo] = useState<string | null>(null);

  return (
    <div className="flex flex-col md:flex-row gap-5 mb-6">
      <div className="md:flex-shrink-0">
        <p className="text-[10px] uppercase tracking-label text-label mb-2">
          Vessels in transit
        </p>
        <div className="aspect-square md:w-[520px] md:h-[520px] md:aspect-auto">
          <VesselMap
            vessels={vessels}
            selectedImo={selectedImo}
            onSelectVessel={setSelectedImo}
          />
        </div>
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[10px] uppercase tracking-label text-label mb-2">
          Vessel details
        </p>
        <VesselTable
          vessels={vessels}
          selectedImo={selectedImo}
          onSelectVessel={setSelectedImo}
        />
      </div>
    </div>
  );
}
