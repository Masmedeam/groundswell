# DATA.md

Integration boundary doc for everything under `data/`. Every JSON in here is committed and current as of the validated final state (see `CLAUDE.md` for the build log). Built to be wired into Salim's repo (`Masmedeam/groundswell`) without reverse-engineering.

**Universal conventions**

- All time-series rows use the **data contract** `{metro, signal, date: "YYYY-MM-DD", value}`. The `metro` field carries a display name (e.g. `"San Francisco"`, `"Salt Lake City"`); translate to `metro_id` via [`data/metro-id-map.json`](data/metro-id-map.json) `name_lookups.by_display_name`.
- Dates are either YYYY-MM-01 (first-of-month convention) or YYYY-MM-31 (end-of-month, ZORI source convention). Use `date.slice(0,7)` for month-key joins.
- Numeric values use raw units: rents in USD/month, prices in USD, employment in thousands of jobs, JOLTS rates in % (e.g. 4.2 = 4.2%), WARN in affected-worker count.

---

## File inventory at a glance

| File | Type | Rows | Metros | Date range | Pipeline | Live or historical |
|---|---|---|---|---|---|---|
| `metro-id-map.json` | reference | 17 | 17 | n/a | hand-written | static |
| `employment.json` | signal input | 2,312 | 17 | 2015-01 → 2026-04 | `npm run data:fred` | historical |
| `rent.json` | signal input (target) | 2,351 | 17 | 2015-01 → 2026-04 | `npm run data:rent` | historical |
| `warn.json` | signal input | 927 | 9 | 2014-07 → 2026-05 | `npm run data:warn` | historical |
| `postings.json` | signal input | 1,037 | 17 | 2020-02 → 2025-02 | `npm run data:postings` | historical (Indeed discontinued) |
| `jolts.json` | signal input (3 derived) | 15,300 | 17 | 2001-01 → 2025-12 | `npm run data:jolts` | historical |
| `permits.json` | tested + removed | 1,755 | 9 | 2010-01 → 2026-03 | `npm run data:permits` | historical (descriptive only) |
| `wages.json` | tested + removed | 1,848 | 9 | 2007-01 → 2026-04 | `npm run data:wages` | historical (descriptive only) |
| `rent-vs-own.json` | tested + removed | 1,224 | 9 | 2015-01 → 2026-04 | `npm run data:rent-vs-own` | historical (descriptive only) |
| `zhvi.json` | price proxy | 5,354 | 17 | 2000-01 → 2026-04 | `npm run data:zhvi` | historical |
| `benchmark.json` | REIT backdrop | 149 | 1 (US) | 2014-01 → 2026-05 | `npm run data:benchmark` | historical |
| `results.json` | analytical output | 103 | 17 | per-row windows | `npm run data:analyze-signals` | derived |
| `detection.json` | analytical output | n=58 turns | 17 | 2017-01 → 2026-03 | `npm run data:detection` | derived |
| `forecast-skill.json` | analytical output | n=58 | 17 | turn-anchored | `npm run data:skill` | derived |
| `buckets.json` | analytical output | 90 cells | 9 | annual 2016→2025 | `npm run data:buckets` | derived |
| `backtest.json` | analytical output | 29 rebalances | 4 | 2019-01 → 2026-01 | `npm run data:backtest` | derived |
| `backtest-rotation.json` | analytical output | 48 positions | 17 | 2017-01 → 2026-04 | `npm run data:rotation` | derived |
| `backtest-rotation-flex.json` | analytical output | 48 positions | 17 | 2017-01 → 2026-04 | `npm run data:rotation-flex` | derived |
| `postings-live.json` | BD live snapshot | n=950 postings | 17 | as-of timestamp | `npm run data:postings-live` | **live (re-snap to refresh)** |
| `listings-live.json` | BD live snapshot | n=666 listings | 17 | as-of timestamp | `npm run data:listings-live` | **live (re-snap to refresh)** |
| `zori.csv` | raw source | (wide) | (many) | 2015-01 → current | manual Zillow download | historical |
| `warn-cache/` | extraction cache | per-FY | n/a | n/a | populated by data:warn | cache |

