import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  basePath: "/aus-fuel-import-monitor",
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
