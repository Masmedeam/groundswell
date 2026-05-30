import "./globals.css";
import type { Metadata } from "next";
import { Inter, Source_Serif_4 } from "next/font/google";

// Mirror the pitch PDF type stack: Inter for body / UI, Source Serif 4
// for editorial headings + metro names. CSS variables consumed by
// tailwind.config.ts (font-sans, font-serif).
const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const sourceSerif = Source_Serif_4({
  subsets: ["latin"],
  variable: "--font-serif",
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "HomeStar",
  description: "Rental market intelligence",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${sourceSerif.variable}`}>
      <body>{children}</body>
    </html>
  );
}
