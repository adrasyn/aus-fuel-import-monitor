export default function Footer() {
  return (
    <footer className="border-t border-border pt-6 mt-8 pb-8">
      <p className="text-[10px] text-label-light leading-relaxed max-w-3xl">
        This site provides estimates based on publicly available AIS vessel
        tracking data and Australian Government petroleum statistics. Cargo
        volumes are approximations derived from vessel dimensions and draught
        readings. This site is not affiliated with AMSA or the Australian Government.
      </p>
      <p className="text-[10px] text-label-light mt-3">
        Data refreshes daily at 06:00 AEST.
      </p>
      <p className="text-[10px] text-label-light mt-3">
        With love from{" "}
        <a href="https://x.com/jameswilson" target="_blank" rel="noopener noreferrer"
          className="underline hover:text-label">James Wilson</a>
      </p>
    </footer>
  );
}
