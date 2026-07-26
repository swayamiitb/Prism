import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // A dark "investigation console" palette.
        ink: {
          950: "#05060a",
          900: "#0a0c14",
          800: "#11141f",
          700: "#1a1f2e",
          600: "#262d40",
          500: "#3a4358",
        },
        neon: {
          cyan: "#22d3ee",
          violet: "#a78bfa",
          green: "#34d399",
          amber: "#fbbf24",
          pink: "#f472b6",
        },
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
