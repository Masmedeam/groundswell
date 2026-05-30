// DATA SOURCES — the transparency layer.
//
// Ported from the original repo's `/` Gather page with the institutional
// design language applied. Honest framing on convergence: the historical
// engine and the live Bright Data concession layer are TWO genuinely
// independent data sources converging on the same Sun Belt cluster. The
// rotation backtest was deliberately removed from the convergence
// callout because it shares data with the lead-lag engine (same labor
// pipeline, different analysis) — framing it as a third independent
// methodology would overstate.

import Link from "next/link";
import TopNav from "@/components/TopNav";
import {
  getListingsLive,
  getDatasetMeta,
  ageString,
  fmtKB,
  type ListingsMetro,
} from "@/lib/site-data";

export const dynamic = "force-dynamic";

const METRO_ORDER = [
  "San Francisco", "Austin", "Salt Lake City", "Philadelphia",
  "New York", "Seattle", "Boston",
  "Boise", "Sacramento",
  "Chicago", "Denver", "Atlanta", "Washington DC",
  "Dallas", "Phoenix", "Minneapolis", "Miami",
];

interface WarnSourcing {
  source: string;
  window: string;
  note?: string;
  direct: boolean;
}
const WARN_SOURCING: Record<string, WarnSourcing> = {
  "San Francisco":  { source: "CA EDD xlsx + 11 archive PDFs (Claude PDF extraction)", window: "2014-07 → 2026-05", note: "Multi-cycle, the proven metro", direct: true },
  "Austin":         { source: "TX TWC annual xlsx", window: "2022-07 → 2026-04", note: "Recent 4yr only — full TX backfill deferred", direct: true },
  "Salt Lake City": { source: "UT DWS yearly HTML tables", window: "2022-01 → 2026-02", direct: true },
  "Philadelphia":   { source: "PA L&I HTML (Claude extraction, notice_date imputed effective −60d)", window: "2023-01 → 2026-05", direct: true },
  "New York":       { source: "layoffdata.com NY sheet (NY DOL aggregate)", window: "2006-07 → 2020-08", note: "Sheet stops at Aug 2020 — single confirmed turn 2020-09 (COVID wave)", direct: false },
  "Seattle":        { source: "layoffdata.com WA sheet (WA ESD aggregate)", window: "2004-01 → 2026-05", note: "22yr, longest history of any metro", direct: false },
  "Boston":         { source: "layoffdata.com MA sheet (mass.gov weekly CSVs)", window: "2019-07 → 2026-05", note: "mass.gov blocks bulk; BD blocks .gov by policy", direct: false },
  "Boise":          { source: "layoffdata.com ID sheet (IDOL aggregate)", window: "2009-01 → 2026-01", note: "ID has no state mini-WARN — federal-only filings, structurally thin", direct: false },
  "Sacramento":     { source: "CA EDD xlsx + 11 archive PDFs (re-extracted for Sac MSA counties)", window: "2014-07 → 2026-05", note: "Same coverage as SF — chain doesn't replicate (signals lag rent)", direct: true },
  "Chicago":        { source: "WARN deferred (Phase N)", window: "n/a", note: "Engine uses employment + postings + JOLTS quits", direct: false },
  "Denver":         { source: "WARN deferred (Phase N)", window: "n/a", note: "Engine uses employment + postings + JOLTS quits", direct: false },
  "Atlanta":        { source: "WARN deferred (Phase N)", window: "n/a", note: "Engine uses employment + postings + JOLTS quits", direct: false },
  "Washington DC":  { source: "WARN deferred (Phase N)", window: "n/a", note: "Engine uses employment + postings + JOLTS quits", direct: false },
  "Dallas":         { source: "WARN deferred (Phase N)", window: "n/a", note: "Shares TX-state JOLTS with Austin", direct: false },
  "Phoenix":        { source: "WARN deferred (Phase N)", window: "n/a", note: "Engine uses employment + postings + JOLTS quits", direct: false },
  "Minneapolis":    { source: "WARN deferred (Phase N)", window: "n/a", note: "Engine uses employment + postings + JOLTS quits", direct: false },
  "Miami":          { source: "WARN deferred (Phase N)", window: "n/a", note: "Engine uses employment + postings + JOLTS quits", direct: false },
};

