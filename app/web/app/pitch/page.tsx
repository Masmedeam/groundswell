// Pitch page — branded landing for the submission PDF.
// We deliberately do NOT embed the PDF inline (browser viewer chrome —
// toolbar, zoom, menu — looks unbranded). Instead we surface a clean
// branded card with a primary Download button and a secondary
// "View in browser" link that opens /pitch.pdf in a new tab (the
// browser's native viewer takes over outside our brand).
//
// To swap the PDF: overwrite app/web/public/pitch.pdf and redeploy.
// No code change.

import TopNav from "@/components/TopNav";

export const metadata = {
  title: "HomeStar — Submission pitch",
  description:
    "Two-page submission pitch for HomeStar — a demand-side early-warning engine for CRE rental markets, validated across 17 markets.",
};

export default function PitchPage() {
  return (
    <main className="min-h-screen bg-cream">
      <TopNav />

      {/* Title block */}
      <section className="mx-auto max-w-3xl px-6 pt-16">
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
      </section>

      {/* Branded download card — no embedded viewer */}
      <section className="mx-auto max-w-3xl px-6 pt-10 pb-20">
        <div className="border-t border-ground/80 bg-white/70 px-8 py-7">
          <div className="flex items-baseline justify-between gap-4">
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-ground/80">
                Document
              </div>
              <div className="mt-1.5 font-serif text-[18px] font-semibold text-ground-ink">
                HomeStar pitch
              </div>
            </div>
            <div className="text-right text-[11px] tabular-nums text-ink-faint">
              2 pages · PDF · 494 KB
            </div>
          </div>

          <div className="mt-7 flex flex-wrap items-center gap-x-6 gap-y-3">
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
              View in browser →
            </a>
          </div>

          <p className="mt-7 border-t border-rule pt-4 text-[11px] text-ink-faint">
            Also linked from the app header. Direct URL:{" "}
            <a
              href="/pitch.pdf"
              className="text-ground hover:underline"
              target="_blank"
              rel="noopener"
            >
              /pitch.pdf
            </a>
          </p>
        </div>
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
