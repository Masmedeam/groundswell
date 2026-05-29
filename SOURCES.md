# Groundswell — Source Catalog & Retrieval Tests

**Product:** market-level, demand-side *defensibility* tool for institutional US rental underwriters.
**Architecture:** rent is the **target** (downloaded free), not scraped. Value is in **leading indicators**.
**Stance:** public web data only. **Country:** US. **Demo metros:** SF, Austin, Phoenix (+ NY, IL for breadth).

Legend — Test status: ✅ live-verified · 🟡 actor/endpoint exists, not yet run · ⛔ blocked · ⬜ not started

---

## Tier 0 — Targets & reference (free, no scraping) — **build first**

| Source | Role | Access | Fields | Freshness | Test |
|---|---|---|---|---|---|
| **Zillow ZORI** | Headline target (rent growth) | `files.zillowstatic.com/research/public_csvs/zori/Metro_zori_uc_sfrcondomfr_sm_month.csv` | metro, monthly rent index ~2014→ | Monthly (file last-mod 2026-05-16) | ✅ HTTP 200, 1 MB CSV |
| **BLS Total Nonfarm by MSA** (via FRED) | Intermediate target (validate signal→labor) | `fredgraph.csv?id=<ID>` keyless; e.g. `SANF806NA`, `PHOE004NA`, `NEWY636NA`, `CHIC917NA` | metro employment, monthly | Monthly (data→Apr 2026) | ✅ keyless CSV; Austin ID TBD |
| **BLS JOLTS** (via FRED) | Cross-check (openings/quits/layoffs) | FRED API / fredgraph CSV | national+regional, monthly | Monthly | 🟡 same mechanism as PAYEMS |

> Get a free FRED API key (`api.stlouisfed.org`) for bulk/series-search; `fredgraph.csv` works keyless per-series for ad-hoc pulls.

## Tier 1 — The spine (hero signal) — **build first**

| Source | Role | Access | Fields | Test |
|---|---|---|---|---|
| **WARN layoff filings** (CA, TX, AZ, NY, IL) | Hero leading indicator (leads BLS ~2mo) | **Apify** `jungle_synthesizer/warn-layoffs-aggregator` (multi-state) | employer, city/county/zip, notice_date, effective_date, affected_workers, layoff_type, source_url | ✅ **live run, CA, clean structured rows** |
| ↳ alt direct scrape | fallback / "live ops" flex | **Bright Data** Web Unlocker per state portal (CA EDD, TX TWC, AZ, NY DOL, IL IDES) | same | ⛔ BD blocked (no zone/perms) |

## Tier 2 — High-value adds

| Source | Role | Access | Fields | Test |
|---|---|---|---|---|
| **Indeed job postings** | Expansion-side signal | **Apify** `misceres/indeed-scraper` (1.5M runs) | title, company, location, date, salary | 🟡 actor verified, not run |
| **Census Building Permits (BPS)** | Supply blade (easy mode) | `census.gov/construction/bps` files + EITS API | MSA permits, monthly | ⬜ |

## Tier 3 — Roadmap

| Source | Role | Access |
|---|---|---|
| Office-lease announcements (Bisnow, The Real Deal, biz journals, CBRE/JLL PRs) | Commitment signal | **Bright Data SERP API** + news scrape |
| Census Business Formation Statistics | Expansion tell | `census.gov/econ/bfs` (free) |
| City/county permits (SF DBI, Austin DSD, Phoenix P&D) | Granular supply | per-jurisdiction scrape |
| Migration (Census/IRS/U-Haul) | Slow demand tell | free, annual |
| Layoffs.fyi, SEC 10-K/Q headcount, earnings transcripts | Company-level corroboration | public/EDGAR |

---

## Retrieval test log (2026-05-29)

- **ZORI** — `curl -sIL` → HTTP/2 200, `content-length: 1009332`, `last-modified: Sat, 16 May 2026`. ✅
- **FRED PAYEMS** — keyless `fredgraph.csv` → CSV through `2026-04-01,158736`. ✅
- **FRED metro** — `SANF806NA / PHOE004NA / NEWY636NA / CHIC917NA` return CSV; `AUST148NA` invalid (resolve Austin area code via FRED search). ✅(4/5)
- **WARN (Apify)** — `run-sync-get-dataset-items`, input `{states:["CA"], noticeDateFrom:"2026-01-01", maxItems:5}` (+ required `sp_*` survey fields) → 5 structured rows, 16 fields, sourced from CA EDD xlsx. ✅
- **Indeed (Apify)** — actor confirmed public, 1.5M runs; test run pending. 🟡
- **Bright Data Web Unlocker** — UNBLOCKED. Zone `web_unlocker1` created. Welcome test ✅; **Indeed SF search unlocked: 1.53 MB, 19 job cards** ✅ (canonical bot-protected target). CA EDD WARN page → 502 (covered by Apify anyway); TWC URL was stale. Call: `POST api.brightdata.com/request` with `{"zone":"web_unlocker1","url":...,"format":"raw"|"json"}`, Bearer auth. ✅

## Account status

- **Apify** — FREE plan, ~$7.93/$105 used (May cycle). 50k SERPs, 20GB residential proxy ~untouched. Frugal on paid runs.
- **Bright Data** — active, balance **$252** (6-day trial), Pay-as-you-go **$1.50/CPM**, 1000 req/min. ✅
