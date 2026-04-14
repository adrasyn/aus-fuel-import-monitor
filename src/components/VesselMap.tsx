"use client";

import { useEffect, useState } from "react";
import type { Vessel } from "@/lib/types";

interface VesselMapProps {
  vessels: Vessel[];
  selectedImo: string | null;
  onSelectVessel: (imo: string | null) => void;
}

export default function VesselMap({ vessels, selectedImo, onSelectVessel }: VesselMapProps) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [MapComponents, setMapComponents] = useState<{ rl: any; L: any } | null>(null);

  useEffect(() => {
    // Dynamic import to avoid SSR issues with Leaflet
    Promise.all([
      import("react-leaflet"),
      import("leaflet"),
      // @ts-expect-error -- CSS import handled at runtime by bundler
      import("leaflet/dist/leaflet.css"),
    ]).then(([rl, L]) => {
      setMapComponents({ rl, L: L.default });
    });
  }, []);

  if (!MapComponents) {
    return (
      <div className="bg-panel border border-border h-[400px] md:h-full min-h-[300px] flex items-center justify-center">
        <span className="text-label-light text-sm">Loading map...</span>
      </div>
    );
  }

  const { MapContainer, TileLayer, CircleMarker, Popup } = MapComponents.rl;
  const center: [number, number] = [-20, 130];

  return (
    <MapContainer
      center={center}
      zoom={4}
      className="h-[400px] md:h-full min-h-[300px] w-full border border-border"
      scrollWheelZoom={true}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
      />
      {vessels.map((vessel) => {
        if (vessel.lat === 0 && vessel.lon === 0) return null;
        const isSelected = vessel.imo === selectedImo;
        const color = vessel.ship_type === "crude" ? "#dc2626" : "#1e40af";
        const radius = isSelected ? 8 : 5;

        const lastSeenMs = vessel.last_position_update
          ? Date.now() - new Date(vessel.last_position_update).getTime()
          : 0;
        const staleHours = lastSeenMs / 3_600_000;
        const isStale = staleHours > 24;

        const ballastFactor = vessel.is_ballast ? 0.3 : 1;
        const staleFactor = isStale ? 0.4 : 1;
        const opacity = ballastFactor * staleFactor;

        const lastSeenLabel = (() => {
          if (!isStale) return null;
          const days = Math.floor(staleHours / 24);
          if (days >= 1) return `Last seen ${days}d ago`;
          return `Last seen ${Math.floor(staleHours)}h ago`;
        })();

        return (
          <CircleMarker
            key={vessel.mmsi}
            center={[vessel.lat, vessel.lon]}
            radius={radius}
            pathOptions={{
              color: isSelected ? "#111827" : color,
              fillColor: color,
              fillOpacity: opacity,
              weight: isSelected ? 2 : 1,
            }}
            eventHandlers={{ click: () => onSelectVessel(vessel.imo) }}
          >
            <Popup>
              <div className="font-body text-xs">
                <p className="font-semibold">{vessel.name || "Unknown"}</p>
                <p className="text-label">
                  {vessel.vessel_class} &middot;{" "}
                  <span className={vessel.ship_type === "crude" ? "text-crude" : "text-product"}>
                    {vessel.ship_type === "crude" ? "Crude" : "Product"}
                  </span>
                </p>
                <p>Est. cargo: {(vessel.cargo_litres / 1_000_000).toFixed(0)}M L{vessel.draught_missing && " *"}</p>
                <p>Dest: {vessel.destination_parsed || vessel.destination || "Unknown"}</p>
                <p>Speed: {vessel.speed.toFixed(1)} kn</p>
                {vessel.is_ballast && <p className="text-label-light italic">Ballast (empty)</p>}
                {lastSeenLabel && (
                  <p className="text-label-light italic">{lastSeenLabel}</p>
                )}
              </div>
            </Popup>
          </CircleMarker>
        );
      })}
    </MapContainer>
  );
}
