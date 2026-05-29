# Groundswell — Implementation Plan

Goal of this pass: **build all possible sources** (ingestion) and prove each is retrievable, landing in local Elasticsearch. App/embeddings are later passes.

## Phase 0 — Unblock & scaffold (now)
- [ ] **Bright Data:** create a Web Unlocker zone (+ SERP zone) in the dashboard; grant the API token zone-management permission. (Currently blocks all BD scraping.) — *user action*
- [ ] Get a free **FRED API key** (optional but cleaner than per-series CSV).
- [ ] Repo scaffold: `ingest/` (per-source pullers), `data/` (raw, gitignored), `docker/` (Elasticsearch + Kibana compose), `.env` (done).

## Phase 1 — Free anchors (no credits, highest reliability)
- [ ] `ingest/zori.py` — download ZORI metro CSV, normalize to `{metro, month, rent_index}`.
- [ ] `ingest/fred.py` — pull Total Nonfarm per demo metro (resolve Austin ID) + JOLTS; normalize to `{metro, month, value, series}`.
- [ ] Define metro mapping: ZORI metro name ↔ FRED metro series ↔ county/zip (for WARN rollup).

## Phase 2 — Hero signal (Apify, validated)
- [ ] `ingest/warn.py` — call `jungle_synthesizer/warn-layoffs-aggregator` for [CA, TX, AZ, NY, IL]; geocode city/county/zip → metro; aggregate to monthly `{metro, month, notices, affected_workers}`.
- [ ] Backtest **WARN → BLS nonfarm** lead-lag per metro (the IC-defensibility chart).

## Phase 3 — Expansion + supply signals
- [ ] `ingest/indeed.py` — `misceres/indeed-scraper`, non-remote, posted ≤21d, dedupe company+title+location, per metro.
- [ ] `ingest/permits.py` — Census BPS MSA monthly.

## Phase 4 — Storage & indexing
- [ ] `docker compose up` Elasticsearch + Kibana (single-node, local).
- [ ] Indices: `signals` (long-format time series), `warn_notices` (raw), `metros` (dim). Bulk-load from Phase 1–3 outputs.

## Phase 5 — Roadmap (only if time)
- [ ] Bright Data SERP → office-lease news (commitment signal) — depends on Phase 0 unblock.
- [ ] Embeddings over notices/news + minimal web app (metro view, signals leaderboard, live-ops panel).

## Decisions still open
- Hackathon deadline? (drives how much of Phase 3–5 we attempt)
- Austin FRED series ID (resolve via FRED search).
- WARN→metro geocoding source (zip→CBSA crosswalk; HUD or Census).
