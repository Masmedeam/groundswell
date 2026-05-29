# GroundsWell

GroundsWell is a rental-market intelligence prototype for institutional underwriters.
The app goal is a simple agent interface: a Google-style prompt opens into a
two-panel workspace where the left side is the user/agent conversation and the
right side renders evidence from Elasticsearch as charts, maps, tables, and
source-backed market notes.

The current build is focused on the data layer. It combines public datasets,
Apify actors, and Bright Data-capable fetch helpers into normalized Parquet and
Elasticsearch indices.

## Current Status

Verified locally on `localhost:9201`.

| ES index | Docs | Store | Purpose |
|---|---:|---:|---|
| `groundswell-zillow_indices` | 60,984,628 | 8.3 GB | Zillow ZORI/ZHVI/sales/inventory/price-cut/market heat, metro/county/city/zip |
| `groundswell-apartment_list_indices` | 791,909 | 105 MB | Apartment List rent estimates, rent growth, vacancy, time-on-market |
| `groundswell-fred_series` | 39,231 | 2 MB | FRED labor/housing/rent context |
| `groundswell-permits_raw` | 25,789 | 2.3 MB | Census/FRED building permits |
| `groundswell-qcew` | 5,761 | 3.2 MB | BLS QCEW county industry employment and wages |
| `groundswell-warn_notices` | 4,727 | 1.5 MB | WARN layoff notices from Apify plus official TX/AZ enrichment |
| `groundswell-fhfa_hpi` | 2,833 | 287 KB | FHFA house-price index for buy-vs-rent pressure |
| `groundswell-job_postings` | 1,794 | 852 KB | Indeed postings from Apify |
| `groundswell-linkedin_job_postings` | 1,253 | 6 MB | LinkedIn postings from Apify |
| `groundswell-redfin_listings` | 375 | 557 KB | Redfin active/sale listing comps |
| `groundswell-apartments_com_properties` | 126 | 225 KB | Apartments.com multifamily property comps |
| `groundswell-signals` | 8,039 | 474 KB | Canonical aligned time series for modeling/agent tools |
| `groundswell-market_context_docs` | 54 | 38 KB | Retrieval-ready narrative summaries derived from signals |
| `groundswell-metros` | 5 | 9 KB | Demo metro dimension table |

Total indexed corpus is roughly **61.86M documents**. Local generated data is
about **2.0 GB** under `data/`, which is intentionally gitignored.

## Demo Metros

Configured in `config/metros.yaml`:

- San Francisco
- Austin
- Phoenix
- New York
- Chicago

These metros anchor canonical signals and live Apify pulls. Many raw indices
contain national/ZIP/county/city coverage beyond the five demo metros.

## Canonical Signals

`groundswell-signals` is the aligned time-series core that the agent should query
for quick market reads.

| Series | Rows | Metros | Range |
|---|---:|---:|---|
| `apartment_list_rent` | 565 | 5 | 2017-01 to 2026-05 |
| `apartment_list_vacancy` | 565 | 5 | 2017-01 to 2026-05 |
| `apartment_list_time_on_market` | 445 | 5 | 2019-01 to 2026-05 |
| `fhfa_hpi` | 1,000 | 5 | 1975-07 to 2026-01 |
| `linkedin_postings` | 78 | 5 | 2023-06 to 2026-05 |
| `nonfarm_emp` | 2,180 | 5 | 1990-01 to 2026-04 |
| `permits` | 2,295 | 5 | 1988-01 to 2026-03 |
| `postings` | 74 | 5 | 2020-08 to 2026-05 |
| `qcew_emp` | 25 | 5 | 2020-01 to 2024-01 |
| `rent_index` | 680 | 5 | 2015-01 to 2026-04 |
| `warn_affected` | 66 | 2 | 2020-02 to 2026-05 |
| `warn_notices` | 66 | 2 | 2020-02 to 2026-05 |

## Data Sources Implemented

### Public / Direct

- Zillow Research CSV catalog: ZORI, ZHVI, sales, inventory, price cuts, days,
  market heat across available geographic levels.
- Apartment List public CSVs: rent estimates, rent growth, vacancy, time on
  market.
- FRED/FREDGraph: national and metro labor/housing series.
- Census/FRED permits: building permit signals and raw permit rows.
- BLS QCEW: county industry employment/wages for demo metro counties.
- FHFA HPI: MSA house-price index.

### Apify

