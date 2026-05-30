// Pitch page — renders the submission PDF as inline page images.
//
// Why images, not <object data="...pdf">: the browser's PDF viewer chrome
// (toolbar, zoom controls, menu) reads as unbranded and clunky on top of
// the cream/ground design language. Rendering each page as a high-DPI PNG
// inside a styled container gives a clean on-brand presentation with no
// viewer UI.
//
// Page images are pre-rendered from public/pitch.pdf via pdftocairo and
// committed to public/. Single source of truth is still pitch.pdf — the
// PNGs are a derived artifact.
//
// To swap the PDF (e.g. after the Loom demo link is filled in):
//   1. Overwrite app/web/public/pitch.pdf
//   2. From app/web/public/, run:
//      pdftocairo -png -r 200 pitch.pdf pitch-page
//      (produces pitch-page-1.png + pitch-page-2.png)
//   3. Commit all three files together
//
// pdftocairo is from poppler-utils (brew install poppler on macOS).

import Image from "next/image";
import TopNav from "@/components/TopNav";

export const metadata = {
  title: "HomeStar — Submission pitch",
  description:
    "Two-page submission pitch for HomeStar — a demand-side early-warning engine for CRE rental markets, validated across 17 markets.",
};

const PAGE_ASPECT = 1700 / 2200; // pdftocairo -r 200 → 1700×2200 for US Letter

export default function PitchPage() {
  return (
    <main className="min-h-screen bg-cream">
      <TopNav />

      {/* Title block */}
      <section className="mx-auto max-w-3xl px-6 pt-12">
        <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-ground">
          Market intelligence · Submission pitch
        </p>
        <h1 className="mt-4 font-serif text-4xl font-semibold leading-[1.1] tracking-tight text-ground-ink sm:text-[44px]">
          HomeStar — CRE rental-market intelligence
        </h1>
        <p className="mt-5 max-w-2xl text-[15px] leading-relaxed text-ink-soft">
          A demand-side early-warning engine, validated across 17 markets.
          Two-page pitch — methodology, headline numbers, what we tested and
          dropped, and where the Bright Data live layer corroborates the
          historical engine.
        </p>

        {/* Secondary affordances — sit beside the pitch, not above it */}
        <div className="mt-7 flex flex-wrap items-center gap-x-6 gap-y-3 border-t border-rule pt-5">
          <a
            href="/pitch.pdf"
            download="HomeStar-pitch.pdf"
            className="rounded-sm bg-ground px-5 py-2.5 text-[11.5px] font-semibold uppercase tracking-[0.16em] text-white transition hover:bg-ground-deep"
          >
            Download PDF
          </a>
          <a
            href="/pitch.pdf"
            target="_blank"
            rel="noopener"
            className="text-[12px] font-medium text-ground transition hover:text-ground-deep hover:underline underline-offset-4"
          >
            View full PDF →
          </a>
          <span className="ml-auto text-[10.5px] tabular-nums uppercase tracking-[0.14em] text-ink-faint">
            2 pages · PDF · 494 KB
          </span>
        </div>
      </section>

      {/* Inline rendered pages — the actual content */}
      <section className="mx-auto max-w-3xl px-6 pt-10 pb-20">
        <ul className="space-y-8">
          {[1, 2].map((n) => (
            <li
              key={n}
              className="relative overflow-hidden border border-rule bg-white shadow-[0_4px_24px_-12px_rgba(14,21,19,0.18)]"
              style={{ aspectRatio: PAGE_ASPECT }}
            >
              <Image
                src={`/pitch-page-${n}.png`}
                alt={`HomeStar pitch — page ${n} of 2`}
                fill
                priority={n === 1}
                sizes="(min-width: 768px) 720px, 100vw"
                className="object-contain"
              />
              <div className="absolute bottom-3 right-4 text-[10px] font-semibold uppercase tracking-[0.18em] tabular-nums text-ink-faint">
                Page {n} / 2
              </div>
            </li>
          ))}
        </ul>
      </section>

      {/* Footer */}
      <footer className="border-t border-rule">
        <div className="mx-auto max-w-5xl px-6 py-6 text-[11px] text-ink-soft">
          Built on Bright Data Web Unlocker · Anthropic Claude (Sonnet 4.6) · FRED / BLS / Zillow public data
          <br />
          <span className="font-medium text-ground-ink">
            Laurie Sartain · Salim Masmoudi
          </span>
        </div>
      </footer>
    </main>
  );
}
