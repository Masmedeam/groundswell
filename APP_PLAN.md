# GroundsWell — Web App Implementation Plan & Design Guidelines

> Agentic, conversational analytics over the Groundswell dataset. Ask a question in plain
> English → the agent queries Elasticsearch via tool calls → **left panel** streams a textual
> answer, **right panel** renders the supporting charts, maps, and "show-your-work" sources.
> Audience: institutional rental underwriters. Principle: **defensibility over slickness.**

## 1. Product flow
1. **Landing** — a single centered input (Google-style): *"Ask about any U.S. rental market…"* with 3–4 example prompt chips. Nothing else.
2. **Submit** → transitions into the **two-panel workspace** (`/c/[sessionId]`):
   - **Left (≈45%): Chat.** User questions + agent's streamed textual answers (markdown). No charts here — just prose, with inline references like `[1]` that link to right-panel artifacts.
   - **Right (≈55%): Canvas.** Visual analytics for the current answer — metric cards, time-series charts, cross-metro comparisons, choropleth maps, data tables, and a collapsible **Sources / show-your-work** tray. Updates each turn; prior turns' canvases are scrollable.
3. Follow-up questions refine the same session (agent keeps context).

## 2. Architecture
```
Browser (Next.js)  ──SSE──►  Agent API (FastAPI)  ──►  Claude (tool use)
   left: chat tokens                │                         │ decides tools
   right: artifacts                 │ executes tools          ▼
                                    └────────────────►  Elasticsearch (:9201)
                                                         signals / zillow_indices /
                                                         warn_notices / job_postings /
                                                         fred_series / permits_raw / metros
```
- **Frontend:** Next.js (App Router) + TypeScript + Tailwind + **shadcn/ui**. Charts: **Recharts** (line/bar) — simple + elegant. Maps: **MapLibre GL** (no API token) with Census TIGER GeoJSON (CBSA/county/ZIP) for choropleths. State: minimal (React Query + a session store).
- **Agent API:** **FastAPI** (Python — reuses our ES client + `store`/`es` code). Endpoints: `POST /chat` (SSE stream), `GET /artifact/{id}/sources`, `GET /health`. Uses **Claude with tool use + prompt caching** (cache the system prompt + tool schemas + metro reference).
- **Why this stack:** matches the existing Python/ES pipeline, Claude tool-use fits the "agent function calls" model exactly, shadcn+Recharts+MapLibre is the elegant-minimal sweet spot with no paid tokens.

## 3. The agent (Claude tool use)
**System prompt** encodes the Groundswell doctrine: market-level demand-side reads; give **direction + a defensible range, never a false-precision point forecast**; always cite sources, sample size, date range, and confidence; lead with leading indicators (WARN/postings) vs. the rent target (ZORI). 

**Tools = ES queries** (each returns JSON data *and* an artifact spec for the right panel):
| Tool | Purpose | Artifact |
|---|---|---|
| `get_metro_overview(metro_id)` | latest rent-growth YoY, employment trend, permits, WARN/postings direction + confidence | metric_cards + summary |
| `get_timeseries(metro_ids[], series[], range)` | aligned monthly series from `signals` | timeseries (line) |
| `lead_lag(metro_id, signal, target)` | cross-correlation + estimated lead (months) | timeseries w/ annotated lead |
| `compare_metros(series, metro_ids[], period)` | cross-market ranking | bar / heat board |
| `get_zillow_metric(metric, level, region, range)` | granular rent/value/inventory/days/price-cut | timeseries or table |
| `map_metric(metric, level, metro_id, period)` | ZIP/county choropleth within a metro | map |
| `search_warn(metro_id, range, min_workers)` | layoff notices | table + count |
| `search_postings(metro_id, range, query)` | hiring postings | table + agg |
| `semantic_search(query)` *(Phase C)* | embeddings over WARN/news notes | table |

