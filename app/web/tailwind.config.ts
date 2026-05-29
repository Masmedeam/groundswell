import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ground: { DEFAULT: "#10644C", soft: "#E7F0EC", ink: "#0E1513" },
        firm: "#15803d",
        cool: "#b91c1c",
        stable: "#a16207",
      },
      fontFamily: {
        sans: ["ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "Inter", "sans-serif"],
      },
    },
  },
  plugins: [],
};
export default config;
