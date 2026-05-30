"""GroundsWell agent — Claude tool-use loop over the ES tools.

Streams events: tool_call -> artifact -> token -> done. Conversation state is kept
server-side per session_id so the client never re-sends tool blocks.
"""
import json

from anthropic import Anthropic

from config import CLAUDE_API_KEY, MODEL
import es_tools

client = Anthropic(api_key=CLAUDE_API_KEY)
SESSIONS: dict[str, list] = {}

TOOLS = [
    {"name": "get_metro_overview", "description": "Artifact: metric_cards. Compact market snapshot for one metro: latest rent index, employment, permits with YoY. Use for quick answers when a full board is unnecessary.",
     "input_schema": {"type": "object", "properties": {"metro_id": {"type": "string"}}, "required": ["metro_id"]}},
    {"name": "get_market_snapshot", "description": "Artifact: snapshot_board. Full metro board across rent, labor, supply, ownership pressure, Apartment List vacancy/time-on-market, LinkedIn postings, WARN, permits, and FHFA. Use first for broad metro read, underwriting, firming/cooling, or 'what is going on in this market' questions.",
     "input_schema": {"type": "object", "properties": {"metro_id": {"type": "string"}}, "required": ["metro_id"]}},
    {"name": "get_industry_mix", "description": "Artifact: bar. Latest annual private-sector employment by industry (NAICS sector) for a metro, from QCEW. Use to explain WHICH sectors drive a metro's labor demand and wage levels.",
     "input_schema": {"type": "object", "properties": {"metro_id": {"type": "string"}}, "required": ["metro_id"]}},
    {"name": "get_timeseries", "description": "Artifact: timeseries. Monthly time series for one or more metros and one signal series. Use for trend questions, historical context, and single-signal comparisons across metros.",
     "input_schema": {"type": "object", "properties": {
         "metro_ids": {"type": "array", "items": {"type": "string"}},
         "series": {"type": "string", "enum": es_tools.SIGNAL_SERIES},
         "date_from": {"type": "string"}, "date_to": {"type": "string"}}, "required": ["metro_ids", "series"]}},
    {"name": "lead_lag", "description": "Artifact: timeseries with lead annotation. Estimate how many months a leading signal (WARN, postings, permits, LinkedIn) leads a target (nonfarm_emp or rent_index) in a metro. Use for explicit lead/lag or predictive signal questions.",
     "input_schema": {"type": "object", "properties": {"metro_id": {"type": "string"}, "signal": {"type": "string"},
                                                       "target": {"type": "string"}}, "required": ["metro_id", "signal"]}},
    {"name": "compare_metros", "description": "Artifact: bar. Rank metros by one signal, latest value or YoY. Use when the user asks for a simple ranking on one metric.",
     "input_schema": {"type": "object", "properties": {"series": {"type": "string"},
                                                       "metro_ids": {"type": "array", "items": {"type": "string"}},
                                                       "mode": {"type": "string", "enum": ["latest", "yoy"]}}, "required": ["series"]}},
    {"name": "compare_market_board", "description": "Artifact: heatmap. Cross-metro signal board across several indicators. Use for 'compare markets', 'which metro is strongest/weakest', or multi-signal screening questions.",
     "input_schema": {"type": "object", "properties": {"metro_ids": {"type": "array", "items": {"type": "string"}},
                                                       "series": {"type": "array", "items": {"type": "string"}},
                                                       "mode": {"type": "string", "enum": ["latest", "yoy"]}}, "required": []}},
    {"name": "get_zillow_metric", "description": "Artifact: timeseries. Query Zillow metrics (e.g. zori_allhomes_sm, zhvi_allhomes_mid_sa, median_sale_price_sm, for_sale_inventory_sm, market_heat_index) at Metro/County/City/Zip level.",
     "input_schema": {"type": "object", "properties": {"dataset": {"type": "string"}, "level": {"type": "string"},
                                                       "metro_id": {"type": "string"}, "date_from": {"type": "string"},
                                                       "date_to": {"type": "string"}}, "required": ["dataset"]}},
    {"name": "map_metric", "description": "Artifact: map. Latest Zillow metric by Zip/County within a metro. Use for geography, submarket, neighborhood, ZIP, county, and heat-map questions.",
     "input_schema": {"type": "object", "properties": {"dataset": {"type": "string"}, "level": {"type": "string"},
                                                       "metro_id": {"type": "string"}, "period": {"type": "string"}}, "required": ["dataset", "metro_id"]}},
    {"name": "get_warn_timeline", "description": "Artifact: event_timeline. Monthly WARN notices/affected workers with recent event list. Use before a raw WARN table when the user asks about layoffs, demand risk, or recent labor contraction.",
     "input_schema": {"type": "object", "properties": {"metro_id": {"type": "string"}, "date_from": {"type": "string"},
                                                       "date_to": {"type": "string"}, "min_workers": {"type": "integer"}}, "required": []}},
    {"name": "get_postings_timeline", "description": "Artifact: event_timeline. Monthly job-posting counts with recent postings from LinkedIn/Indeed. Use for hiring momentum, expansion pressure, live job pulse, or keyword-specific hiring questions.",
     "input_schema": {"type": "object", "properties": {"metro_id": {"type": "string"}, "date_from": {"type": "string"},
                                                       "date_to": {"type": "string"}, "query": {"type": "string"}}, "required": []}},
    {"name": "search_warn", "description": "Artifact: table. Recent WARN layoff notices, filterable by metro/date/min affected workers. Use when the user asks to inspect notices or companies.",
     "input_schema": {"type": "object", "properties": {"metro_id": {"type": "string"}, "date_from": {"type": "string"},
                                                       "date_to": {"type": "string"}, "min_workers": {"type": "integer"}}, "required": []}},
    {"name": "search_postings", "description": "Artifact: table. Job postings from historical Indeed plus live LinkedIn snapshots, filterable by metro/date/keyword. Use when the user asks to inspect individual postings.",
     "input_schema": {"type": "object", "properties": {"metro_id": {"type": "string"}, "date_from": {"type": "string"},
                                                       "date_to": {"type": "string"}, "query": {"type": "string"}}, "required": []}},
    {"name": "get_live_comps", "description": "Artifact: comps. Live/current-state comps from Apartments.com rent properties or Redfin for-sale listings. Use for comps, listings, rent ranges, sale prices, amenities, and current property-level market pulse.",
     "input_schema": {"type": "object", "properties": {"metro_id": {"type": "string"},
                                                       "source": {"type": "string", "enum": ["apartments", "redfin"]},
                                                       "price_min": {"type": "number"}, "price_max": {"type": "number"},
                                                       "beds": {"type": "integer"}}, "required": []}},
]


