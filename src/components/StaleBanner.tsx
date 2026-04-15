interface StaleBannerProps {
  // timestamp is max(last_position_update) across the current in-transit
  // roster — i.e. the freshest ping we have for any tracked vessel. Shifts
  // forward as individual vessels re-broadcast even between pipeline runs.
  timestamp: string;
}

export default function StaleBanner({ timestamp }: StaleBannerProps) {
  if (!timestamp) return null;
  const lastUpdate = new Date(timestamp);
  const now = new Date();
  const hoursAgo = (now.getTime() - lastUpdate.getTime()) / (1000 * 60 * 60);
  if (hoursAgo < 36) return null;

  const formatted = lastUpdate.toLocaleDateString("en-AU", {
    day: "numeric", month: "long", year: "numeric",
    hour: "2-digit", minute: "2-digit",
    timeZone: "Australia/Sydney", timeZoneName: "short",
  });

  return (
    <div className="bg-panel border border-border px-4 py-3 mb-6 text-sm text-label">
      Data last updated {formatted}. Live collection unavailable — showing most recent snapshot.
    </div>
  );
}
