import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "GroundsWell",
  description: "Demand-side rental market intelligence",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