def _system():
    try:
        ms = es_tools.metros()
        metro_lines = "\n".join(f"  - {mid}: {m.get('name')} ({m.get('zori_region')})" for mid, m in ms.items())
    except Exception:  # noqa: BLE001
        metro_lines = "  - sf, austin, phoenix, nyc, chicago"
    return f"""You are the HomeStar agent — a rental-market intelligence analyst for institutional real estate underwriters.

Your job: help an underwriter defend or revise a rent-growth view for a US metro, grounded in evidence. Use the tools to pull data from Elasticsearch before making claims. Every quantitative statement must come from a tool result.

Data hierarchy:
- Treat ZORI/rent_index as the rent target, not a leading signal.
- Lead with true demand indicators: WARN layoffs as contraction pressure, job postings/LinkedIn snapshots as expansion pressure, employment as labor confirmation, and JOLTS where available.
- Use permits, FHFA/ZHVI/ownership pressure, wages, rent-vs-own, and Apartments.com listings as descriptive context unless a tool result clearly frames them otherwise.
- LinkedIn and Apartments.com are live/current-state snapshots. Use them as market pulse evidence, not as long backtested time series.
- Historical Indeed postings are discontinued/stale after early 2025 where present; live LinkedIn is the fresher hiring signal.

Doctrine:
- Lead with LEADING indicators and relate them to the rent target (ZORI rent_index) and employment (nonfarm_emp).
- Give a DIRECTION call and a DEFENSIBLE RANGE, never a false-precision point forecast. State confidence and that it's directional.
- ALWAYS frame "vs. what's priced in": compare your demand-side read to the CURRENT ZORI rent growth, then say explicitly what underwrite is defensible and what would need extra justification (e.g. "labor consistent with 3.5–5% YoY; underwrites above 6% need more support").
- Use get_industry_mix to explain WHICH sectors drive a metro (tech, health, etc.) and fhfa_hpi for ownership/buy-vs-rent pressure when relevant.
- Keep historical signals, live snapshots, descriptive context, and derived/backtest-style evidence separate in the prose.
- Be concise and plain-spoken. Cite which signals drove your read. The right-hand panel renders your tool artifacts (charts/maps/tables) automatically — refer to them naturally ("see the chart"), don't paste raw number tables in prose.
- If data is thin or coverage differs by metro/source, say so honestly.

Right-panel artifact choices:
- Broad one-metro read: get_market_snapshot, then add get_timeseries or get_warn_timeline only if it supports the answer.
- Cross-metro screen: compare_market_board for multi-signal views; compare_metros for one-metric rankings.
- Geography/submarket: map_metric.
- Layoffs/hiring momentum: get_warn_timeline or get_postings_timeline; use search_* only for detailed rows.
- Property comps/current listings: get_live_comps.

Available metros (use these metro_id values):
{metro_lines}

Signal series: {", ".join(es_tools.SIGNAL_SERIES)}.
Keep answers tight (a few short paragraphs). End a metro read with a one-line "HomeStar read:" or "Defensible underwrite:" takeaway."""


def run(session_id, user_message, max_steps=8):
    msgs = SESSIONS.setdefault(session_id, [])
    msgs.append({"role": "user", "content": user_message})
    system = _system()
    for _ in range(max_steps):
        with client.messages.stream(model=MODEL, max_tokens=2048, system=system,
                                    tools=TOOLS, messages=msgs) as stream:
            for ev in stream:
                if ev.type == "content_block_delta" and getattr(ev.delta, "type", None) == "text_delta":
                    yield {"type": "token", "text": ev.delta.text}
            final = stream.get_final_message()
        tool_results = []
        assistant_content = []
        for block in final.content:
            if block.type == "text":
                assistant_content.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                assistant_content.append({"type": "tool_use", "id": block.id,
                                          "name": block.name, "input": block.input})
                yield {"type": "tool_call", "name": block.name, "input": block.input}
                out = es_tools.run_tool(block.name, block.input)
                if out.get("artifact"):
                    yield {"type": "artifact", "artifact": out["artifact"]}
                tool_results.append({"type": "tool_result", "tool_use_id": block.id,
                                     "content": json.dumps(out.get("summary", {}))})
        msgs.append({"role": "assistant", "content": assistant_content})
        if final.stop_reason == "tool_use":
            msgs.append({"role": "user", "content": tool_results})
            continue
        break
    yield {"type": "done"}