**Categories:**
- **Signal inputs** (5): the lead-lag pipeline reads these to produce `results.json`.
- **Tested + removed signals** (3): kept as descriptive context, NOT in `SIGNAL_META` / not read by analyze-signals / detection / backtest / rotation. See each file's header for the failure narrative.
- **Price/return data** (2): consumed by the rotation backtest. ZHVI is the metro price proxy; benchmark is the REIT backdrop.
- **Analytical outputs** (8): derived from inputs by deterministic scripts. Re-run pipeline rebuilds them.
- **BD live layer** (2): current-state snapshots, NOT in the prediction pipeline. Same caveat class as a weather observation vs a forecast.

---

## Reference

### `data/metro-id-map.json`

**Purpose** — Canonical lookup for translating `metro` display names to `metro_id` keys matching Salim's app convention (`sf`, `austin`, `phoenix`, `nyc`, `chicago` + 12 added).

**Shape**
```ts
{
  metros: {
    [metro_id: string]: {
      display_name: string;           // matches `metro` field in all signal data
      msa_name: string;               // canonical Census MSA name
      cbsa_code: string;              // 5-digit CBSA code
      states: string[];               // e.g. ["CA"] or ["NY", "NJ", "PA"]
      anchor_county_fips: string;     // 5-digit county FIPS for BEA/county-level joins
      anchor_county_name: string;
      zillow_region_id: number;       // for ZHVI/ZORI cross-app joins
      tier: "original-4" | "tier-1" | "tier-2" | "tier-3";
      in_salim_demo_set: boolean;     // true if metro is in Salim's 5-metro demo set
      aliases: string[];              // alternate metro_id strings if naming preference differs
      notes?: string;
    }
  },
  name_lookups: {
    by_display_name: { [display_name: string]: metro_id };
    by_cbsa_code:    { [cbsa_code: string]: metro_id };
  }
}
```

**Integration** — load once at app start; cache the `name_lookups.by_display_name` map. Every join from Laurie's data to Salim's ES `metro_id`-keyed indices goes through this.

---

## Signal inputs (lead-lag pipeline)

All five files share the contract `{metro, signal, date, value}`. They feed `scripts/analyze-signals.mjs` → `data/results.json` and `scripts/detection.mjs` → `data/detection.json`.

### `data/employment.json`

**Purpose** — BLS total-nonfarm metro employment, monthly, in thousands of jobs.
**Source** — FRED API: 16 NAN-suffix series (one per metro) + Boston SMS series. See `scripts/pull-fred.mjs` for the per-metro series IDs.
**Sample**
```json
{ "metro": "San Francisco", "signal": "bls_employment", "date": "2015-01-01", "value": 2189.1 }
```
**Lead-lag pre-stated sign vs rent**: POSITIVE.

### `data/rent.json`

**Purpose** — Zillow ZORI metro rent index, monthly, in USD/month (smoothed seasonally adjusted, all-homes mid-tier).
**Source** — `data/zori.csv` (manual Zillow Research download) → parsed by `scripts/parse-zori.mjs`. The CSV is wide-format (1 row per metro, 1 column per month); the parser pivots to long-format rows.
**Sample**
```json
{ "metro": "Atlanta", "signal": "rent", "date": "2015-01-31", "value": 993.97 }
```
**Note** — `date` uses end-of-month (Zillow convention). Compare months via `date.slice(0,7)`. **This is the lead-lag TARGET series** — all signal-vs-rent correlations use this.

### `data/warn.json`

