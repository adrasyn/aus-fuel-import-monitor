export default function StaleBanner() {
  return (
    <div className="bg-panel border border-border px-4 py-3 mb-6 text-sm text-label space-y-2">
      <p>
        Note: The AIS service we use, aisstream.io, was not accessible for 21
        May and 22 May due to their SSL certificate expiring. There is no data
        available for those dates.
      </p>
      <p>
        We've added a workaround but aisstream.io's service still appears to be
        degraded and isn't allowing us the full 30 minutes listening period
        we've previously relied on. We'll keep you posted as we learn more.
      </p>
    </div>
  );
}
