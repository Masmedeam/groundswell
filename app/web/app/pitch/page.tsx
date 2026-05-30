// Pitch page — branded landing that embeds the submission PDF + offers
// a direct download. The PDF itself lives at app/web/public/pitch.pdf,
// served by Next at /pitch.pdf. To update the PDF (e.g. after the Loom
// demo is recorded and the link is filled in), just overwrite that one
// asset file and redeploy. No code change.
//
// Uses HomeStar design tokens (ground green, cream bg, serif headings).
// Not server-component-only — could be either since there's no data
// fetch; kept as a default export client-or-server page for simplicity.

import Link from "next/link";
import Image from "next/image";

export const metadata = {
  title: "HomeStar — Submission pitch",
  description:
    "Two-page submission pitch for HomeStar — a demand-side early-warning engine for CRE rental markets, validated across 17 markets.",
};

export default function PitchPage() {
  return (
    <main className="min-h-screen bg-[#FAFAF7]">
      {/* Header band — matches the app's branding */}
      <header className="border-b border-black/[0.06] bg-[#FAFAF7]">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <Link
            href="/"
            className="flex items-center gap-3 transition hover:opacity-80"
            title="Back to the engine"
          >
            <Image
              src="/logo.png"
              alt="HomeStar"
              width={36}
              height={36}
              priority
            />
            <span className="font-sans text-base font-semibold text-ground-ink">
              Home<span className="text-ground">Star</span>
            </span>
          </Link>
          <div className="flex items-center gap-5">
            <a
              href="/pitch.pdf"
              download="HomeStar-pitch.pdf"
              className="rounded-md bg-ground px-4 py-2 text-xs font-semibold text-white hover:opacity-90"
            >
              Download PDF
            </a>
            <Link
              href="/"
              className="text-xs text-black/45 hover:text-ground"
            >
              ← Back to app
            </Link>
          </div>
        </div>
      </header>

      {/* Title block */}
      <section className="mx-auto max-w-5xl px-6 pt-10 pb-6">
        <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-ground">
          Submission pitch · Bright Data hackathon 2026
        </p>
        <h1 className="mt-3 font-serif text-3xl font-semibold leading-tight tracking-tight text-ground-ink sm:text-4xl">
          HomeStar — CRE rental-market intelligence
        </h1>
        <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-black/60">
          A demand-side early-warning engine, validated across 17 markets.
          Two-page pitch — methodology, headline numbers, what we tested and
          dropped, and where the Bright Data live layer corroborates the
          historical engine.
        </p>
      </section>

      {/* Embedded PDF viewer */}
      <section className="mx-auto max-w-5xl px-6 pb-16">
        <div className="overflow-hidden rounded-lg border border-black/10 bg-white shadow-sm">
          <object
            data="/pitch.pdf#view=FitH&toolbar=1"
            type="application/pdf"
            className="block h-[1100px] w-full"
            aria-label="HomeStar submission pitch (PDF)"
          >
            {/* Fallback if browser can't embed PDFs (mobile, some browsers) */}
            <div className="flex flex-col items-center justify-center gap-3 p-12 text-center">
              <p className="text-sm text-black/60">
                Your browser can&apos;t embed the PDF inline.
              </p>
              <a
                href="/pitch.pdf"
                className="rounded-md bg-ground px-4 py-2 text-xs font-semibold text-white hover:opacity-90"
              >
                Open PDF in new tab
              </a>
            </div>
          </object>
        </div>
        <p className="mt-3 text-center text-[11px] text-black/40">
          PDF is also linked from the app header.
          {" "}<a href="/pitch.pdf" className="text-ground hover:underline">
            Direct link: /pitch.pdf
          </a>
        </p>
      </section>

      {/* Footer — matches the app's tone */}
      <footer className="border-t border-black/[0.06] bg-[#FAFAF7]">
        <div className="mx-auto max-w-5xl px-6 py-6 text-[11px] text-black/55">
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