**Purpose** — WARN Act layoff filings aggregated to monthly affected-worker counts per metro.
**Source** — 8 state pipelines (5 direct .gov: CA EDD xlsx + 11 CA archive PDFs, TX TWC, UT DWS, PA L&I; 3 layoffdata.com Google Sheets: NY/MA/WA/ID). Aggregated via `lib/warn.mjs` `aggregateToSignal()` after per-state filtering for MSA-relevant counties.
**Sample**
```json
{ "metro": "Austin", "signal": "warn", "date": "2022-07-01", "value": 78 }
```
**Coverage** — 9 of 17 metros (Tier 3 deferred per Phase N "don't burn hours" discipline). `value` = sum of `employees_affected` in that month. Months with zero filings are NOT present; `lib/leadlag.mjs` `fillMonthlyGaps(0)` densifies them before correlation.
**Lead-lag pre-stated sign vs rent**: NEGATIVE.

### `data/postings.json`

**Purpose** — Indeed Hiring Lab Job Postings Index per MSA, monthly (mean of daily observations within the month).
**Source** — FRED API: `IHLIDX{cbsa}` per metro (e.g. `IHLIDX41860` for SF).
**Sample**
```json
{ "metro": "San Francisco", "signal": "postings", "date": "2020-02-01", "value": 99.55 }
```
**Note** — Index value, base 100 = Feb 2020. Indeed **discontinued** publishing this series Feb 2025; no further updates possible. Pre-stated sign vs rent: POSITIVE.

### `data/jolts.json`

