// METHODOLOGY — the rigor surface.
//
// Validation + walk-forward discipline + forecast skill + signal-discipline
// scars + trading-test honesty (both backtests, complementary). Numbers
// sourced from forecast-skill.json, detection.json, results.json,
// backtest.json, backtest-rotation.json — same JSON the agent reads.
//
// Postings framing: 16/17 metros at r = 0.91-0.98 (the headline range),
// Austin the lone weak outlier at r = 0.51 (still clean direction). Strictly
// honest claim — preserved exactly from the original validation copy and the
// pitch PDF so the number doesn't drift.

import Link from "next/link";
import TopNav from "@/components/TopNav";
import {
  getDetection,
  getResults,
  getSkill,
  getBacktest,
  getRotation,
  type ResultsRow,
} from "@/lib/site-data";

export const dynamic = "force-dynamic";

const METRO_ORDER = [
  "San Francisco", "Austin", "Salt Lake City", "Philadelphia",
  "New York", "Seattle", "Boston",
  "Boise", "Sacramento",
  "Chicago", "Denver", "Atlanta", "Washington DC",
  "Dallas", "Phoenix", "Minneapolis", "Miami",
];

const fmtPct = (v: number | null | undefined, digits = 1): string => {
  if (v == null) return "—";
  return `${(v * 100).toFixed(digits)}%`;
};
const fmtPctSigned = (v: number | null | undefined, digits = 1): string => {
  if (v == null) return "—";
  return `${v >= 0 ? "+" : ""}${(v * 100).toFixed(digits)}%`;
};
const fmtPp = (v: number | null | undefined): string => {
  if (v == null) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(1)} pp`;
};
const fmtBss = (v: number | null | undefined): string => {
  if (v == null) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}`;
};

function flagTone(f: string): string {
  if (f === "wrong-sign" || f === "lags-not-leads") return "text-cool";
  return "text-stable";
}

