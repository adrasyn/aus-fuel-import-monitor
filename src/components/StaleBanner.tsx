export default function StaleBanner() {
  return (
    <div className="bg-panel border border-border px-4 py-3 mb-6 text-sm text-label space-y-2">
      <p>
        Note: The AIS service we use, aisstream.io, was not accessible for 21
        May and 22 May due to their SSL certificate expiring. There is no data
        available for those dates.
      </p>
      <p>
        We&rsquo;ve added a workaround but aisstream.io&rsquo;s service still
        appears to be degraded. We&rsquo;ll keep you posted.
      </p>
    </div>
  );
}
