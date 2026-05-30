import type { Config } from "tailwindcss";

// Design tokens mirror the submission pitch PDF (pitch.html CSS variables)
// so landing + pitch read as the same brand. Font families are wired to
// the next/font CSS variables (--font-sans, --font-serif) loaded in
// app/layout.tsx.
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ground: {
          DEFAULT: "#10644C",
          soft: "#E7F0EC",
          deep: "#0B4A37",
          ink: "#0E1513",
        },
        // Editorial ink tints — match pitch PDF --ink-soft / --ink-faint
        // for body copy + captions on the cream background.
        "ink-soft": "rgba(14, 21, 19, 0.62)",
        "ink-faint": "rgba(14, 21, 19, 0.36)",
        rule: "rgba(14, 21, 19, 0.14)",
        firm: "#15803d",
        cool: "#b91c1c",
        stable: "#a16207",
        cream: "#FAFAF7",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "Inter", "sans-serif"],
        serif: ["var(--font-serif)", "Source Serif 4", "Georgia", "Times New Roman", "serif"],
      },
    },
  },
  plugins: [],
};
export default config;
