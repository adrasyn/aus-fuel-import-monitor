import type { Snapshot } from "@/lib/types";

interface HeaderProps {
  snapshot: Snapshot;
  totalLitres: number;
  vesselCount: number;
}

export default function Header({ snapshot, totalLitres, vesselCount }: HeaderProps) {
  const litresFormatted =
    totalLitres >= 1_000_000_000
      ? `${(totalLitres / 1_000_000_000).toFixed(1)} billion litres`
      : `${(totalLitres / 1_000_000).toFixed(0)} million litres`;

  const timestamp = snapshot.timestamp
    ? new Date(snapshot.timestamp).toLocaleDateString("en-AU", {
        day: "numeric",
        month: "long",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        timeZone: "Australia/Sydney",
        timeZoneName: "short",
      })
    : "No data available";

  return (
    <header className="border-b-[2.5px] border-border-heavy pb-3 mb-6">
      <p className="text-[10px] uppercase tracking-label text-label mb-1">
        Australian Fuel Import Monitor
      </p>
      <div className="flex justify-between items-baseline gap-8">
        <h1 className="font-headline text-2xl md:text-3xl leading-tight">
          {vesselCount} tankers carrying an estimated {litresFormatted} of fuel
          are en route to Australia
        </h1>
        <div className="text-[10px] text-label-light whitespace-nowrap text-right hidden sm:block leading-snug">
          <p>Updated daily at 6am AEST</p>
          <p>Last updated {timestamp}</p>
        </div>
      </div>
      <div className="text-[10px] text-label-light mt-1 sm:hidden leading-snug">
        <p>Updated daily at 6am AEST</p>
        <p>Last updated {timestamp}</p>
      </div>
    </header>
  );
}