- `jungle_synthesizer/warn-layoffs-aggregator`: WARN base pull.
- `misceres/indeed-scraper`: Indeed job postings.
- `leadsbrary/linkedin-jobs-scraper`: LinkedIn job postings.
- `sian.agency/apartments-com-property-scraper`: Apartments.com multifamily comps.
- `crawlerbros/redfin-scraper`: Redfin listing comps.

### Official WARN Enrichment

The Apify WARN actor returned partial coverage, so the pipeline enriches it with:

- Texas TWC public WARN Excel files.
- Arizona Job Connection public WARN search pages.

## Architecture

```text
sources -> raw cache -> normalized Parquet -> DuckDB views -> Elasticsearch
                                        \-> canonical signals
                                        \-> market_context_docs
```

Main package layout:

```text
groundswell/
  cli.py                ingest/load/verify CLI
  config.py             env, paths, metro config
  fetch.py              curl/ranged/Bright Data download helpers
  store.py              Parquet write/upsert + DuckDB views
  es.py                 Parquet-to-Elasticsearch loader
  sources/
    zillow.py
    apartment_list.py
    fred.py
    permits.py
    warn.py
    postings.py
    fhfa.py
    qcew.py
    context_docs.py
```

Frontend/API scaffold:

```text
app/api/                FastAPI agent/API layer
app/web/                Next.js web UI
docker/docker-compose.yml
```

## Setup

Create `.env` in the repo root:

```bash
APIFY_TOKEN=...
BRIGHTDATA_TOKEN=...
BRIGHTDATA_ZONE=web_unlocker1
CLAUDE_API_KEY=...
```

Install Python data dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Start Elasticsearch/Kibana:

```bash
docker compose -f docker/docker-compose.yml up -d elasticsearch kibana
```

Project ES is exposed at `http://localhost:9201`. Port `9200` may belong to
another local project.

## Common Commands

Ingest one source:

```bash
python -m groundswell.cli ingest --source zillow
python -m groundswell.cli ingest --source apartment_list
python -m groundswell.cli ingest --source fred
python -m groundswell.cli ingest --source permits
python -m groundswell.cli ingest --source warn
python -m groundswell.cli ingest --source postings --postings-max 60
python -m groundswell.cli ingest --source fhfa
python -m groundswell.cli ingest --source qcew
python -m groundswell.cli ingest --source context_docs
```

Load selected tables into ES:

```bash
python -m groundswell.cli load-es --only signals market_context_docs
python -m groundswell.cli load-es --only zillow_indices
python -m groundswell.cli load-es --only apartment_list_indices
python -m groundswell.cli load-es --only apartments_com_properties redfin_listings
python -m groundswell.cli load-es --only job_postings linkedin_job_postings
```

Verify local Parquet/DuckDB coverage:

```bash
python -m groundswell.cli verify
```

Verify ES:

```bash
curl -s 'http://localhost:9201/_cat/indices/groundswell-*?v&h=index,docs.count,store.size&s=index'
```

## App Direction

Agent A is building the app surface. The data layer is prepared for tools like:

- `get_metro_overview(metro_id)`
- `get_timeseries(metro_id, series, date_range)`
- `compare_metros(series, metros)`
- `search_warn(metro_id, company_or_keyword)`
- `search_postings(metro_id, keyword)`
- `search_live_comps(metro_id, source, price_range)`
- `get_industry_mix(metro_id)`
- `get_market_context_docs(metro_id, topic)`

The left panel should stream the agent response. The right panel should render
the retrieved ES artifacts: charts, maps, tables, comp cards, and source links.

## Push Prep Notes

This workspace has been initialized as a local git repository, but it is not
connected to a remote yet. Generated data and secrets are excluded from git:

- `.env`
- `.venv/`
- `data/`
- `node_modules/`
- frontend build/cache directories
- Python caches

To commit and push once your git identity and remote are available:

```bash
git config user.name "Your Name"
git config user.email "you@example.com"
git status --short
git commit -m "Build GroundsWell data pipeline and app scaffold"
git branch -M main
git remote add origin <repo-url>
git push -u origin main
```

Before committing, run:

```bash
git status --short
python -m py_compile groundswell/*.py groundswell/sources/*.py
```

Do not commit `data/` or `.env`; the data can be regenerated with the CLI.

## Current Gaps / Next Data Push

- HUD ZIP/county/CBSA crosswalk for geographic joins.
- ACS affordability/demographics.
- Redfin/Apartments.com broader scrape depth if Apify credits allow.
- More WARN state-specific official scrapers.
- Embeddings or ES semantic fields for `market_context_docs`.