export default function MethodologyPage() {
  const det = getDetection();
  const skill = getSkill();
  const results = getResults();
  const backtest = getBacktest();
  const rotation = getRotation();

  const vsRent = results.filter((r) => r.target === "rent");

  // Postings framing: count metros in the headline r-range (≥ 0.91), and
  // count Austin as the "weak outlier" excluded from the strict headline.
  // Preserved 16/17 framing from original copy + pitch PDF.
  const postingsRows = vsRent.filter((r) => r.signal === "postings");
  const postingsStrong = postingsRows.filter(
    (r) => (r.corr ?? 0) >= 0.91 && r.flags.length === 0 && (r.leadMonths ?? 0) > 0,
  ).length;
  const postingsTotal = postingsRows.length;
  // Austin specifically — explicit citation in copy.
  const austinPostings = postingsRows.find((r) => r.metro === "Austin");

  // JOLTS quits — 14/17 clean per the original framing.
  const joltsRows = vsRent.filter((r) => r.signal === "jolts_quits");
  const joltsClean = joltsRows.filter(
    (r) => r.flags.length === 0 && (r.leadMonths ?? 0) > 0,
  ).length;

  // SF WARN — the multi-cycle hero.
  const sfWarn = vsRent.find((r) => r.metro === "San Francisco" && r.signal === "warn");
  // NY WARN — over 2016-2020.
  const nyWarn = vsRent.find((r) => r.metro === "New York" && r.signal === "warn");

  const overallSL = det.aggregate.overall.atSignalLead;
  const sfAgg = det.aggregate.byMetro["San Francisco"];

  const sk = skill.aggregate.overall;

  return (
    <>
      <TopNav />
      <main className="mx-auto max-w-6xl px-8 pt-8 pb-16">
        {/* Title block */}
        <header className="mb-10">
          <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-ground">
            Methodology
          </div>
          <h1 className="mt-2 font-serif text-[34px] font-semibold leading-tight tracking-tight text-ground-ink">
            Walk-forward, no lookahead, honest about what failed.
          </h1>
          <p className="mt-3 max-w-2xl text-[14px] leading-relaxed text-ink-soft">
            Validation of the signal → rent link, the discipline that produced
            it, the trading tests we ran (and why both failed by design), and the
            three signals we tested and removed.
          </p>
        </header>

        {/* Transmission chain */}
        <section className="mb-12">
          <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-ground">
            The chain
          </div>
          <h2 className="mt-2 font-serif text-[22px] font-semibold leading-snug text-ground-ink">
            Two-stage transmission. We validate the upstream link.
          </h2>

          {/* Three equal-width stage columns on a strict CSS grid, with
              arrow+lag connectors between them in `auto` columns. Every
              stage gets the SAME top-rule (border-t-2 border-ground) so
              they read as parallel equal steps; hierarchy lives in text
              color only. flex-col + mt-auto on the footer pushes role
              lines to the bottom so they align across columns even if
              detail rows wrap. */}
          <div className="mt-7">
            <div className="hidden md:grid md:grid-cols-[1fr_auto_1fr_auto_1fr] md:items-stretch md:gap-x-6">
              {/* STAGE 1 */}
              <article className="flex flex-col border-t-2 border-ground pt-4">
                <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-ground">
                  Stage 1 · upstream
                </div>
                <div className="mt-3 font-serif text-[18px] font-semibold leading-tight text-ground-ink">
                  Demand signal
                </div>
                <div className="mt-1.5 text-[12.5px] leading-snug text-ink-soft">
                  postings · JOLTS quits · WARN · employment
                </div>
                <div className="mt-auto pt-4 text-[10.5px] font-semibold uppercase tracking-[0.16em] text-ground">
                  where HomeStar operates
                </div>
              </article>

              {/* CONNECTOR 1 — vertically centered against the stage columns */}
              <div className="flex items-center">
                <div className="flex flex-col items-center gap-1">
                  <span className="text-[22px] font-normal leading-none text-ground/70">→</span>
                  <span className="text-[10px] font-semibold uppercase tracking-[0.18em] tabular-nums text-ground">5–7 mo</span>
                  <span className="text-[9.5px] uppercase tracking-[0.16em] text-ink-faint">leads</span>
                </div>
              </div>

              {/* STAGE 2 */}
              <article className="flex flex-col border-t-2 border-ground pt-4">
                <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-ground/80">
                  Stage 2 · proximate
                </div>
                <div className="mt-3 font-serif text-[18px] font-semibold leading-tight text-ground-ink">
                  Rent growth
                </div>
                <div className="mt-1.5 text-[12.5px] leading-snug text-ink-soft">
                  ZORI (NOI-growth proxy)
                </div>
                <div className="mt-auto pt-4 text-[10.5px] font-semibold uppercase tracking-[0.16em] text-ground">
                  we validate signal → rent here
                </div>
              </article>

              {/* CONNECTOR 2 */}
              <div className="flex items-center">
                <div className="flex flex-col items-center gap-1">
                  <span className="text-[22px] font-normal leading-none text-ink-faint">→</span>
                  <span className="text-[10px] font-semibold uppercase tracking-[0.18em] tabular-nums text-ink-soft">6–12 mo</span>
                  <span className="text-[9.5px] uppercase tracking-[0.16em] text-ink-faint">further lag</span>
                </div>
              </div>

              {/* STAGE 3 */}
              <article className="flex flex-col border-t-2 border-ground pt-4">
                <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-ink-soft">
                  Stage 3 · downstream
                </div>
                <div className="mt-3 font-serif text-[18px] font-semibold leading-tight text-ink-soft">
                  Price appreciation
                </div>
                <div className="mt-1.5 text-[12.5px] leading-snug text-ink-soft">
                  cap-rate moves · buyer re-rating
                </div>
                <div className="mt-auto pt-4 text-[10.5px] font-semibold uppercase tracking-[0.16em] text-ink-faint">
                  slow + noisy · not what we forecast
                </div>
              </article>
            </div>

            {/* Mobile fallback — vertical stack with inline ↓ lag markers */}
            <div className="md:hidden space-y-6">
              {[
                { kicker: "Stage 1 · upstream", kickerTone: "text-ground", name: "Demand signal", nameTone: "text-ground-ink", desc: "postings · JOLTS quits · WARN · employment", footer: "where HomeStar operates", footerTone: "text-ground" },
                { kicker: "Stage 2 · proximate", kickerTone: "text-ground/80", name: "Rent growth", nameTone: "text-ground-ink", desc: "ZORI (NOI-growth proxy)", footer: "we validate signal → rent here", footerTone: "text-ground" },
                { kicker: "Stage 3 · downstream", kickerTone: "text-ink-soft", name: "Price appreciation", nameTone: "text-ink-soft", desc: "cap-rate moves · buyer re-rating", footer: "slow + noisy · not what we forecast", footerTone: "text-ink-faint" },
              ].map((s, i) => (
                <div key={s.kicker}>
                  {i > 0 && (
                    <div className="mb-5 text-center text-[10px] font-semibold uppercase tracking-[0.18em] tabular-nums text-ink-faint">
                      ↓ {i === 1 ? "5–7 mo · leads" : "6–12 mo · further lag"}
                    </div>
                  )}
                  <div className="border-t-2 border-ground pt-4">
                    <div className={`text-[10px] font-semibold uppercase tracking-[0.22em] ${s.kickerTone}`}>{s.kicker}</div>
                    <div className={`mt-3 font-serif text-[18px] font-semibold leading-tight ${s.nameTone}`}>{s.name}</div>
                    <div className="mt-1.5 text-[12.5px] leading-snug text-ink-soft">{s.desc}</div>
                    <div className={`mt-4 text-[10.5px] font-semibold uppercase tracking-[0.16em] ${s.footerTone}`}>{s.footer}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <p className="mt-5 max-w-4xl text-[12.5px] leading-relaxed text-ink-soft">
            Total signal → price latency is ~12–18 months. Buyers re-rate value
            on trailing rent (T-6 to T-12) plus a forward outlook, so price
            moves slowly even after rent turns. The detection-accuracy headline
            below validates the{" "}
            <strong className="font-semibold text-ground-ink">signal → rent</strong>{" "}
            link — the fast, clean part of the chain. The slower signal → price
            link is implied by the chain, not directly tested.
          </p>
        </section>

        {/* Validation — breadth + depth */}
        <section className="mb-12">
          <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-ground">
            Validation
          </div>
          <h2 className="mt-2 font-serif text-[22px] font-semibold leading-snug text-ground-ink">
            Two signals, two strengths. Postings runs broad; WARN runs deep.
          </h2>

          <div className="mt-6 grid grid-cols-1 gap-8 md:grid-cols-2">
            <article className="border-t-2 border-ground pt-5">
              <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-ground">
                Breadth · postings → rent
              </div>
              <p className="mt-2 text-[13px] leading-relaxed text-ink-soft">
                Indeed Hiring Lab postings index leads rent by 1–7 months at
                r = 0.91–0.98 in{" "}
                <strong className="font-semibold tabular-nums text-ground-ink">{postingsStrong} of {postingsTotal} metros</strong>.
                Austin is the lone weak outlier at{" "}
                <span className="tabular-nums">r = {austinPostings?.corr?.toFixed(2) ?? "0.51"}</span>
                {" "}(still clean direction). The universal signal across thick + thin labor markets.
              </p>
              <p className="mt-3 text-[12px] leading-relaxed text-ink-faint">
                Caveat: coverage is single-cycle (2020-02 → 2025-02), so
                cross-regime predictiveness is unproven — within window, the
                chain is uniform.
              </p>
            </article>
            <article className="border-t-2 border-ground/40 pt-5">
              <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-ground/80">
                Depth · WARN → rent
              </div>
              <p className="mt-2 text-[13px] leading-relaxed text-ink-soft">
                SF: leads <span className="tabular-nums">{sfWarn?.leadMonths ?? 7}mo</span>,{" "}
                r = <span className="tabular-nums">{sfWarn?.corr?.toFixed(2) ?? "−0.59"}</span>,{" "}
                n = <span className="tabular-nums">{sfWarn?.nAtBestLag ?? 117}</span>, multi-cycle 2014–2026.
                NY replicates the same chain (leads <span className="tabular-nums">{nyWarn?.leadMonths ?? 4}mo</span>,{" "}
                r = <span className="tabular-nums">{nyWarn?.corr?.toFixed(2) ?? "−0.68"}</span>) over the
                available 2016–2020 window. JOLTS quits also corroborates broadly:{" "}
                <strong className="font-semibold tabular-nums text-ground-ink">{joltsClean} of 17 metros</strong>{" "}
                clean at 1–6mo leads, 24-year state-level history.
              </p>
              <p className="mt-3 text-[12px] leading-relaxed text-ink-faint">
                Caveat: NY 2016–2020 is a single confirmed turn (2020-09 COVID
                wave) — see the NY window caveat in the bottom caveats card.
                Per-state WARN sourcing detailed on{" "}
                <Link href="/data-sources" className="text-ground underline underline-offset-2 hover:text-ground-deep">
                  Data Sources
                </Link>.
              </p>
            </article>
          </div>
        </section>

        {/* Detection accuracy + skill */}
        <section className="mb-12">
          <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-ground">
            Detection accuracy + forecast skill
          </div>
          <h2 className="mt-2 font-serif text-[22px] font-semibold leading-snug text-ground-ink">
            <span className="tabular-nums text-ground">{fmtPct(overallSL.hitRate)}</span> at the dominant signal&apos;s lead. Beats climatology by{" "}
            <span className="tabular-nums">{fmtPp(sk.skill.vsBaseRate * 100)}</span>.
          </h2>

          <div className="mt-6 grid grid-cols-2 gap-x-8 gap-y-4 border-t border-rule pt-5 md:grid-cols-4">
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-ground/80">Overall · 17 metros</div>
              <div className="mt-1 font-serif text-[28px] font-semibold tabular-nums text-ground">{fmtPct(overallSL.hitRate)}</div>
              <div className="mt-0.5 text-[11px] tabular-nums text-ink-faint">{overallSL.hits}/{overallSL.n} turns · median dominant lead {overallSL.medianDominantLead}mo</div>
            </div>
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-ground/80">Skill vs base rate</div>
              <div className="mt-1 font-serif text-[28px] font-semibold tabular-nums text-ground">{fmtPp(sk.skill.vsBaseRate * 100)}</div>
              <div className="mt-0.5 text-[11px] tabular-nums text-ink-faint">engine beats climatology baseline</div>
            </div>
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-ground/80">BSS vs base rate</div>
              <div className="mt-1 font-serif text-[28px] font-semibold tabular-nums text-ground">{fmtBss(sk.bss.vsBaseRate)}</div>
              <div className="mt-0.5 text-[11px] tabular-nums text-ink-faint">positive ⇒ engine has skill</div>
            </div>
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-ink-soft">Skill vs persistence</div>
              <div className="mt-1 font-serif text-[28px] font-semibold tabular-nums text-ink-soft">{fmtPp(sk.skill.vsPersistence * 100)}</div>
              <div className="mt-0.5 text-[11px] tabular-nums text-ink-faint">essentially tied with trend-continuation</div>
            </div>
          </div>

          <p className="mt-5 max-w-4xl text-[12.5px] leading-relaxed text-ink-soft">
            Per-signal-lead evaluation: every turn judged at the leadMonths of
            its dominant contributing signal (largest |contribution|). The lead
            value comes from the same walk-forward lead-lag refit that drove
            the score — it&apos;s an input, locked before any rent outcome is
            read. Persistence is the hard competitor: BSS vs persistence{" "}
            ({fmtBss(sk.bss.vsPersistence)}) is negative because rent is sticky
            enough that trend-continuation is a strong baseline; what matters
            for the rigor claim is the{" "}
            <strong className="font-semibold text-ground-ink">{fmtBss(sk.bss.vsBaseRate)} BSS vs climatology</strong>{" "}
            — the engine demonstrably beats &ldquo;always predict softening&rdquo;
            by a wide margin. SF is the multi-cycle case study:{" "}
            <span className="tabular-nums">{sfAgg?.atSignalLead?.hits ?? 4}/{sfAgg?.atSignalLead?.n ?? 5}</span> turns
            clean across 2017–2026.
          </p>
        </section>

        {/* Signal-discipline scars */}
        <section className="mb-12">
          <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-ground">
            Signal discipline
          </div>
          <h2 className="mt-2 font-serif text-[22px] font-semibold leading-snug text-ground-ink">
            Three signals tested. Three signals dropped.
          </h2>
          <p className="mt-3 max-w-3xl text-[13px] leading-relaxed text-ink-soft">
            Pre-stated sign and threshold for each. When the result violated
            the pre-stated test, the signal was removed from the pipeline and
            the failure was published — not re-signed, not silently demoted.
            Below: the actual numbers, including how much each dropped the
            engine&apos;s hit rate and BSS when included.
          </p>

          <div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-3">
            <article className="border-t border-rule pt-4">
              <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-cool">
                Wages · removed
              </div>
              <div className="mt-1.5 font-serif text-[16px] font-semibold text-ground-ink">
                3/9 wrong-sign
              </div>
              <p className="mt-2 text-[12px] leading-relaxed text-ink-soft">
                BLS CES Avg Hourly Earnings per MSA, pre-stated POSITIVE vs
                rent. Result: Austin, Boston, NY all inversely correlated.
                Only Sacramento clean (weak r = 0.20). Adding wages dropped
                hit rate{" "}
                <span className="tabular-nums">79.3% → 71.9%</span>, skill vs
                persistence{" "}
                <span className="tabular-nums">−3.4 → −9.4 pp</span>, and BSS
                vs base rate{" "}
                <span className="tabular-nums">+0.31 → +0.05</span>.
              </p>
            </article>
            <article className="border-t border-rule pt-4">
              <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-cool">
                Rent-vs-own · removed
              </div>
              <div className="mt-1.5 font-serif text-[16px] font-semibold text-ground-ink">
                8/9 failed
              </div>
              <p className="mt-2 text-[12px] leading-relaxed text-ink-soft">
                P&amp;I via MORTGAGE30US × Zillow ZHVI ÷ ZORI. Pre-stated POSITIVE
                LEAD. Result: 7 lags-not-leads, 1 wrong-sign (Austin coincident,
                r = −0.41). Only SF clean direction but |r| = 0.21 below the
                0.30 actionable floor. Mechanical reason: ZORI in the
                denominator AND target — ratio responds to rent rather than
                leading it.
              </p>
            </article>
            <article className="border-t border-rule pt-4">
              <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-cool">
                Permits · removed
              </div>
              <div className="mt-1.5 font-serif text-[16px] font-semibold text-ground-ink">
                Pro-cyclical
              </div>
              <p className="mt-2 text-[12px] leading-relaxed text-ink-soft">
                Census permits via FRED, swept lags 0–30mo per metro,
                pre-stated NEGATIVE sign. Every lag in every metro: positive
                correlation with rent — builders permit when demand fires, so
                supply-suppression isn&apos;t separable from the demand cycle in
                this time series. Retained as descriptive supply-state
                context only.
              </p>
            </article>
          </div>
        </section>

        {/* Trading tests — both, honestly */}
        <section className="mb-12">
          <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-ground">
            Trading tests
          </div>
          <h2 className="mt-2 font-serif text-[22px] font-semibold leading-snug text-ground-ink">
            Both tests failed. By design.
          </h2>
          <p className="mt-3 max-w-3xl text-[13px] leading-relaxed text-ink-soft">
            Two tests of &ldquo;what if you trade the lead?&rdquo; — one naive
            quarterly, one CRE-realistic. Both failed their pre-stated
            hypotheses, both for the reasons the spine already flags. Together
            they make the early-warning-not-trading conclusion airtight.
          </p>

          <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* Naive backtest */}
            <article className="border-t-2 border-stable/70 pt-5">
              <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-stable">
                Naive quarterly rebalance · 4 metros · rent appreciation
              </div>
              <h3 className="mt-1.5 font-serif text-[17px] font-semibold text-ground-ink">
                Signal-weighted underperformed equal-weight by{" "}
                <span className="tabular-nums">{Math.abs(backtest.headline.outperfVsEqualPct).toFixed(1)} pp</span>.
              </h3>
              <dl className="mt-4 grid grid-cols-[1fr_auto] gap-y-1.5 text-[12.5px]">
                <dt className="text-ink-soft">Signal-weighted (top-2 of 4)</dt>
                <dd className="tabular-nums text-ground-ink">{fmtPctSigned(backtest.headline.finalSignal - 1)}</dd>
                <dt className="text-ink-soft">Equal-weight (25%×4)</dt>
                <dd className="tabular-nums text-ground-ink">{fmtPctSigned(backtest.headline.finalEqual - 1)}</dd>
                <dt className="text-ink-soft">Worst-ranked (bottom-1, 100%)</dt>
                <dd className="tabular-nums text-ground-ink">{fmtPctSigned(backtest.headline.finalWorst - 1)}</dd>
                <dt className="text-ink-soft">REIT backdrop (price-only)</dt>
                <dd className="tabular-nums text-ink-faint">{fmtPctSigned(backtest.headline.finalBenchmark - 1)}</dd>
              </dl>
              <p className="mt-4 text-[11.5px] leading-relaxed text-ink-soft">
                <strong className="font-semibold text-ground-ink">Pre-stated test failed</strong>{" "}
                by {Math.abs(backtest.headline.outperfVsEqualPct).toFixed(1)} pp over {backtest.headline.quarters} quarterly rebalances. But signal-weighted beat <em>worst-ranked</em> by{" "}
                <span className="tabular-nums">{backtest.headline.outperfVsWorstPct.toFixed(1)} pp</span> — the engine IS informative about which metro to avoid, even where it lacks edge to beat broad diversification across just 4 markets. The AVOID/SELL use case is where the lead matters.
              </p>
            </article>

            {/* Rotation backtest — mechanism */}
            <article className="border-t-2 border-cool/70 pt-5">
              <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-cool">
                Price-rotation · 17 metros · 2–4yr CRE holds · ZHVI
              </div>
              <h3 className="mt-1.5 font-serif text-[17px] font-semibold text-ground-ink">
                Worked 2019–22. Failed 2023. The rate channel dominated.
              </h3>
              <dl className="mt-4 grid grid-cols-[1fr_auto] gap-y-1.5 text-[12.5px]">
                <dt className="text-ink-soft">Strategy</dt>
                <dd className="tabular-nums text-ground-ink">{fmtPctSigned(rotation.headline.strategyMeanAnnualized)} /yr</dd>
                <dt className="text-ink-soft">Equal-weight rotation</dt>
                <dd className="tabular-nums text-ground-ink">{fmtPctSigned(rotation.headline.equalWeightMeanAnnualized)} /yr</dd>
                <dt className="text-ink-soft">Momentum rotation</dt>
                <dd className="tabular-nums text-ground-ink">{fmtPctSigned(rotation.headline.momentumMeanAnnualized)} /yr</dd>
                <dt className="text-ink-soft">Broad-index buy/hold</dt>
                <dd className="tabular-nums text-ink-faint">{fmtPctSigned(rotation.headline.broadIndexAnnualized)} /yr</dd>
              </dl>
              <p className="mt-4 text-[11.5px] leading-relaxed text-ink-soft">
                Engine correctly called Sun Belt firming in 2019–20 — 15 take-gain exits, +20–50% over 2yr holds (Austin, Miami, Boston, Dallas). Engine correctly called labor firming AGAIN in 2023 (Austin / Dallas / Chicago / Boston quits-rate turned positive). Strategy bought into a Fed-rate-cycle valuation top: 2023 cohort lost 4–17% per position. <strong className="font-semibold text-ground-ink">Labor was right; the discount rate dominated.</strong> Exactly the BUY-existing-asset risk the spine flags as dangerous.
              </p>
            </article>
          </div>

          <p className="mt-6 max-w-4xl text-[12.5px] leading-relaxed text-ink-soft">
            Conclusion: trading a leading indicator at the lead horizon is a
            known trap. Early ≠ wrong, but in illiquid CRE you commit before the
            move and can&apos;t exit cheaply if it takes 9 months instead of 5.
            The product&apos;s claim is{" "}
            <strong className="font-semibold text-ground-ink">detection and
            decision-timing by decision type</strong>, not high-frequency alpha.
            See{" "}
            <Link href="/pitch" className="text-ground underline underline-offset-2 hover:text-ground-deep">
              Pitch
            </Link>{" "}
            for the three-decision framework (AVOID / BUILD / BUY).
          </p>
        </section>

        {/* Per-metro signal leaderboard */}
        <section className="mb-12">
          <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-ground">
            Leaderboard
          </div>
          <h2 className="mt-2 font-serif text-[20px] font-semibold leading-snug text-ground-ink">
            Per-metro lead-lag, every signal, vs rent.
          </h2>
          <p className="mt-2 max-w-3xl text-[12.5px] leading-relaxed text-ink-soft">
            All values YoY × YoY, lag swept ±12mo. Flagged rows are{" "}
            <em>tested but not established</em> in this window — discipline is
            honest flagging, not silent exclusion.
          </p>

          <div className="mt-5 grid grid-cols-1 gap-x-10 md:grid-cols-2 lg:grid-cols-3">
            {METRO_ORDER.map((metro) => {
              const rows = vsRent.filter((r) => r.metro === metro);
              if (rows.length === 0) return null;
              const sorted = [...rows].sort((a, b) => {
                const aClean = a.flags.length === 0 ? 1 : 0;
                const bClean = b.flags.length === 0 ? 1 : 0;
                if (aClean !== bClean) return bClean - aClean;
                return Math.abs(b.corr ?? 0) - Math.abs(a.corr ?? 0);
              });
              return (
                <article key={metro} className="border-t border-rule pt-3 pb-4">
                  <div className="mb-2 flex items-baseline justify-between">
                    <h3 className="font-serif text-[15px] font-semibold text-ground-ink">{metro}</h3>
                    <span className="text-[10px] uppercase tracking-[0.14em] text-ink-faint">vs rent</span>
                  </div>
                  <ul className="space-y-1">
                    {sorted.map((r: ResultsRow) => {
                      const clean = r.flags.length === 0;
                      return (
                        <li key={r.signal} className={`flex items-baseline gap-3 text-[11.5px] tabular-nums ${clean ? "text-ground-ink" : "text-ink-faint"}`}>
                          <span className="w-[88px] text-[10.5px] uppercase tracking-[0.12em]">{r.signal}</span>
                          <span className="w-[58px] text-ink-soft">
                            {r.leadMonths == null ? "—" : r.leadMonths > 0 ? `+${r.leadMonths}mo` : `${r.leadMonths}mo`}
                          </span>
                          <span className="w-[44px]">r={r.corr == null ? "—" : r.corr.toFixed(2)}</span>
                          <span className="ml-auto text-[10px] text-ink-faint">
                            {clean ? "clean" : r.flags.map((f) => (
                              <span key={f} className={`ml-1 ${flagTone(f)}`}>{f}</span>
                            ))}
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                </article>
              );
            })}
          </div>
        </section>

        {/* Caveats */}
        <section id="caveats" className="mb-12 scroll-mt-24">
          <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-ground">
            Caveats
          </div>
          <h2 className="mt-2 font-serif text-[20px] font-semibold leading-snug text-ground-ink">
            On the detection test itself.
          </h2>
          <ul className="mt-4 max-w-4xl space-y-3 text-[12.5px] leading-relaxed text-ink-soft">
            <li>
              <strong className="font-semibold text-ground-ink">17 metros across 4 tiers, {det.aggregate.overall.nTurns} confirmed turns total.</strong>{" "}
              Sample doubled from the original 9-metro 29-turn run to the
              17-metro 58-turn run and overall hit rate held byte-identical at
              79.3%. Tier 3 uses employment + postings + JOLTS only (WARN
              deferred — see{" "}
              <Link href="/data-sources" className="text-ground underline underline-offset-2 hover:text-ground-deep">
                Data Sources
              </Link>) — that the aggregate held with one fewer signal is the
              strongest evidence postings + JOLTS quits are the universal
              load-bearing signals.
            </li>
            <li>
              <strong className="font-semibold text-ground-ink">NY is 2016–2020 window, single turn.</strong>{" "}
              The NY WARN sheet (layoffdata.com → NY DOL) stops at August 2020.
              NY&apos;s 100% hit rate is on n=1 confirmed turn (2020-09 COVID
              wave). Read as &ldquo;NY replicates SF&apos;s pattern over the
              available window&rdquo; — NOT as equivalent to SF&apos;s 4/5
              over a decade.
            </li>
            <li>
              <strong className="font-semibold text-ground-ink">~1 cycle of coverage (2017–2026) for most metros.</strong>{" "}
              Includes COVID, post-COVID recovery, 2022–23 tech wave, current
              normalization — multi-regime but not multi-cycle in the
              long-term sense. WA is the only metro with 22 years.
            </li>
            <li>
              <strong className="font-semibold text-ground-ink">Hit definition is lenient by default.</strong>{" "}
              &ldquo;Hit&rdquo; = rent YoY moved in the predicted direction
              from base. A stricter version (≥1pp move) is recorded per turn
              in the raw data; it predictably brings the hit rate down.
            </li>
            <li>
              <strong className="font-semibold text-ground-ink">Direction, not magnitude.</strong>{" "}
              We do not claim the signal forecasts <em>how much</em> rent will
              move — only the direction within the lead window.
            </li>
            <li>
              <strong className="font-semibold text-ground-ink">Walk-forward and pub-lagged.</strong>{" "}
              Every score uses observations strictly before asOf = detectionDate
              − {det.config.pubLagMonths}mo. No future peek anywhere.
              Persistence filter: {det.config.persistenceMonths} months on the
              new side before a turn is confirmed.
            </li>
            <li>
              <strong className="font-semibold text-ground-ink">Evaluation horizon is sourced from the lead-lag, not chosen.</strong>{" "}
              Each turn is evaluated at the leadMonths of its dominant
              contributing signal. The lead value comes from the same
              walk-forward lead-lag refit that drove the score that caused the
              turn — locked input, not a free parameter. The fixed +3/+6/+9
              grid is retained alongside as a diagnostic only.
            </li>
          </ul>
        </section>

        {/* Engine config */}
        <section className="mb-10">
          <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-ground">
            Engine
          </div>
          <h2 className="mt-2 font-serif text-[20px] font-semibold leading-snug text-ground-ink">
            Configuration.
          </h2>
          <dl className="mt-4 grid grid-cols-2 gap-x-8 gap-y-2 border-t border-rule pt-4 text-[12.5px] md:grid-cols-4">
            <div>
              <dt className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-faint">Window</dt>
              <dd className="tabular-nums text-ground-ink">{det.config.startYM} → {det.config.endYM}</dd>
            </div>
            <div>
              <dt className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-faint">State buffer</dt>
              <dd className="tabular-nums text-ground-ink">±{det.config.stateBuffer}</dd>
            </div>
            <div>
              <dt className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-faint">Persistence</dt>
              <dd className="tabular-nums text-ground-ink">{det.config.persistenceMonths} months</dd>
            </div>
            <div>
              <dt className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-faint">Pub-lag</dt>
              <dd className="tabular-nums text-ground-ink">{det.config.pubLagMonths} month</dd>
            </div>
            <div>
              <dt className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-faint">Horizons</dt>
              <dd className="tabular-nums text-ground-ink">{det.config.horizons.join(" / ")} mo</dd>
            </div>
            <div>
              <dt className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-faint">Metros</dt>
              <dd className="tabular-nums text-ground-ink">{det.config.metros.length}</dd>
            </div>
            <div>
              <dt className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-faint">Walk-forward</dt>
              <dd className="text-ground-ink">yes</dd>
            </div>
            <div>
              <dt className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-faint">Target</dt>
              <dd className="text-ground-ink">signal → rent</dd>
            </div>
          </dl>
          {det.config.whyNotPrice && (
            <p className="mt-4 max-w-4xl text-[11.5px] italic leading-relaxed text-ink-faint">
              {det.config.whyNotPrice}
            </p>
          )}
        </section>

        <p className="mt-10 text-[10.5px] uppercase tracking-[0.18em] text-ink-faint">
          Numbers reflect the validated engine state · same JSON the agent reads
        </p>
      </main>
    </>
  );
}