**Purpose** — BLS state-level JOLTS, monthly, fanned to parent-state metros. Carries THREE derived signals in one file (filter on `signal` field):
- `jolts_absorption` = state openings (JOL) / state hires (HIL). Pre-stated NEG vs rent (came out wrong-sign empirically; reported as-is).
- `jolts_hires` = state hires rate (HIR), % of employment. Pre-stated POS.
- `jolts_quits` = state quits rate (QUR), % of employment. Pre-stated POS. **The corrected universal breadth signal — clean in 14 of 17 metros.**
**Source** — BLS public API (state JOLTS isn't on FRED). 8 parent states cover all 17 metros (TX → austin + dallas; CA → sf + sacramento).
**Sample**
```json
{ "metro": "Atlanta", "signal": "jolts_absorption", "date": "2001-01-01", "value": 1.005376 }
```

---

## Tested + removed signals (descriptive context only)

These three were pre-stated, run, and failed their pre-stated tests. Kept as descriptive context per project discipline — NOT in `lib/signal-eval.mjs` `SIGNAL_META`, NOT read by analyze-signals / detection / backtest / rotation. See each pull-script header for the full failure narrative.

### `data/permits.json`

**Purpose** — Census Building Permits per MSA (FRED `{cbsa}BPPRIVSA` series).
**Sample** `{ "metro": "San Francisco", "signal": "permits", "date": "2010-01-01", "value": 287.12 }`
**Failure mode** — Permits are pro-cyclical (builders permit *when* demand fires), not counter-cyclical leading indicators. Both contemporaneous-elasticity and extended-lag tests came out wrong-sign in all 9 metros.
**Coverage** — 9 of 17 metros. Pre-stated NEG vs rent. Could be useful for descriptive "supply state" overlays.

### `data/wages.json`

**Purpose** — BLS CES Average Hourly Earnings, Total Private per MSA, monthly (FRED `SMU…500000003`).
**Sample** `{ "metro": "San Francisco", "signal": "wages", "date": "2011-01-01", "value": 32.3 }`
**Failure mode** — Pre-stated POSITIVE failed in 3/9 metros wrong-sign, only Sacramento clean (weak r=0.20). Adding wages dropped engine hit rate 79.3% → 71.9% and BSS vs base rate +0.31 → +0.05.
**Coverage** — 9 of 17 metros.

### `data/rent-vs-own.json`

**Purpose** — Affordability ratio = monthly P&I on 30yr fixed (MORTGAGE30US × Zillow ZHVI) / ZORI rent.
**Sample** `{ "metro": "Austin", "signal": "rent_vs_own", "date": "2015-01-01", "value": 1.0149 }`
**Failure mode** — Pre-stated POSITIVE failed in 8/9 metros (7 lags-not-leads, 1 wrong-sign). Mechanical reason: ZORI appears in the denominator AND is the lead-lag target. Could surface as a per-metro affordability **level** metric on a markets view.
**Coverage** — 9 of 17 metros.

---

## Price / return data

### `data/zhvi.json`

**Purpose** — Zillow ZHVI metro price index, monthly, in USD (smoothed seasonally adjusted, all-homes mid-tier 0.33–0.67 percentile band).
**Source** — Same Zillow ZHVI CSV as the rent-vs-own ratio numerator; raw level persisted here. Pulled by `scripts/pull-zhvi.mjs` (RegionID-matched to disambiguate Austin TX from Austin MN).
**Sample**
```json
{ "metro": "Atlanta", "signal": "zhvi_price", "date": "2000-01-01", "value": 150717.14 }
```
**Used by** — `scripts/backtest-rotation.mjs` and `scripts/backtest-rotation-flex.mjs` as the price proxy for CRE valuation channel. **NOT a leading signal in `SIGNAL_META`** — it's the return measure for the rotation backtest.
**Caveat** — Residential repeat-sales index, used as a directional proxy for the CRE valuation channel; NOT a deal-level price proxy.

### `data/benchmark.json`

**Purpose** — Nasdaq US Benchmark REIT Index (price-only, FRED `NASDAQNQUSB351020`), monthly aggregated to last-close.
**Sample**
```json
{ "metro": "US", "signal": "reit_price", "date": "2014-01-01", "value": 1085.42, "source_date": "2014-01-31" }
```
**Used by** — `scripts/backtest.mjs` as a listed-REIT backdrop on the naive-trading test chart. Price-only (NOT total-return) for like-for-like comparison with appreciation-only strategy lines.

---

## Live Bright Data layers

**These are CURRENT-STATE snapshots, NOT historical. Re-snap to refresh.** Both files include a top-level `fetched_at` ISO timestamp.

### `data/postings-live.json`

**Purpose** — LinkedIn job-search snapshot per metro via Bright Data Web Unlocker → Sonnet 4.6 structured extraction. Server-side ≤21-day filter, hygiene gates (dedupe by company+title+metro, drop remote).
**Shape**
```ts
{
  fetched_at: string;     // ISO timestamp
  source: "linkedin";
  hygiene: { maxDaysAgo: 21 };
  metros: {
    [display_name: string]: {
      count: number;
      stats: { fetched, dropped_remote, dropped_old, deduped };
      postings: Array<{ metro, company, title, city, posted_text, days_ago, is_remote, url? }>;
    } | { error: string };
  };
}
```
**Coverage** — 17 of 17 metros as of latest snapshot. ~55 postings each.
**Spend** — ~$0.05 BD + ~$0.20 LLM per full 17-metro refresh.

### `data/listings-live.json`

**Purpose** — Apartments.com listings snapshot per metro via Bright Data Web Unlocker → Sonnet 4.6 extraction. Per-metro median asking rent + concession share — the "leading edge of rent" before face/asking rent moves in ZORI.
**Shape**
```ts
{
  fetched_at: string;
  source: "apartments.com";
  mechanism: string;
  caveats: { cadence, proxy, sampling, concessions };
  metros: {
    [display_name: string]: {
      n: number;
      medianAskingRent: number | null;
      concessionShare: number | null;
      concessionsCount: number;
      sampleConcessionPhrases: string[];
      stats: { fetched, dropped_no_name, dropped_no_rent, deduped };
      listings: Array<{
        metro, building_name, address, city,
        asking_rent_min: number | null,
        asking_rent_text: string,
        bed_counts_visible: string[],
        has_concession: boolean,
        concession_text: string,
      }>;
    } | { error: string };
  };
  miami_refetched_at?: string;
}
```
**Coverage** — 17 of 17 metros as of latest snapshot. ~40 buildings each (Miami refetched after a thin first hit).
**Spend** — ~$0.05 BD + ~$0.20 LLM per full 17-metro refresh.
**Integration** — for ES loading, flatten one doc per `(metro_id, fetched_at)` with the metro-level aggregates (`n`, `medianAskingRent`, `concessionShare`, `concessionsCount`); the per-listing `listings` array can be a nested field or a separate doc-per-listing index.

---

## Analytical outputs

### `data/results.json`

**Purpose** — Lead-lag leaderboard. Every (metro, signal, target) pair from analyze-signals gets one row with leadMonths + correlation + flags.
**Shape — array of:**
```ts
{
  metro: string;
  signal: "employment" | "rent" | "warn" | "postings" | "jolts_absorption" | "jolts_hires" | "jolts_quits";
  target: "employment" | "rent";
  leadMonths: number | null;          // positive = signal leads target by N months
  corr: number | null;                // Pearson on YoY × YoY
  expectedSign: "positive" | "negative" | null;
  nAtBestLag: number;
  window: { start: "YYYY-MM", end: "YYYY-MM" };
  signalMonths: number;
  signalNonzeroPct: number;
  flags: Array<"boundary-pinned" | "thin" | "sparse" | "wrong-sign" | "lags-not-leads">;
}
```
**Headline reading** — `r.flags.length === 0` AND `r.leadMonths > 0` AND `r.target === "rent"` = a clean leading signal for that metro.
**Integration** — flatten directly; one ES doc per row. Index name suggestion: `groundswell-leadlag_results`.

### `data/detection.json`

**Purpose** — Walk-forward turn-detection backtest. Every confirmed monthly turn (engine fires direction-change) gets a row with horizon-evaluation hits.
**Shape**
```ts
{
  config: {
    startYM, endYM, lastRentYM, pubLagMonths, stateBuffer,
    persistenceMonths, horizons: [3, 6, 9],
    metros: string[], evaluationLeadRule: string, whyNotPrice: string,
  };
  turns: Array<{
    metro, detectionYM, detectionDate, firstNewStateYM,
    direction: "firming" | "softening",
    priorState: "firming" | "softening" | "neutral",
    scoreAtDetection: number,
    contributingSignals: Array<{name, leadMonths, corr, contribution}>,
    forwardWindows: { "3": {hit, ...}, "6": {...}, "9": {...} };
    signalLead: {
      dominantSignal, dominantLeadMonths, dominantCorr,
      hit: boolean | null,
      beyondData: boolean,
      delta: number,            // rent YoY change at dominant lead
    } | null;
    isWorkedExample?: boolean;
  }>;
  currentByMetro: {
    [metro_display_name]: {
      ym, asOfYM, state, score, cleanCount,
      contributingSignals: Array<{...}>,
    };
  };
  aggregate: {
    overall: { nTurns, hitRates: {3,6,9}, atSignalLead: {hits, n, hitRate, medianDominantLead} };
    byDirection: { softening: {...}, firming: {...} };
    byMetro: { [display_name]: {nTurns, hitRates, atSignalLead} };
  };
}
```
**Headline number** — `aggregate.overall.atSignalLead.hitRate` = 0.7931 (46/58).
**Integration** — `turns[]` flattens cleanly to one ES doc per turn. `currentByMetro` is the "what is the engine saying NOW" view — flatten to one doc per metro. `aggregate` is a small dict best kept as a single doc.

### `data/forecast-skill.json`

**Purpose** — Engine vs persistence + base-rate baselines on the same confirmed turns (apples-to-apples). Brier + BSS scoring + confidence-weighted accuracy.
**Shape**
```ts
{
  config: { methodology, evaluatedAt, confidenceMapping, persistenceMethod, baseRateMethod, ... };
  perTurn: Array<{
    metro, detectionYM, realized, delta, scoreAtDetection,
    dominantSignal, dominantLeadMonths, dominantCorr,
    engine:      { dir, hit, p };
    persistence: { dir, hit, p, trend };
    baseRate:    { dir, hit, p };
  }>;
  aggregate: {
    overall: {
      n, engine: {hits, hitRate, brier, weightedAcc},
      persistence: {nJudged, hits, hitRate, brier},
      baseRate: {hits, hitRate, brier},
      skill: {vsPersistence: pp, vsBaseRate: pp},
      bss: {vsPersistence, vsBaseRate},
    };
    byMetro: { [display_name]: <same shape as overall> };
  };
}
```
**Headline numbers** — `aggregate.overall.skill.vsPersistence` = −0.017 (−1.7 pp); `aggregate.overall.bss.vsBaseRate` = +0.31.
**Integration** — `perTurn[]` flattens to one ES doc per turn (joinable with `detection.json.turns` by `(metro, detectionYM)`). `aggregate` is a small summary doc.

### `data/buckets.json`

**Purpose** — Annual BUY/HOLD/SELL classification per metro per year, with realized 12mo forward rent growth. Used by `/decisions` for current supply-state context per metro.
**Shape**
```ts
{
  config: { startYear, endYear, metros, pubLagMonths, txnCost, ... };
  cells: Array<{
    year, metro, asOfYM,
    bucket: "BUY" | "HOLD" | "SELL",
    reason: string,
    prevBucket: string | null,
    transition: "ENTRY" | "EXIT" | null,
    demandScore, demandCleanCount,
    supplyState: "tight" | "moderate" | "elastic" | null,    // descriptive only
    supplyRatio: number | null,
    signalsUsed: Array<{name, leadMonths, corr, latestYoY, contribution}>,
    forwardGrowth, netGrowth, costApplied,
  }>;
  buckets: { BUY: {...}, SELL: {...}, HOLD: {...} };
  headline: { decisionYears, cellCount, buyVsSell: {...} };
}
```
**Coverage** — 9 of 17 metros, 10 years (2016–2025) = 90 cells.
**Note** — supplyState is computed but is descriptive only (Phase K removed permits from classification).

### `data/backtest.json`

**Purpose** — Naive quarterly-rebalance signal-driven portfolio test on rent appreciation. The "trading test" deliberately framed as a known trap.
**Shape**
```ts
{
  config: { startYM, endYM, freqMonths, pubLagMonths, topK, metros, gates, returnProxy, benchmarkSource };
  rebalances: Array<{
    date, asOf, endDate,
    perMetro: Array<{metro, score, cleanCount, perSignal}>,
    ranked: string[],
    topDriver: {signal, leadMonths, corr} | null,
    allocations: { signalWeighted: {...}, equalWeight: {...}, worstRanked: {...} },
    periodReturns: { signalWeighted, equalWeight, worstRanked, benchmark },
  }>;
  series: Array<{date, signalWeighted, equalWeight, worstRanked, benchmark}>;
  headline: { quarters, finalSignal, finalEqual, finalWorst, finalBenchmark, outperfVsEqualPct, outperfVsWorstPct, preStated, preStatedHeld };
}
```
**Coverage** — 4 metros (SF/Austin/SLC/Philly — deliberate Phase G design, NOT expanded to 17).
**Headline** — `headline.preStatedHeld === false` (signal-weighted underperformed equal-weight by ~1pp); framed on `/backtest` as "expected failure, by design."

### `data/backtest-rotation.json`

**Purpose** — Phase O fixed-exit rotation backtest. Hold-period strategy on PRICE (ZHVI) appreciation, 2yr min / 4yr max, 17 metros.
**Shape**
```ts
{
  config: {
    entryCadenceMonths, minHoldMonths, maxHoldMonths,
    priceTrailingMonths, stretchedLookbackMonths, stretchedQuantile, takeGainQuantile,
    pubLagMonths, metros, startYM, endYM,
    preStated: {thesis, beatsEqualWeight, beatsMomentum},
    methodology: {priceSeries, whyIndex, returns, whatThisProxiesFor, leverageNote},
    thinSampleCaveat: string,
  };
  strategy: {
    n, meanReturnPerPosition, meanAnnualizedReturn, medianAnnualizedReturn,
    meanHoldMonths, portfolioReturn, exitReasonCounts,
    positions: Array<RotationPosition>,
    entryLog: Array<{ym, asOfYM, metro, entered, reason, ...}>;
  };
  baselines: {
    equalWeightRotation: <same shape as strategy>,
    momentumRotation:    <same shape as strategy>,
    broadIndexBuyHold:   { n, startYM, endYM, holdMonths, meanReturn, annualizedReturn, perMetro },
  };
  headline: { strategyMeanAnnualized, ..., beatsEqual, beatsMomentum, preStatedHeld };
}

// where:
interface RotationPosition {
  metro, entryYM, entryPrice, demandScore, dominantSignal, trailingYoY,
  exitYM, exitPrice, holdMonths,
  return: number | null,
  exitReason: "take-gain" | "stretched-rolling-over" | "max-hold" | "window-end",
}
```
**Headline** — pre-stated FAILED (strategy −0.4 pp vs equal-weight, −1.8 pp vs momentum). Framed on `/rotation` as "labor was right, rate cycle dominated valuations — early-warning tool not trading."

### `data/backtest-rotation-flex.json`

**Purpose** — Phase Q flex-exit variant. Same entry, signal-driven exit (no fixed clock), 2yr min / 7yr cap.
**Shape** — same as `backtest-rotation.json` plus:
- `config.exitRules` documenting the four exit conditions
- `config.preStated.thesisN` for the two-thesis flex test
- `strategy.completed` / `strategy.truncated` sub-aggregates (signal-driven exit vs window-end truncation)
- `strategy.holdBuckets` for the horizon-bucket analysis (2-3yr / 3-5yr / 5-7yr / 7yr-cap)
- `RotationPosition.exitReason` extended with `"demand-rollover"` and `"stretched"` (separated, vs Phase O's combined `"stretched-rolling-over"`)

**Key finding documented in file** — horizon-bucket test was vacuous (all signal-driven exits fired at exactly 24mo). 5–7yr bucket empty. Read alongside `backtest-rotation.json` for the comparison context.

---

## Raw source

### `data/zori.csv`

**Purpose** — Raw Zillow ZORI CSV download. Manual drop, used as input to `scripts/parse-zori.mjs`.
**Source** — Zillow Research → "Metro_zori_uc_sfrcondomfr_sm_month.csv". Wide format: 1 row per region, columns include RegionID, SizeRank, RegionName, RegionType, StateName, then 1 column per month.
**Note** — Re-download from Zillow to refresh. Not auto-fetched; if missing, `npm run data:rent` will fail with a clear error.

### `data/warn-cache/`

**Purpose** — Per-fiscal-year extraction cache for the 11 California archive WARN PDFs (FY2014-15 → FY2024-25). Each `ca-{fy}.json` (SF Bay Area counties) and `ca-sac-{fy}.json` (Sacramento MSA counties) holds the Sonnet 4.6 extraction output from `lib/warn-ca-history.mjs`.
**Why cached** — Each archive PDF extraction is ~5-10 Claude calls (chunked at 15 pages each). Cached results make subsequent `npm run data:warn` runs finish in seconds instead of 5-10 minutes.
**Safe to delete** — yes; will be regenerated on next run.

---

## Env vars — mapping to Salim's repo

Both repos use Anthropic Claude + Bright Data. Variable names differ; same keys, different names:

| Mine (`.env.local`)          | Salim's (`.env`)        | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY`          | `CLAUDE_API_KEY`        | Same Anthropic API key, different var name. |
| `BRIGHTDATA_API_KEY`         | `BRIGHTDATA_TOKEN`      | Same BD API token. |
| `BRIGHTDATA_UNLOCKER_ZONE`   | `BRIGHTDATA_ZONE`       | Same BD Web Unlocker zone name. |
| `FRED_API_KEY`               | (not in his .env)       | He primarily fetches FRED via per-series CSV; my pipeline uses the FRED API. Add this to his env for cleaner FRED ingestion if my Node scripts move into his repo. |
| `BLS_API_KEY`                | (not in his .env)       | He uses BLS via FRED/FREDGraph + QCEW direct; I use BLS public API for state JOLTS. Optional in BLS API (higher rate limits with a key); my scripts work without one. |
| (not in mine)                | `APIFY_TOKEN`           | He uses Apify for WARN/Indeed/LinkedIn scraping; I don't. Keep his Apify pipeline as-is. |

**Merge path** — I'd rename my var reads to read both names: `process.env.ANTHROPIC_API_KEY ?? process.env.CLAUDE_API_KEY` etc. Then either `.env` shape works. Two-line change per script; not done in this prep pass per scope.

**Both `.env*` files are gitignored** — `.gitignore` in this repo matches `.env*` (catches `.env.local`, `.env`, `.env.production` etc.). Verified.

---

## How the analytical outputs depend on each other

```
                  employment, rent, warn, postings, jolts.json
                              │
                              ▼ scripts/analyze-signals.mjs
                              │
                  data/results.json   (lead-lag leaderboard)
                              │
                              │   (also reads: employment, rent, postings, warn, jolts directly)
                              ▼ scripts/detection.mjs
                              │
                  data/detection.json (walk-forward turns + per-signal-lead hits)
                              │
                              ▼ scripts/forecast-skill.mjs
                              │
                  data/forecast-skill.json (engine vs persistence + base-rate)


                  zhvi.json + signals + rent
                              │
                              ▼ scripts/backtest.mjs           ▶ data/backtest.json
                              ▼ scripts/backtest-rotation.mjs  ▶ data/backtest-rotation.json
                              ▼ scripts/backtest-rotation-flex.mjs ▶ data/backtest-rotation-flex.json


                  signals + rent + permits
                              │
                              ▼ scripts/bucket-analysis.mjs    ▶ data/buckets.json
```

To regenerate from scratch: run `data:fred` + `data:rent` + `data:warn` + `data:postings` + `data:jolts` + `data:permits` + `data:zhvi` + `data:benchmark` (inputs), then `data:analyze-signals` + `data:detection` + `data:skill` + `data:buckets` + `data:backtest` + `data:rotation` + `data:rotation-flex` (outputs). The BD live layers (`data:postings-live` + `data:listings-live`) are independent — re-snap to refresh.

---

## Validated final state — last regenerated

All `data/*.json` files are committed and reflect the validated final state through Phase R (the BD-centered polish pass). Specific milestones in committed history:

- `f679842` — Phase N (Tier 3 expansion to 17 metros). `employment`, `rent`, `postings`, `jolts`, `results`, `detection`, `forecast-skill` all re-generated.
- `e331a3e` — Phase O rotation backtest. `zhvi`, `backtest-rotation` first generated.
- `4bf6e7c` — Phase Q flex-exit. `backtest-rotation-flex` first generated.
- `6ad4cbf` — Phase P concessions. `listings-live` first generated.
- `133cc8f` — Phase R polish. `postings-live` re-snapped at 17 metros (was 4).
- `40d1c55` / `5c2248c` / `c4b13bc` — failed-test removals (rent-vs-own / wages / permits). Data files retained as descriptive.

Run `git log -- data/*.json` for full provenance.