**Streaming protocol (SSE events):** `tool_call` (status chip), `artifact` (right panel), `token` (left chat text), `done`. Each `artifact` carries `sources[]` = `{label, es_index, query, n, date_range, url}` powering the show-your-work tray and inline `[n]` links.

**Artifact schema** (frontend has one renderer per `type`):
```json
{ "id","type":"metric_cards|timeseries|bar|map|table|sources",
  "title","data","encoding":{"x","y","series","color"},
  "annotations":[], "confidence":"low|moderate|directional",
  "sources":[{"label","es_index","query","n","date_range","url"}] }
```

## 4. Design guidelines (minimal • elegant • institutional)
- **Aesthetic:** generous whitespace, calm and document-like (not a toy chatbot). Restrained palette: near-black text on white/`#FAFAFA`; neutral grays; **one accent** (a deep groundswell green ~`#10644C`); semantic green/amber/red only for direction (firming/stable/cooling). Font: **Inter** (or system). Subtle motion only (150–200ms fades; no bounce).
- **Layout:** resizable split (default 45/55), each panel independently scrolls; canvas collapsible to focus on chat. Mobile: stack (chat first, canvas below).
- **Left/chat:** minimal — no heavy bubbles; user prompts in a subtle container, agent answers as clean prose with inline `[n]` refs. Streaming cursor. Sticky composer at bottom.
- **Right/canvas:** cards on a quiet background; one idea per card; titles + a one-line plain-English takeaway; consistent per-metro colors; **ranges shaded, not single lines** where it's a forecast; every card has a "Sources" affordance.
- **Defensibility UX (the differentiator):** every number is one click from its evidence — ES query, source URL, sample size, date range. Confidence stated explicitly ("based on N markets / X years — treat as directional"). No `R²=0.847` theater.
- **Minimal actions:** type and read. Example chips on landing; click a number/chart to reveal sources; that's the core interaction surface.
- **Accessibility:** WCAG AA contrast, keyboard-navigable, colorblind-safe direction encoding (icon + color).

## 5. Docker / deployment
New services added to `docker/docker-compose.yml` on the existing network (so the API reaches ES by service name):
- `groundswell-api` (FastAPI) — port **8000** (fallback 8010), env `ES_URL=http://elasticsearch:9200`, `CLAUDE_API_KEY`.
- `groundswell-web` (Next.js) — port **3000** (fallback 3010), env `NEXT_PUBLIC_API_URL`.
- Reuses existing `elasticsearch` (host :9201) + `kibana`. (Verify 3000/8000 are free — this machine already runs other services.)

## 6. Build scope — full Phase B in one pass (decided)
The first implementation delivers the **complete two-panel analytics app**, not a skeleton:
- Landing input → split workspace; FastAPI `/chat` SSE; Claude tool-use agent.
- **Full tool suite:** `get_metro_overview`, `get_timeseries`, `lead_lag`, `compare_metros`, `get_zillow_metric`, `map_metric`, `search_warn`, `search_postings`.
- **All artifact renderers:** metric_cards, timeseries (with ranges/annotations), bar/heat board, **choropleth map**, table, and the **show-your-work sources tray** with inline `[n]` references.
- Multi-turn session context + per-metro color system + streaming.

**Deferred to a later pass (Phase C):** embeddings + `semantic_search` over WARN/news (ES `dense_vector`), saved views, export-chart-to-PNG (the IC-memo screenshot).

## 7. Decisions
**Resolved:** LLM = **Claude API** (Anthropic, tool-use + caching); frontend = **Next.js + Tailwind + shadcn/ui + Recharts + MapLibre** (no map token); maps = MapLibre + Census TIGER GeoJSON; first build = **full Phase B**.

**Still open:**
1. **`CLAUDE_API_KEY`** — needed in `.env` before the agent can run. *(blocker to start implementation)*
2. **Embeddings provider** (Phase C): Voyage AI (Anthropic-recommended) vs OpenAI vs local.
3. **Ports** if 3000 (web) / 8000 (api) clash with existing services on this machine → fall back to 3010 / 8010.
