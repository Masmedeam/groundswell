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
    {"name": "get_metro_overview", "description": "Market snapshot for one metro: latest rent index, employment, permits with YoY. Use first when asked about a metro.",
     "input_schema": {"type": "object", "properties": {"metro_id": {"type": "string"}}, "required": ["metro_id"]}},
    {"name": "get_industry_mix", "description": "Latest annual private-sector employment by industry (NAICS sector) for a metro, from QCEW. Use to explain WHICH sectors drive a metro's labor demand and wage levels.",
     "input_schema": {"type": "object", "properties": {"metro_id": {"type": "string"}}, "required": ["metro_id"]}},
    {"name": "get_timeseries", "description": "Monthly time series for one or more metros and a signal series. Use to show trends/charts.",
     "input_schema": {"type": "object", "properties": {
         "metro_ids": {"type": "array", "items": {"type": "string"}},
         "series": {"type": "string", "enum": es_tools.SIGNAL_SERIES},
         "date_from": {"type": "string"}, "date_to": {"type": "string"}}, "required": ["metro_ids", "series"]}},
    {"name": "lead_lag", "description": "Estimate how many months a leading signal (e.g. warn_notices, postings, permits) leads a target (nonfarm_emp or rent_index) in a metro, via cross-correlation.",
     "input_schema": {"type": "object", "properties": {"metro_id": {"type": "string"}, "signal": {"type": "string"},
                                                       "target": {"type": "string"}}, "required": ["metro_id", "signal"]}},
    {"name": "compare_metros", "description": "Rank metros by a signal, latest value or YoY. Use for cross-market questions.",
     "input_schema": {"type": "object", "properties": {"series": {"type": "string"},
                                                       "metro_ids": {"type": "array", "items": {"type": "string"}},
                                                       "mode": {"type": "string", "enum": ["latest", "yoy"]}}, "required": ["series"]}},
    {"name": "get_zillow_metric", "description": "Query the Zillow family (e.g. zori_allhomes_sm, zhvi_allhomes_mid_sa, median_sale_price_sm, for_sale_inventory_sm, market_heat_index) at a level (Metro/County/City/Zip) for a metro.",
     "input_schema": {"type": "object", "properties": {"dataset": {"type": "string"}, "level": {"type": "string"},
                                                       "metro_id": {"type": "string"}, "date_from": {"type": "string"},
                                                       "date_to": {"type": "string"}}, "required": ["dataset"]}},
    {"name": "map_metric", "description": "Choropleth data: latest value of a Zillow dataset per Zip/County within a metro. Use for map/geographic questions.",
     "input_schema": {"type": "object", "properties": {"dataset": {"type": "string"}, "level": {"type": "string"},
                                                       "metro_id": {"type": "string"}, "period": {"type": "string"}}, "required": ["dataset", "metro_id"]}},
    {"name": "search_warn", "description": "Recent WARN layoff notices, filterable by metro/date/min affected workers.",
     "input_schema": {"type": "object", "properties": {"metro_id": {"type": "string"}, "date_from": {"type": "string"},
                                                       "date_to": {"type": "string"}, "min_workers": {"type": "integer"}}, "required": []}},
    {"name": "search_postings", "description": "Recent Indeed job postings, filterable by metro/date/keyword.",
     "input_schema": {"type": "object", "properties": {"metro_id": {"type": "string"}, "date_from": {"type": "string"},
                                                       "date_to": {"type": "string"}, "query": {"type": "string"}}, "required": []}},
]


def _system():
    try:
        ms = es_tools.metros()
        metro_lines = "\n".join(f"  - {mid}: {m.get('name')} ({m.get('zori_region')})" for mid, m in ms.items())
    except Exception:  # noqa: BLE001
        metro_lines = "  - sf, austin, phoenix, nyc, chicago"
    return f"""You are the GroundsWell analyst — a demand-side rental-market intelligence agent for institutional real estate underwriters.

Your job: help an underwriter defend or revise a rent-growth view for a US metro, grounded in evidence. Use the tools to pull data from Elasticsearch before making claims. Every quantitative statement must come from a tool result.

Doctrine:
- Lead with LEADING indicators (WARN layoffs = contraction; job postings = expansion; building permits = supply) and relate them to the rent target (ZORI rent_index) and employment (nonfarm_emp).
- Give a DIRECTION call and a DEFENSIBLE RANGE, never a false-precision point forecast. State confidence and that it's directional.
- ALWAYS frame "vs. what's priced in": compare your demand-side read to the CURRENT ZORI rent growth, then say explicitly what underwrite is defensible and what would need extra justification (e.g. "labor consistent with 3.5–5% YoY; underwrites above 6% need more support").
- Use get_industry_mix to explain WHICH sectors drive a metro (tech, health, etc.) and fhfa_hpi for ownership/buy-vs-rent pressure when relevant.
- Be concise and plain-spoken. Cite which signals drove your read. The right-hand panel renders your tool artifacts (charts/maps/tables) automatically — refer to them naturally ("see the chart"), don't paste raw number tables in prose.
- If data is thin (e.g. WARN only covers some metros), say so honestly.

Available metros (use these metro_id values):
{metro_lines}

Signal series: rent_index, nonfarm_emp, permits, postings, warn_notices, warn_affected, fhfa_hpi (FHFA house-price index), qcew_emp (QCEW employment).
Keep answers tight (a few short paragraphs). End a metro read with a one-line "Defensible underwrite:" takeaway."""


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