export default function DataSourcesPage() {
  const listings = getListingsLive();
  const datasets = getDatasetMeta();

  // Convergence stats — pull genuinely independent reads only.
  const concessionRows = Object.entries(listings.metros)
    .map(([metro, m]): { metro: string; share: number | null } | null => {
      if (!("concessionShare" in m)) return null;
      return { metro, share: (m as ListingsMetro).concessionShare };
    })
    .filter((r): r is { metro: string; share: number } =>
      r !== null && r.share !== null)
    .sort((a, b) => b.share - a.share);
  const highConcession = concessionRows.filter((r) => r.share >= 0.75);
  const lowConcession = concessionRows.filter((r) => r.share < 0.35);

  return (
    <>
      <TopNav />
      <main className="mx-auto max-w-6xl px-8 pt-8 pb-16">

        {/* Title block */}
        <header className="mb-10">
          <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-ground">
            Data sources
          </div>
          <h1 className="mt-2 font-serif text-[34px] font-semibold leading-tight tracking-tight text-ground-ink">
            Two layers, one read.
          </h1>
          <p className="mt-3 max-w-2xl text-[14px] leading-relaxed text-ink-soft">
            The historical engine runs entirely on clean public APIs and files.
            The Bright Data layer adds the live demand-texture overlay where
            no clean public API exists.
          </p>
        </header>

        {/* Two-layer framing */}
        <section className="mb-12 grid grid-cols-1 gap-6 lg:grid-cols-2">
          <article className="border-t-2 border-ground/80 pt-5">
            <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-ground">
              Historical engine
            </div>
            <h2 className="mt-1.5 font-serif text-[18px] font-semibold text-ground-ink">
              FRED · BLS · Zillow · state .gov
            </h2>
            <p className="mt-3 text-[13px] leading-relaxed text-ink-soft">
              Lead-lag prediction across{" "}
              <strong className="font-semibold text-ground-ink">17 metros</strong>.
              Demand signals (postings, JOLTS quits, WARN, employment) lead
              rent growth by{" "}
              <strong className="font-semibold text-ground-ink">5–7 months</strong>{" "}
              at a{" "}
              <strong className="font-semibold text-ground">79.3% hit rate</strong>{" "}
              on 58 confirmed turns, +24.1 pp skill vs climatology baseline.
              Detailed validation on{" "}
              <Link href="/methodology" className="text-ground underline underline-offset-2 hover:text-ground-deep">
                /methodology
              </Link>.
            </p>
          </article>
          <article className="border-t-2 border-ground/40 pt-5">
            <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-ground/80">
              Live layer · Bright Data Web Unlocker
            </div>
            <h2 className="mt-1.5 font-serif text-[18px] font-semibold text-ground-ink">
              LinkedIn postings · apartments.com concessions
            </h2>
            <p className="mt-3 text-[13px] leading-relaxed text-ink-soft">
              Two anti-bot targets with no clean public API. Both are the{" "}
              <strong className="font-semibold text-ground-ink">public-data proxy
              for the kind of demand-texture signal institutions normally license</strong>{" "}
              from CoStar / RealPage / Yardi. The historical engine validates the
              chain; Bright Data delivers the current-state evidence that confirms it.
            </p>
          </article>
        </section>

        {/* Convergence — honest two-source framing */}
        {highConcession.length > 0 && lowConcession.length > 0 && (
          <section className="mb-12 border-y border-rule py-8">
            <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-ground">
              Convergence · two independent data sources, same geographic answer
            </div>
            <h2 className="mt-2 font-serif text-[22px] font-semibold leading-snug text-ground-ink">
              The engine&apos;s labor read and Bright Data&apos;s live concessions
              point at the same Sun Belt cluster.
            </h2>
            <p className="mt-3 max-w-3xl text-[13.5px] leading-relaxed text-ink-soft">
              Two genuinely independent sources — engine fundamentals (FRED / BLS
              labor data) and live concessions (Bright Data → apartments.com,
              operators cutting effective rent right now). They converge on the
              same cluster despite measuring different things on different
              cadences. That convergence is the strongest external check on
              whether the spine is real.
            </p>

            <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2">
              <article className="border-l-2 border-cool/70 pl-4">
                <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-cool">
                  Sun Belt oversupply · {highConcession.length} metros at ≥75% concession
                </div>
                <p className="mt-1.5 text-[12.5px] tabular-nums leading-relaxed text-ink-soft">
                  {highConcession
                    .map((r) => `${r.metro} ${(r.share * 100).toFixed(0)}%`)
                    .join(" · ")}
                </p>
              </article>
              <article className="border-l-2 border-firm/70 pl-4">
                <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-firm">
                  Constrained coastal · {lowConcession.length} metros at &lt;35% concession
                </div>
                <p className="mt-1.5 text-[12.5px] tabular-nums leading-relaxed text-ink-soft">
                  {lowConcession
                    .map((r) => `${r.metro} ${(r.share * 100).toFixed(0)}%`)
                    .join(" · ")}
                </p>
              </article>
            </div>

            <p className="mt-5 text-[11.5px] leading-relaxed text-ink-faint">
              Note: the rotation backtest (on{" "}
              <Link href="/methodology" className="text-ground underline underline-offset-2 hover:text-ground-deep">
                /methodology
              </Link>) reads the same Sun Belt 2023 firming on the same labor data
              — but it is the engine, not an independent source. We do not
              count it as a third leg of the convergence.
            </p>
          </section>
        )}

        {/* Bright Data — how we use it */}
        <section className="mb-12">
          <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-ground">
            How we use Bright Data
          </div>
          <h2 className="mt-2 font-serif text-[22px] font-semibold leading-snug text-ground-ink">
            Two targets, both anti-bot, both no-API, both valuable and difficult to access.
          </h2>

          <div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-2">
            <article className="border-t border-rule pt-5">
              <div className="font-serif text-[16px] font-semibold text-ground-ink">
                LinkedIn job search
              </div>
              <dl className="mt-3 grid grid-cols-[112px_1fr] gap-y-1.5 text-[12px] leading-snug">
                <dt className="text-ink-faint">Endpoint</dt>
                <dd className="tabular-nums text-ground-ink">POST api.brightdata.com/request</dd>
                <dt className="text-ink-faint">Extracts</dt>
                <dd className="text-ground-ink"><code className="rounded bg-ground-soft px-1 text-[11px] text-ground">record_postings</code> tool (Sonnet 4.6)</dd>
                <dt className="text-ink-faint">Fields</dt>
                <dd className="text-ink-soft">company · title · city · days_ago · is_remote</dd>
                <dt className="text-ink-faint">Hygiene</dt>
                <dd className="text-ink-soft">≤21d server-filter · dedupe · drop remote</dd>
                <dt className="text-ink-faint">Coverage</dt>
                <dd className="text-ground-ink"><span className="tabular-nums">17 metros</span>, ~55 postings each</dd>
                <dt className="text-ink-faint">Why hard</dt>
                <dd className="text-ink-soft">auth walls · JS-rendered cards · server-side time filter (<code className="text-[11px]">f_TPR=r1814400</code>)</dd>
              </dl>
            </article>
            <article className="border-t border-rule pt-5">
              <div className="font-serif text-[16px] font-semibold text-ground-ink">
                Apartments.com listings
              </div>
              <dl className="mt-3 grid grid-cols-[112px_1fr] gap-y-1.5 text-[12px] leading-snug">
                <dt className="text-ink-faint">Endpoint</dt>
                <dd className="tabular-nums text-ground-ink">POST api.brightdata.com/request</dd>
                <dt className="text-ink-faint">Extracts</dt>
                <dd className="text-ground-ink"><code className="rounded bg-ground-soft px-1 text-[11px] text-ground">record_listings</code> tool (Sonnet 4.6)</dd>
                <dt className="text-ink-faint">Fields</dt>
                <dd className="text-ink-soft">building · address · asking_rent · has_concession · beds</dd>
                <dt className="text-ink-faint">Hygiene</dt>
                <dd className="text-ink-soft">drop blank/no-rent · dedupe by building+addr</dd>
                <dt className="text-ink-faint">Coverage</dt>
                <dd className="text-ground-ink"><span className="tabular-nums">17 metros</span>, ~40 buildings each</dd>
                <dt className="text-ink-faint">Why hard</dt>
                <dd className="text-ink-soft">CoStar-owned · CSAT cookies · JS card grids · geo-fenced</dd>
              </dl>
            </article>
          </div>

          <div className="mt-6 grid grid-cols-1 gap-4 border-t border-rule pt-5 text-[12px] leading-relaxed text-ink-soft md:grid-cols-3">
            <div>
              <div className="mb-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-ground/80">
                Spend
              </div>
              ~$0.50 per full 34-call refresh (17 LinkedIn + 17 apartments.com
              Web Unlocker requests + Sonnet 4.6 extractions) on the public
              ~$3/1k tier. Refreshable arbitrarily often against budget.
            </div>
            <div>
              <div className="mb-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-ground/80">
                Where we don&apos;t use Bright Data
              </div>
              FRED, BLS public API, Zillow research CSVs — clean public APIs.
              Using BD there would be theatre. We use BD only where it&apos;s
              genuinely the right tool: anti-bot, no-API, demand-texture data
              otherwise inaccessible.
            </div>
            <div>
              <div className="mb-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-ground/80">
                Why apartments.com matters
              </div>
              Operators cut <em>effective</em> rent via concessions (&ldquo;1
              Month Free&rdquo;, &ldquo;$N off&rdquo;) BEFORE face/asking rent
              moves. ZORI won&apos;t reflect a softening market for ~a quarter;
              the BD concessions share visible <em>right now</em> is the live
              read inside the demand → rent stage of the chain.
            </div>
          </div>
        </section>

        {/* WARN sourcing per metro — transparency table */}
        <section className="mb-12">
          <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-ground">
            WARN sourcing per metro
          </div>
          <h2 className="mt-2 font-serif text-[20px] font-semibold leading-snug text-ground-ink">
            Direct .gov where feasible. Clean republishers where it isn&apos;t.
          </h2>
          <p className="mt-3 max-w-3xl text-[13px] leading-relaxed text-ink-soft">
            NY DOL omits employee counts on year pages and would require 5000+
            per-filing PDF fetches. mass.gov publishes only the latest week&apos;s
            CSV (historical URLs return 403). WA paginates a ~3yr window only.
            Bright Data Web Unlocker blocks .gov by policy, so it can&apos;t
            bypass any of those. Per-metro windows below show exactly what each
            row is built on. The methodology caveats (
            <Link href="/methodology#caveats" className="text-ground underline underline-offset-2 hover:text-ground-deep">
              /methodology
            </Link>) reference this table.
          </p>

          <div className="mt-5 overflow-hidden border-t border-rule">
            <table className="w-full text-[12px]">
              <thead className="border-b border-rule bg-ground-soft/30 text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-soft">
                <tr>
                  <th className="px-3 py-2 text-left font-semibold">Metro</th>
                  <th className="px-3 py-2 text-left font-semibold">Source</th>
                  <th className="px-3 py-2 text-left font-semibold">Window</th>
                  <th className="px-3 py-2 text-left font-semibold">Note</th>
                </tr>
              </thead>
              <tbody>
                {METRO_ORDER.map((m, i) => {
                  const s = WARN_SOURCING[m];
                  return (
                    <tr key={m} className={i % 2 === 0 ? "bg-cream" : "bg-ground-soft/15"}>
                      <td className="px-3 py-1.5 font-medium text-ground-ink">{m}</td>
                      <td className={`px-3 py-1.5 ${s.direct ? "text-firm" : "text-ink-soft"}`}>
                        <span className="inline-block min-w-[60px] text-[9.5px] font-semibold uppercase tracking-[0.14em]">
                          {s.direct ? "Direct" : "Republished"}
                        </span>
                        <span className="text-ink-soft"> · {s.source}</span>
                      </td>
                      <td className="px-3 py-1.5 tabular-nums text-ink-soft">{s.window}</td>
                      <td className="px-3 py-1.5 text-[11.5px] italic text-ink-faint">{s.note ?? ""}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>

        {/* Sources inventory */}
        <section className="mb-10">
          <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-ground">
            Inventory
          </div>
          <h2 className="mt-2 font-serif text-[20px] font-semibold leading-snug text-ground-ink">
            What&apos;s in the cache.
          </h2>
          <p className="mt-2 max-w-3xl text-[12.5px] leading-relaxed text-ink-soft">
            Every snapshot the agent and these pages read. Bright Data layers
            marked with a small green dot.
          </p>

          <div className="mt-5 grid grid-cols-1 gap-x-8 gap-y-0 md:grid-cols-2">
            {datasets.map((d) => (
              <article key={d.key} className="border-t border-rule py-3.5 px-1">
                <div className="flex items-baseline justify-between gap-3">
                  <div className="flex items-baseline gap-2">
                    {d.isBD && <span className="h-1.5 w-1.5 rounded-full bg-ground translate-y-[-1px]" />}
                    <span className="font-serif text-[14.5px] font-semibold text-ground-ink">{d.label}</span>
                  </div>
                  <span className="text-[10.5px] tabular-nums text-ink-faint">{d.file}</span>
                </div>
                <p className="mt-1 text-[12px] leading-snug text-ink-soft">{d.mechanism}</p>
                <div className="mt-1.5 flex items-center gap-4 text-[10.5px] tabular-nums text-ink-faint">
                  <span>{fmtKB(d.size)}</span>
                  <span>updated {ageString(d.mtime)}</span>
                </div>
              </article>
            ))}
          </div>
        </section>

        <p className="mt-12 text-[10.5px] uppercase tracking-[0.18em] text-ink-faint">
          Demo mode · cached snapshots · all numbers reproducible from the JSON above
        </p>
      </main>
    </>
  );
}
