import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        crude: "#dc2626",
        product: "#1e40af",
        border: "#e2e8f0",
        "border-heavy": "#111827",
        label: "#6b7280",
        "label-light": "#9ca3af",
        panel: "#f8fafc",
      },
      fontFamily: {
        headline: ['"Instrument Serif"', "Georgia", "serif"],
        body: ['"Inter"', "system-ui", "sans-serif"],
      },
      letterSpacing: {
        label: "0.15em",
      },
    },
  },
  plugins: [],
};

export default config;
