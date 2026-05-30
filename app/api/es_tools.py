"""Elasticsearch query tools for the GroundsWell agent.

Each tool returns {"summary": <compact dict for the model>, "artifact": <for the UI>}.
Artifacts carry their own `sources` (index + query + n + date range) for show-your-work.
"""
import json
import uuid
from pathlib import Path

from elasticsearch import Elasticsearch

from config import ES_URL, INDEX_PREFIX

es = Elasticsearch(ES_URL, request_timeout=60)

_GEO = Path(__file__).resolve().parent / "geo"


def _load_geo(name):
    p = _GEO / name
    return json.loads(p.read_text()) if p.exists() else {}


ZIP_CENTROIDS = _load_geo("zip_centroids.json")
COUNTY_CENTROIDS = _load_geo("county_centroids.json")


def _centroid(level, region_name, state):
    if level == "Zip":
        return ZIP_CENTROIDS.get(str(region_name))
    if level == "County":
        nm = str(region_name or "").lower().replace(" county", "").replace(" parish", "").strip()
        return COUNTY_CENTROIDS.get(f"{nm}|{state}")
    return None

SIGNAL_SERIES = [
    "rent_index",
    "nonfarm_emp",
    "permits",
    "postings",
    "linkedin_postings",
    "warn_notices",
    "warn_affected",
    "fhfa_hpi",
    "qcew_emp",
    "apartment_list_rent",
    "apartment_list_vacancy",
    "apartment_list_time_on_market",
]
ZILLOW_LEVELS = ["Metro", "County", "City", "Zip"]

# NAICS sector code -> label (QCEW agglvl 74)
NAICS = {
    "11": "Agriculture", "21": "Mining", "22": "Utilities", "23": "Construction",
    "31-33": "Manufacturing", "42": "Wholesale trade", "44-45": "Retail trade",
    "48-49": "Transport & warehousing", "51": "Information", "52": "Finance & insurance",
    "53": "Real estate", "54": "Professional & technical", "55": "Management",
    "56": "Admin & waste svcs", "61": "Education", "62": "Health care & social",
    "71": "Arts & entertainment", "72": "Accommodation & food", "81": "Other services",
    "92": "Public administration",
}


def _idx(name):
    return INDEX_PREFIX + name


def term(field, value):
    return {"term": {f"{field}.keyword": value}}


def _points(index, filters, sort_field="date", size=4000):
    """Return sorted [{date, value}] for a filtered query."""
    body = {
        "size": size,
        "query": {"bool": {"filter": filters}},
        "sort": [{sort_field: "asc"}],
        "_source": ["date", "value"],
    }
    res = es.search(index=index, body=body)
    out = []
    for h in res["hits"]["hits"]:
        s = h["_source"]
        if s.get("value") is not None and s.get("date"):
            out.append({"date": s["date"][:10], "value": s["value"]})
    return out


def _yoy(points):
    """Year-over-year % change from the last 13 monthly points."""
    if len(points) < 13:
        return None
    last, prior = points[-1]["value"], points[-13]["value"]
    if not prior:
        return None
    return round((last / prior - 1) * 100, 2)


def metros():
    res = es.search(index=_idx("metros"), body={"size": 50, "query": {"match_all": {}}})
    return {h["_source"]["metro_id"]: h["_source"] for h in res["hits"]["hits"]}


def _src(index, query_desc, n, points):
    rng = f"{points[0]['date']}..{points[-1]['date']}" if points else "n/a"
    return {"label": index, "es_index": index, "query": query_desc, "n": n, "date_range": rng}


def _artifact(atype, title, **kw):
    return {"id": str(uuid.uuid4())[:8], "type": atype, "title": title, **kw}


def _fmt_num(v):
    if isinstance(v, float):
        return round(v, 2)
    return v


def _latest_signal(metro_id, series):
    pts = _points(_idx("signals"), [term("metro_id", metro_id), term("series", series)])
    if not pts:
        return None, []
    return {
        "latest": _fmt_num(pts[-1]["value"]),
        "as_of": pts[-1]["date"],
        "yoy_pct": _yoy(pts),
        "trend": pts[-18:],
        "n": len(pts),
    }, pts


def _direction(value, higher_is_better=True):
    if value is None:
        return "neutral"
    if value > 0.5:
        return "positive" if higher_is_better else "negative"
    if value < -0.5:
        return "negative" if higher_is_better else "positive"
    return "neutral"


def _month_buckets(rows, date_field, value_field=None):
    buckets = {}
    for row in rows:
        dt = row.get(date_field)
        if not dt:
            continue
        month = dt[:7]
        b = buckets.setdefault(month, {"date": f"{month}-01", "count": 0, "value": 0})
        b["count"] += 1
        if value_field:
            b["value"] += row.get(value_field) or 0
    return [buckets[k] for k in sorted(buckets)]


# ---------------- tools ----------------

def get_metro_overview(metro_id):
    meta = metros().get(metro_id, {"name": metro_id})
    cards, sources = [], []
    for series, label, unit in [
        ("rent_index", "Rent index (ZORI)", "YoY"),
        ("nonfarm_emp", "Employment (nonfarm)", "YoY"),
        ("permits", "Building permits", "YoY"),
    ]:
        pts = _points(_idx("signals"), [term("metro_id", metro_id), term("series", series)])
        if not pts:
            continue
        yoy = _yoy(pts)
        cards.append({"label": label, "latest": pts[-1]["value"], "as_of": pts[-1]["date"],
                      "yoy_pct": yoy, "trend": pts[-24:]})
        sources.append(_src("groundswell-signals", f"metro_id={metro_id} series={series}", len(pts), pts))
    summary = {"metro": meta.get("name"), "cards": [{k: c[k] for k in ("label", "latest", "as_of", "yoy_pct")} for c in cards]}
    art = _artifact("metric_cards", f"{meta.get('name', metro_id)} — market snapshot", cards=cards,
                    confidence="directional", sources=sources)
    return {"summary": summary, "artifact": art}


def get_market_snapshot(metro_id):
    """Board view of rent, labor, supply, ownership, and live pulse signals."""
    meta = metros().get(metro_id, {"name": metro_id})
    groups = [
        ("Rent", [
            ("rent_index", "ZORI rent", True),
            ("apartment_list_rent", "Apartment List rent", True),
            ("apartment_list_vacancy", "Vacancy", False),
            ("apartment_list_time_on_market", "Time on market", False),
        ]),
        ("Labor", [
            ("nonfarm_emp", "Nonfarm employment", True),
            ("postings", "Indeed postings", True),
            ("linkedin_postings", "LinkedIn postings", True),
            ("warn_affected", "WARN affected", False),
        ]),
        ("Supply / Ownership", [
            ("permits", "Building permits", False),
            ("fhfa_hpi", "FHFA HPI", True),
            ("qcew_emp", "QCEW employment", True),
        ]),
    ]
    board, sources = [], []
    for group, series_defs in groups:
        items = []
        for series, label, higher_is_better in series_defs:
            latest, pts = _latest_signal(metro_id, series)
            if not latest:
                continue
            latest.update({
                "label": label,
                "series": series,
                "direction": _direction(latest["yoy_pct"], higher_is_better=higher_is_better),
            })
            items.append(latest)
            sources.append(_src("groundswell-signals", f"metro_id={metro_id} series={series}", len(pts), pts))
        if items:
            board.append({"group": group, "items": items})
    summary = {
        "metro": meta.get("name", metro_id),
        "signals": [
            {"group": g["group"], "label": i["label"], "latest": i["latest"],
             "as_of": i["as_of"], "yoy_pct": i["yoy_pct"], "direction": i["direction"]}
            for g in board for i in g["items"]
        ],
    }
    art = _artifact("snapshot_board", f"{meta.get('name', metro_id)} market board",
                    groups=board, confidence="directional", sources=sources)
    return {"summary": summary, "artifact": art}


def get_timeseries(metro_ids, series, date_from=None, date_to=None):
    lines, sources, summary = [], [], {}
    for mid in metro_ids:
        filters = [term("metro_id", mid), term("series", series)]
        if date_from or date_to:
            r = {}
            if date_from:
                r["gte"] = date_from
            if date_to:
                r["lte"] = date_to
            filters.append({"range": {"date": r}})
        pts = _points(_idx("signals"), filters)
        if not pts:
            continue
        lines.append({"metro_id": mid, "points": pts})
        summary[mid] = {"latest": pts[-1]["value"], "as_of": pts[-1]["date"], "yoy_pct": _yoy(pts)}
        sources.append(_src("groundswell-signals", f"metro_id={mid} series={series}", len(pts), pts))
    art = _artifact("timeseries", f"{series} over time", series=series, lines=lines,
                    encoding={"x": "date", "y": "value"}, sources=sources)
    return {"summary": summary, "artifact": art}


def lead_lag(metro_id, signal, target="nonfarm_emp", max_lag=12):
    sp = _points(_idx("signals"), [term("metro_id", metro_id), term("series", signal)])
    tp = _points(_idx("signals"), [term("metro_id", metro_id), term("series", target)])
    sm = {p["date"][:7]: p["value"] for p in sp}
    tm = {p["date"][:7]: p["value"] for p in tp}
    months = sorted(set(sm) & set(tm))
    summary = {"metro_id": metro_id, "signal": signal, "target": target}
    if len(months) < 24:
        summary["note"] = "insufficient overlapping history for a reliable lead-lag"
        return {"summary": summary, "artifact": _artifact("timeseries", f"{signal} vs {target}", lines=[], sources=[])}
    s = [sm[m] for m in months]
    t = [tm[m] for m in months]

    def corr(a, b):
        n = len(a)
        ma, mb = sum(a) / n, sum(b) / n
        num = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
        da = sum((x - ma) ** 2 for x in a) ** 0.5
        db = sum((x - mb) ** 2 for x in b) ** 0.5
        return num / (da * db) if da and db else 0

    best = {"lag": 0, "corr": -2}
    for lag in range(0, max_lag + 1):  # signal leads target by `lag` months
        if len(s) - lag < 18:
            break
        c = corr(s[: len(s) - lag], t[lag:])
        if abs(c) > abs(best["corr"]):
            best = {"lag": lag, "corr": round(c, 3)}
    summary.update(best)
    summary["interpretation"] = (
        f"{signal} leads {target} by ~{best['lag']} months (corr {best['corr']}) in {metro_id}"
    )
    art = _artifact("timeseries", f"{signal} leads {target} by ~{best['lag']} mo ({metro_id})",
                    series=f"{signal} vs {target}",
                    lines=[{"metro_id": f"{metro_id}:{signal}", "points": sp},
                           {"metro_id": f"{metro_id}:{target}", "points": tp}],
                    annotations=[{"lead_months": best["lag"], "corr": best["corr"]}],
                    confidence="directional",
                    sources=[_src("groundswell-signals", f"metro_id={metro_id} series in [{signal},{target}]",
                                  len(sp) + len(tp), sp or tp)])
    return {"summary": summary, "artifact": art}


def compare_metros(series, metro_ids=None, mode="yoy"):
    metro_ids = metro_ids or list(metros().keys())
    bars, sources = [], []
    for mid in metro_ids:
        pts = _points(_idx("signals"), [term("metro_id", mid), term("series", series)])
        if not pts:
            continue
        val = _yoy(pts) if mode == "yoy" else pts[-1]["value"]
        if val is None:
            continue
        bars.append({"metro_id": mid, "value": val, "as_of": pts[-1]["date"]})
        sources.append(_src("groundswell-signals", f"metro_id={mid} series={series}", len(pts), pts))
    bars.sort(key=lambda b: b["value"], reverse=True)
    art = _artifact("bar", f"{series} by metro ({mode})", metric=f"{series} ({mode})", bars=bars, sources=sources)
    return {"summary": {"mode": mode, "series": series, "ranking": bars}, "artifact": art}


def compare_market_board(metro_ids=None, series=None, mode="yoy"):
    """Heatmap-style cross-metro board across several signals."""
    metro_ids = metro_ids or list(metros().keys())
    series = series or ["rent_index", "nonfarm_emp", "linkedin_postings", "warn_affected",
                        "permits", "apartment_list_vacancy", "fhfa_hpi"]
    rows, sources = [], []
    for mid in metro_ids:
        cells = []
        for s in series:
            pts = _points(_idx("signals"), [term("metro_id", mid), term("series", s)])
            if not pts:
                cells.append({"series": s, "value": None, "as_of": None, "tone": "empty"})
                continue
            val = _yoy(pts) if mode == "yoy" else pts[-1]["value"]
            higher_is_better = s not in {"warn_affected", "warn_notices", "apartment_list_vacancy",
                                         "apartment_list_time_on_market", "permits"}
            cells.append({"series": s, "value": _fmt_num(val), "as_of": pts[-1]["date"],
                          "tone": _direction(val, higher_is_better=higher_is_better)})
            sources.append(_src("groundswell-signals", f"metro_id={mid} series={s}", len(pts), pts))
        rows.append({"metro_id": mid, "cells": cells})
    art = _artifact("heatmap", f"Metro signal board ({mode})", rows=rows, series=series, mode=mode,
                    confidence="directional", sources=sources)
    return {"summary": {"mode": mode, "series": series, "rows": rows}, "artifact": art}


def get_zillow_metric(dataset, level="Metro", metro_id=None, date_from=None, date_to=None):
    filters = [term("dataset", dataset), term("level", level)]
    if metro_id:
        filters.append(term("metro_id", metro_id))
    if date_from or date_to:
        r = {}
        if date_from:
            r["gte"] = date_from
        if date_to:
            r["lte"] = date_to
        filters.append({"range": {"date": r}})
    pts = _points(_idx("zillow_indices"), filters, size=6000)
    art = _artifact("timeseries", f"{dataset} ({level}{', ' + metro_id if metro_id else ''})",
                    series=dataset, lines=[{"metro_id": metro_id or level, "points": pts}],
                    sources=[_src("groundswell-zillow_indices", f"dataset={dataset} level={level} metro_id={metro_id}", len(pts), pts)])
    summary = {"dataset": dataset, "level": level, "n": len(pts),
               "latest": pts[-1] if pts else None}
    return {"summary": summary, "artifact": art}


def map_metric(dataset, level="Zip", metro_id=None, period=None):
    """Choropleth: latest (or `period`) value per region within a metro."""
    filters = [term("dataset", dataset), term("level", level)]
    if metro_id:
        filters.append(term("metro_id", metro_id))
    if period:
        filters.append({"range": {"date": {"gte": period + "-01", "lte": period + "-28"}}})
    body = {
        "size": 0,
        "query": {"bool": {"filter": filters}},
        "aggs": {"regions": {"terms": {"field": "region_name.keyword", "size": 2000},
                             "aggs": {"latest": {"top_hits": {"size": 1, "sort": [{"date": "desc"}],
                                                              "_source": ["region_name", "region_id", "value", "date", "county_name", "state"]}}}}},
    }
    res = es.search(index=_idx("zillow_indices"), body=body)
    regions = []
    for b in res["aggregations"]["regions"]["buckets"]:
        src = b["latest"]["hits"]["hits"][0]["_source"]
        c = _centroid(level, src.get("region_name"), src.get("state"))
        regions.append({"region": src.get("region_name"), "region_id": src.get("region_id"),
                        "value": src.get("value"), "as_of": (src.get("date") or "")[:10],
                        "lat": c[0] if c else None, "lng": c[1] if c else None})
    art = _artifact("map", f"{dataset} by {level} — {metro_id or 'US'}", dataset=dataset, level=level,
                    metro_id=metro_id, regions=regions,
                    sources=[{"label": "groundswell-zillow_indices", "es_index": "groundswell-zillow_indices",
                              "query": f"dataset={dataset} level={level} metro_id={metro_id}", "n": len(regions),
                              "date_range": period or "latest"}])
    return {"summary": {"dataset": dataset, "level": level, "n_regions": len(regions)}, "artifact": art}


def get_warn_timeline(metro_id=None, date_from=None, date_to=None, min_workers=0, size=500):
    filters = []
    if metro_id:
        filters.append(term("metro_id", metro_id))
    if min_workers:
        filters.append({"range": {"affected_workers": {"gte": min_workers}}})
    if date_from or date_to:
        r = {}
        if date_from:
            r["gte"] = date_from
        if date_to:
            r["lte"] = date_to
        filters.append({"range": {"notice_date": r}})
    body = {"size": size, "query": {"bool": {"filter": filters}} if filters else {"match_all": {}},
            "sort": [{"notice_date": {"order": "desc", "missing": "_last"}}],
            "_source": ["employer_name", "city", "county", "state", "affected_workers",
                        "notice_date", "effective_date", "layoff_type", "source_url", "metro_id"]}
    res = es.search(index=_idx("warn_notices"), body=body)
    rows = [h["_source"] for h in res["hits"]["hits"]]
    total = res["hits"]["total"]["value"]
    buckets = _month_buckets(rows, "notice_date", "affected_workers")
    events = rows[:40]
    affected = sum((r.get("affected_workers") or 0) for r in rows)
    art = _artifact("event_timeline", f"WARN timeline — {metro_id or 'all metros'}",
                    buckets=buckets, events=events, count_label="notices",
                    value_label="affected workers",
                    summary_text=f"{total} notices; {affected:,} affected workers in returned sample",
                    sources=[{"label": "groundswell-warn_notices", "es_index": "groundswell-warn_notices",
                              "query": f"metro_id={metro_id} min_workers={min_workers}",
                              "n": total, "date_range": f"{date_from or '*'}..{date_to or '*'}"}])
    return {"summary": {"total_notices": total, "sample_affected": affected,
                        "months": len(buckets), "recent_events": events[:8]}, "artifact": art}


def get_postings_timeline(metro_id=None, date_from=None, date_to=None, query=None, size=500):
    rows, total = [], 0

    def _collect(index, title_field, date_field, source_label):
        filters = []
        if metro_id:
            filters.append(term("metro_id", metro_id))
        if query:
            filters.append({"match": {title_field: query}})
        if date_from or date_to:
            r = {}
            if date_from:
                r["gte"] = date_from
            if date_to:
                r["lte"] = date_to
            filters.append({"range": {date_field: r}})
        body = {"size": size, "query": {"bool": {"filter": filters}} if filters else {"match_all": {}},
                "sort": [{date_field: {"order": "desc", "missing": "_last"}}],
                "_source": [title_field, "company", "location", date_field, "url", "source", "metro_id"]}
        try:
            res = es.search(index=index, body=body)
        except Exception:
            return 0, []
        out = []
        for h in res["hits"]["hits"]:
            s = h["_source"]
            out.append({"title": s.get(title_field), "company": s.get("company"),
                        "location": s.get("location"), "date": s.get(date_field),
                        "url": s.get("url"), "source": s.get("source") or source_label,
                        "metro_id": s.get("metro_id")})
        return res["hits"]["total"]["value"], out

    indeed_total, indeed_rows = _collect(_idx("job_postings"), "positionName", "postingDateParsed", "Indeed")
    linkedin_total, linkedin_rows = _collect(_idx("linkedin_job_postings"), "title", "postedAt", "LinkedIn")
    total = indeed_total + linkedin_total
    rows = sorted(linkedin_rows + indeed_rows, key=lambda r: r.get("date") or "", reverse=True)
    buckets = _month_buckets(rows, "date")
    art = _artifact("event_timeline", f"Job postings timeline — {metro_id or 'all metros'}",
                    buckets=buckets, events=rows[:40], count_label="postings",
                    value_label="postings",
                    summary_text=f"{total} postings across Indeed and LinkedIn (shown {min(len(rows), 40)})",
                    sources=[{"label": "job postings", "es_index": "groundswell-job_postings,groundswell-linkedin_job_postings",
                              "query": f"metro_id={metro_id} q={query}", "n": total,
                              "date_range": f"{date_from or '*'}..{date_to or '*'}"}])
    return {"summary": {"total_postings": total, "months": len(buckets), "recent_events": rows[:8]},
            "artifact": art}


def search_warn(metro_id=None, date_from=None, date_to=None, min_workers=0, size=50):
    filters = []
    if metro_id:
        filters.append(term("metro_id", metro_id))
    if min_workers:
        filters.append({"range": {"affected_workers": {"gte": min_workers}}})
    if date_from or date_to:
        r = {}
        if date_from:
            r["gte"] = date_from
        if date_to:
            r["lte"] = date_to
        filters.append({"range": {"notice_date": r}})
    body = {"size": size, "query": {"bool": {"filter": filters}} if filters else {"match_all": {}},
            "sort": [{"notice_date": "desc"}],
            "_source": ["employer_name", "city", "county", "state", "affected_workers", "notice_date", "layoff_type", "source_url"]}
    res = es.search(index=_idx("warn_notices"), body=body)
    total = res["hits"]["total"]["value"]
    rows = [h["_source"] for h in res["hits"]["hits"]]
    affected = sum((r.get("affected_workers") or 0) for r in rows)
    art = _artifact("table", f"WARN layoff notices — {metro_id or 'all'}", columns=list(rows[0].keys()) if rows else [],
                    rows=rows, summary_text=f"{total} notices; {affected} affected (shown {len(rows)})",
                    sources=[{"label": "groundswell-warn_notices", "es_index": "groundswell-warn_notices",
                              "query": f"metro_id={metro_id} min_workers={min_workers}", "n": total, "date_range": f"{date_from or '*'}..{date_to or '*'}"}])
    return {"summary": {"total_notices": total, "total_affected": affected, "shown": len(rows)}, "artifact": art}


def search_postings(metro_id=None, date_from=None, date_to=None, query=None, size=50):
    rows, total, source_counts = [], 0, {}

    def _search(index, title_field, date_field, source_label):
        filters = []
        if metro_id:
            filters.append(term("metro_id", metro_id))
        if query:
            filters.append({"match": {title_field: query}})
        if date_from or date_to:
            r = {}
            if date_from:
                r["gte"] = date_from
            if date_to:
                r["lte"] = date_to
            filters.append({"range": {date_field: r}})
        body = {"size": size, "query": {"bool": {"filter": filters}} if filters else {"match_all": {}},
                "sort": [{date_field: {"order": "desc", "missing": "_last"}}],
                "_source": [title_field, "company", "location", "salary", date_field, "url", "query", "source"]}
        try:
            res = es.search(index=index, body=body)
        except Exception:
            return 0, []
        hits = []
        for h in res["hits"]["hits"]:
            s = h["_source"]
            hits.append({
                "title": s.get(title_field),
                "company": s.get("company"),
                "location": s.get("location"),
                "salary": s.get("salary"),
                "date": s.get(date_field),
                "url": s.get("url"),
                "query": s.get("query"),
                "source": s.get("source") or source_label,
            })
        return res["hits"]["total"]["value"], hits

    indeed_total, indeed_rows = _search(_idx("job_postings"), "positionName", "postingDateParsed", "Apify:Indeed")
    linkedin_total, linkedin_rows = _search(_idx("linkedin_job_postings"), "title", "postedAt", "LinkedIn")
    total = indeed_total + linkedin_total
    source_counts = {"indeed": indeed_total, "linkedin": linkedin_total}
    rows = (linkedin_rows + indeed_rows)[:size]
    art = _artifact("table", f"Job postings — {metro_id or 'all'}", columns=list(rows[0].keys()) if rows else [],
                    rows=rows, summary_text=f"{total} postings (shown {len(rows)})",
                    sources=[{"label": "job postings", "es_index": "groundswell-job_postings,groundswell-linkedin_job_postings",
                              "query": f"metro_id={metro_id} q={query}", "n": total, "date_range": f"{date_from or '*'}..{date_to or '*'}"}])
    return {"summary": {"total_postings": total, "source_counts": source_counts, "shown": len(rows)}, "artifact": art}


def get_live_comps(metro_id=None, source="apartments", price_min=None, price_max=None, beds=None, size=24):
    source = (source or "apartments").lower()
    if source in {"redfin", "sale", "sales", "for_sale"}:
        filters = []
        if metro_id:
            filters.append(term("metro_id", metro_id))
        if price_min or price_max:
            r = {}
            if price_min:
                r["gte"] = price_min
            if price_max:
                r["lte"] = price_max
            filters.append({"range": {"price": r}})
        if beds:
            filters.append({"range": {"beds": {"gte": beds}}})
        body = {"size": size, "query": {"bool": {"filter": filters}} if filters else {"match_all": {}},
                "sort": [{"scrapedAt": {"order": "desc", "missing": "_last"}}],
                "_source": ["address", "city", "state", "zip", "price", "beds", "baths", "sqFt",
                            "pricePerSqFt", "daysOnRedfin", "propertyType", "listingStatus",
                            "coverPhoto", "url", "metro_id", "latitude", "longitude"]}
        res = es.search(index=_idx("redfin_listings"), body=body)
        items = []
        for h in res["hits"]["hits"]:
            s = h["_source"]
            items.append({"title": s.get("address") or "Redfin listing",
                          "subtitle": ", ".join(x for x in [s.get("city"), s.get("state"), s.get("zip")] if x),
                          "price": s.get("price"), "beds": s.get("beds"), "baths": s.get("baths"),
                          "sqft": s.get("sqFt"), "price_per_sqft": s.get("pricePerSqFt"),
                          "days": s.get("daysOnRedfin"), "property_type": s.get("propertyType"),
                          "status": s.get("listingStatus"), "image": s.get("coverPhoto"),
                          "url": s.get("url"), "lat": s.get("latitude"), "lng": s.get("longitude")})
        idx = "groundswell-redfin_listings"
    else:
        filters = []
        if metro_id:
            filters.append(term("metro_id", metro_id))
        body = {"size": size, "query": {"bool": {"filter": filters}} if filters else {"match_all": {}},
                "sort": [{"finishedAt": {"order": "desc", "missing": "_last"}}],
                "_source": ["propertyName", "name", "address_full", "address_city", "address_state",
                            "address_postalCode", "pricing_rentRange", "rating", "url", "source_url",
                            "metro_id", "phone", "latitude", "longitude"]}
        res = es.search(index=_idx("apartments_com_properties"), body=body)
        items = []
        for h in res["hits"]["hits"]:
            s = h["_source"]
            items.append({"title": s.get("propertyName") or s.get("name") or s.get("address_full") or "Apartment comp",
                          "subtitle": s.get("address_full") or ", ".join(
                              x for x in [s.get("address_city"), s.get("address_state"), s.get("address_postalCode")] if x),
                          "price_text": s.get("pricing_rentRange"), "rating": s.get("rating"),
                          "phone": s.get("phone"), "url": s.get("url") or s.get("source_url"),
                          "lat": s.get("latitude"), "lng": s.get("longitude")})
        idx = "groundswell-apartments_com_properties"
    total = res["hits"]["total"]["value"]
    art = _artifact("comps", f"{'Redfin' if source in {'redfin', 'sale', 'sales', 'for_sale'} else 'Apartments.com'} comps — {metro_id or 'all metros'}",
                    source=source, items=items,
                    summary_text=f"{total} comps matched (shown {len(items)})",
                    sources=[{"label": idx, "es_index": idx,
                              "query": f"metro_id={metro_id} source={source} price={price_min}..{price_max} beds={beds}",
                              "n": total, "date_range": "latest snapshot"}])
    return {"summary": {"total": total, "shown": len(items), "items": items[:8]}, "artifact": art}


def get_industry_mix(metro_id, top=12):
    """Latest annual private-sector employment by NAICS sector (QCEW) for a metro."""
    idx = _idx("qcew")
    if not es.indices.exists(index=idx):
        return {"summary": {"note": "QCEW not loaded yet"}, "artifact": None}
    filters = [term("metro_id", metro_id), term("frequency", "annual"),
               term("own_code", "5"), {"term": {"agglvl_code": 74}}]  # agglvl_code is numeric in ES
    body = {"size": 8000, "query": {"bool": {"filter": filters}},
            "_source": ["industry_code", "annual_avg_emplvl", "total_annual_wages", "date", "year"]}
    res = es.search(index=idx, body=body)
    hits = [h["_source"] for h in res["hits"]["hits"]]
    if not hits:
        return {"summary": {"note": "no QCEW sector rows"}, "artifact": None}
    latest_year = max(int(h.get("year") or 0) for h in hits)
    agg = {}
    for h in hits:
        if int(h.get("year") or 0) != latest_year:
            continue
        code = str(h.get("industry_code"))
        emp = h.get("annual_avg_emplvl") or 0
        wages = h.get("total_annual_wages") or 0
        a = agg.setdefault(code, {"emp": 0, "wages": 0})
        a["emp"] += emp
        a["wages"] += wages
    bars = []
    for code, a in agg.items():
        if not a["emp"]:
            continue
        avg_wage = round(a["wages"] / a["emp"]) if a["emp"] else None
        bars.append({"metro_id": NAICS.get(code, code), "value": int(a["emp"]), "avg_annual_wage": avg_wage})
    bars.sort(key=lambda b: b["value"], reverse=True)
    bars = bars[:top]
    art = _artifact("bar", f"Industry employment mix — {metro_id} ({latest_year})",
                    metric="employees by sector", bars=bars,
                    sources=[{"label": "groundswell-qcew", "es_index": "groundswell-qcew",
                              "query": f"metro_id={metro_id} private sectors {latest_year}",
                              "n": len(hits), "date_range": str(latest_year)}])
    return {"summary": {"year": latest_year, "top_sectors": [{"sector": b["metro_id"], "emp": b["value"],
                        "avg_wage": b["avg_annual_wage"]} for b in bars[:6]]}, "artifact": art}


# ─────────────────────────────────────────────────────────────────────────────
# LAURIE-ENGINE TOOLS — Path B (JSON-on-disk, bypasses Elasticsearch).
# These 4 tools read data/laurie-engine/*.json directly. They expose Laurie's
# validated analytical engine — walk-forward lead-lag, detection-accuracy
# backtest, forecast-skill harness, rotation backtest, and live BD concessions
# snapshot — without requiring an ES loader. See data/laurie-engine/ contents
# + DATA.md at the repo root for the full data shape and provenance.
#
# These supplement (do not replace) the existing ES tools above. Metro IDs
# follow the project convention (sf/austin/phoenix/nyc/chicago plus 12 added
# in Laurie's metro-id-map.json: slc, philly, seattle, boston, boise,
# sacramento, denver, atlanta, dc, dallas, minneapolis, miami).
# ─────────────────────────────────────────────────────────────────────────────

_LE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "laurie-engine"
_LE_CACHE: dict[str, object] = {}


def _le_load(name):
    """Load and cache a laurie-engine JSON file by basename (no extension)."""
    if name not in _LE_CACHE:
        path = _LE_DIR / f"{name}.json"
        _LE_CACHE[name] = json.loads(path.read_text())
    return _LE_CACHE[name]


def _le_src(filename, query_desc, n, date_range="validated final state"):
    """Source disclosure for Laurie-engine JSON-backed tools. Parallels his
    _src() but points at data/laurie-engine/ instead of an ES index."""
    label = f"data/laurie-engine/{filename}"
    return {"label": label, "es_index": label, "query": query_desc,
            "n": n, "date_range": date_range}


def _le_metro_lookups():
    """Return (id_to_display_name, display_name_to_id) maps from
    data/laurie-engine/metro-id-map.json."""
    m = _le_load("metro-id-map")
    id_to_name = {mid: meta["display_name"] for mid, meta in m["metros"].items()}
    name_to_id = m["name_lookups"]["by_display_name"]
    return id_to_name, name_to_id


def get_detection_summary():
    """Headline engine validation: detection hit rate + skill vs baselines.
    Walk-forward, per-signal-lead rule, no lookahead. Across 17 metros.
    Sources: data/laurie-engine/{detection.json, forecast-skill.json}."""
    det = _le_load("detection")
    fs = _le_load("forecast-skill")
    overall = det["aggregate"]["overall"]["atSignalLead"]
    fs_overall = fs["aggregate"]["overall"]
    hit_rate = overall["hitRate"]
    n = overall["n"]
    hits = overall["hits"]
    median_lead = overall["medianDominantLead"]
    skill_p_pp = fs_overall["skill"]["vsPersistence"] * 100
    skill_b_pp = fs_overall["skill"]["vsBaseRate"] * 100
    bss_p = fs_overall["bss"]["vsPersistence"]
    bss_b = fs_overall["bss"]["vsBaseRate"]
    n_metros = len(det["aggregate"]["byMetro"])

    cards = [
        {"label": "Detection hit rate", "latest": f"{hit_rate * 100:.1f}%",
         "as_of": f"{hits} of {n} confirmed turns", "yoy_pct": None, "trend": []},
        {"label": "Median dominant lead", "latest": f"{median_lead} mo",
         "as_of": "lead from walk-forward refit at each turn", "yoy_pct": None, "trend": []},
        {"label": "Skill vs persistence", "latest": f"{skill_p_pp:+.1f} pp",
         "as_of": f"BSS = {bss_p:+.2f}  (engine vs trend-continuation)", "yoy_pct": None, "trend": []},
        {"label": "Skill vs climatology", "latest": f"{skill_b_pp:+.1f} pp",
         "as_of": f"BSS = {bss_b:+.2f}  (>0 = real skill)", "yoy_pct": None, "trend": []},
    ]

    by_metro = det["aggregate"]["byMetro"]
    per_metro = {m: {"hit_rate": round(v["atSignalLead"]["hitRate"], 3),
                     "n_turns": v["atSignalLead"]["n"]} for m, v in by_metro.items()}

    summary = {
        "headline": (f"{hit_rate * 100:.1f}% detection hit rate across {n_metros} metros "
                     f"({hits}/{n} confirmed turns, median {median_lead}mo lead)"),
        "hit_rate_pct": round(hit_rate * 100, 1),
        "n_turns": n, "hits": hits, "median_lead_mo": median_lead,
        "skill_vs_persistence_pp": round(skill_p_pp, 1),
        "skill_vs_base_rate_pp": round(skill_b_pp, 1),
        "bss_vs_persistence": round(bss_p, 2),
        "bss_vs_base_rate": round(bss_b, 2),
        "n_metros": n_metros,
        "methodology": "walk-forward, per-signal-lead rule, no lookahead. Each turn judged at the leadMonths of its dominant contributing signal at that turn's asOf.",
        "per_metro_hit_rates": per_metro,
        "drill_down_hint": "Per-metro signal validation available via get_signal_validation(metro_id).",
    }

    art = _artifact(
        "metric_cards",
        f"Engine validation — {hit_rate * 100:.1f}% hit rate across {n_metros} metros",
        cards=cards, confidence="directional",
        sources=[
            _le_src("detection.json",
                    "aggregate.overall.atSignalLead (per-signal-lead rule, walk-forward)",
                    n, date_range=f"{det['config']['startYM']} → {det['config']['endYM']}"),
            _le_src("forecast-skill.json",
                    "aggregate.overall (engine vs persistence + base-rate baselines, Brier + BSS)",
                    fs_overall["n"]),
        ],
    )
    return {"summary": summary, "artifact": art}


def get_signal_validation(metro_id):
    """Per-metro signal validation vs rent — which signals lead, by how many
    months, with what correlation, with honest flags (clean / wrong-sign /
    boundary-pinned / lags-not-leads / thin). The core drill-down tool for
    'why is X firming/softening?' questions. Source: results.json."""
    id_to_name, name_to_id = _le_metro_lookups()
    if metro_id not in id_to_name:
        return {"summary": {"error": f"unknown metro_id '{metro_id}'",
                            "valid_metro_ids": sorted(id_to_name.keys())},
                "artifact": None}
    metro_display = id_to_name[metro_id]
    results = _le_load("results")
    metro_rows = [r for r in results
                  if r["metro"] == metro_display and r["target"] == "rent"]
    if not metro_rows:
        return {"summary": {"metro_id": metro_id, "metro": metro_display,
                            "note": "no rent-target signals tested for this metro"},
                "artifact": None}

    metro_rows.sort(key=lambda r: abs(r["corr"]) if r["corr"] is not None else -1,
                    reverse=True)

    bars = []
    for r in metro_rows:
        if r["corr"] is None:
            continue
        is_clean = len(r["flags"]) == 0
        flag_note = "" if is_clean else f"  [{', '.join(r['flags'])}]"
        bars.append({
            "metro_id": r["signal"],
            "value": round(r["corr"], 3),
            "as_of": f"leads {r['leadMonths']}mo · n={r['nAtBestLag']}{flag_note}",
        })

    clean_rows = [r for r in metro_rows if len(r["flags"]) == 0 and r["corr"] is not None]
    n_clean = len(clean_rows)
    n_tested = len(metro_rows)

    # top_drivers: up to 3 ranked clean signals. NO PADDING — if fewer than 3
    # clean signals exist for this metro, top_drivers has fewer entries and
    # drivers_note states the honesty explicitly. Flagged signals are NEVER
    # promoted into top_drivers no matter how few clean signals exist —
    # discipline holds.
    top_drivers = [
        {"rank": i + 1, "signal": r["signal"], "leadMonths": r["leadMonths"],
         "corr": round(r["corr"], 2), "n": r["nAtBestLag"]}
        for i, r in enumerate(clean_rows[:3])
    ]

    if n_clean >= 3:
        headline = (
            f"{n_clean} clean signals validated for {metro_display}. "
            f"Top driver: {top_drivers[0]['signal']} leads "
            f"{top_drivers[0]['leadMonths']}mo at r={top_drivers[0]['corr']:.2f}."
        )
        drivers_note = f"top 3 drivers shown (of {n_clean} clean signals)"
    elif n_clean > 0:
        plural = "signals" if n_clean > 1 else "signal"
        headline = (
            f"Only {n_clean} clean {plural} validated for {metro_display} — fewer than 3. "
            f"Top driver: {top_drivers[0]['signal']} leads "
            f"{top_drivers[0]['leadMonths']}mo at r={top_drivers[0]['corr']:.2f}."
        )
        drivers_note = (
            f"only {n_clean} clean {plural} validated for {metro_display} — no padding; "
            f"remaining tested signals were flagged (see flagged_signals)"
        )
    else:
        headline = (
            f"No clean leading signal established for {metro_display} in this window."
        )
        drivers_note = (
            f"no clean leading signal established for {metro_display}; "
            f"all tested signals flagged (see flagged_signals)"
        )

    summary = {
        "metro_id": metro_id,
        "metro": metro_display,
        "headline": headline,
        "top_drivers": top_drivers,
        "drivers_note": drivers_note,
        "n_clean": n_clean,
        "n_signals_tested": n_tested,
        "clean_signals": [
            {"signal": r["signal"], "leadMonths": r["leadMonths"],
             "corr": round(r["corr"], 2), "n": r["nAtBestLag"]}
            for r in clean_rows
        ],
        "flagged_signals": [
            {"signal": r["signal"], "leadMonths": r["leadMonths"],
             "corr": round(r["corr"], 2) if r["corr"] is not None else None,
             "flags": r["flags"]}
            for r in metro_rows if len(r["flags"]) > 0
        ],
        "note": headline,
    }

    art = _artifact(
        "bar",
        f"{metro_display} — signal validation vs rent (Pearson r at best lag)",
        metric="correlation (Pearson r)",
        bars=bars,
        sources=[_le_src("results.json",
                          f"metro={metro_display} target=rent (all signals, clean + flagged)",
                          len(metro_rows))],
    )
    return {"summary": summary, "artifact": art}


def get_concessions_now(metro_id=None):
    """Live apartments.com concessions share per metro — the leading edge of
    rent (operators cut effective rent via concessions BEFORE face/asking rent
    moves; ZORI face-rent indices won't reflect a softening market for
    ~a quarter). Validated Bright Data snapshot from Laurie's Phase P pipeline.
    metro_id optional — no-arg returns the full ranked cohort across 17 metros;
    metro_id highlights that metro's relative position."""
    snap = _le_load("listings-live")
    fetched_at = snap.get("fetched_at", "unknown")
    metros_dict = snap["metros"]
    id_to_name, name_to_id = _le_metro_lookups()

    rows = []
    for display_name, m in metros_dict.items():
        if not isinstance(m, dict) or m.get("concessionShare") is None:
            continue
        mid = name_to_id.get(display_name, display_name.lower().replace(" ", "_"))
        rows.append({
            "metro_id": mid, "display_name": display_name,
            "share": m["concessionShare"], "n": m["n"],
            "median_asking_rent": m.get("medianAskingRent"),
            "concessions_count": m["concessionsCount"],
        })
    rows.sort(key=lambda r: r["share"], reverse=True)

    bars = [{
        "metro_id": r["display_name"],
        "value": round(r["share"] * 100, 1),
        "as_of": f"{r['concessions_count']}/{r['n']} buildings flagged",
    } for r in rows]

    high = [r for r in rows if r["share"] >= 0.75]
    low = [r for r in rows if r["share"] < 0.35]

    focus = None
    if metro_id:
        focus_rows = [r for r in rows if r["metro_id"] == metro_id]
        if focus_rows:
            f = focus_rows[0]
            rank = rows.index(f) + 1
            focus = {
                "metro_id": metro_id, "metro": f["display_name"],
                "concession_share_pct": round(f["share"] * 100, 1),
                "n_buildings_sampled": f["n"],
                "median_asking_rent_usd": f["median_asking_rent"],
                "rank": rank, "n_metros": len(rows),
                "interpretation": (
                    "heavy concessions — Sun Belt oversupply texture" if f["share"] >= 0.75
                    else "moderate concessions — softening texture" if f["share"] >= 0.50
                    else "low concessions — constrained / landlord-favored"
                ),
            }

    summary = {
        "as_of": fetched_at[:10],
        "n_metros": len(rows),
        "focus_metro": focus,
        "high_concession_metros": [
            {"metro": r["display_name"], "share_pct": round(r["share"] * 100, 1)}
            for r in high
        ],
        "low_concession_metros": [
            {"metro": r["display_name"], "share_pct": round(r["share"] * 100, 1)}
            for r in low
        ],
        "note": (
            "Live snapshot via Bright Data Web Unlocker + Sonnet 4.6 → apartments.com "
            "search-results, ~40 buildings sampled per metro. Sun Belt cluster "
            "(Atlanta/Phoenix/Philly/Denver/Austin/Dallas/SLC) at 79-90%; "
            "constrained coastal markets (NY/SF/Chicago) at 24-30%. This is the "
            "validated reference snapshot; Salim's ES pipeline runs an independent "
            "live BD scrape for refreshable data."
        ),
    }

    title = (
        f"Apartments.com concessions — {focus['metro']} (rank {focus['rank']}/{focus['n_metros']})"
        if focus
        else "Apartments.com concessions — 17 metros (Sun Belt oversupply vs constrained coastal)"
    )
    art = _artifact(
        "bar", title,
        metric="% of buildings offering concessions",
        bars=bars,
        sources=[_le_src(
            "listings-live.json",
            "Bright Data Web Unlocker → Sonnet 4.6 → apartments.com search-results",
            len(rows), date_range=f"as of {fetched_at[:10]}",
        )],
    )
    return {"summary": summary, "artifact": art}


def get_rotation_cohort():
    """Phase O price-rotation backtest cohort — the honest 'tried trading the
    signal' result. Reinforces that the engine is an early-warning tool, NOT
    a trading signal. Source: backtest-rotation.json."""
    bt = _le_load("backtest-rotation")
    h = bt["headline"]
    cfg = bt["config"]
    positions = bt["strategy"]["positions"]

    def _ann(p):
        if p["return"] is None or p["holdMonths"] <= 0:
            return None
        return (1 + p["return"]) ** (12 / p["holdMonths"]) - 1

    def _fmt_pct(v):
        return "—" if v is None else f"{v * 100:+.1f}%"

    sorted_pos = sorted(positions, key=lambda p: (p["entryYM"], p["metro"]))
    rows = []
    for p in sorted_pos:
        if p["return"] is None or p["holdMonths"] == 0:
            continue
        rows.append({
            "metro": p["metro"],
            "entry": p["entryYM"],
            "exit": p["exitYM"],
            "hold_mo": p["holdMonths"],
            "return": _fmt_pct(p["return"]),
            "annualized": _fmt_pct(_ann(p)),
            "exit_reason": p["exitReason"],
            "dominant_signal": p.get("dominantSignal") or "—",
        })

    columns = ["metro", "entry", "exit", "hold_mo", "return", "annualized",
               "exit_reason", "dominant_signal"]

    summary = {
        "strategy_mean_annualized_pct": round(h["strategyMeanAnnualized"] * 100, 1),
        "equal_weight_mean_annualized_pct": round(h["equalWeightMeanAnnualized"] * 100, 1),
        "momentum_mean_annualized_pct": round(h["momentumMeanAnnualized"] * 100, 1),
        "broad_index_annualized_pct": (
            round(h["broadIndexAnnualized"] * 100, 1)
            if h.get("broadIndexAnnualized") is not None else None
        ),
        "strategy_minus_equal_pp": (
            round(h["strategyMinusEqualPp"], 1)
            if h["strategyMinusEqualPp"] is not None else None
        ),
        "strategy_minus_momentum_pp": (
            round(h["strategyMinusMomentumPp"], 1)
            if h["strategyMinusMomentumPp"] is not None else None
        ),
        "pre_stated_thesis_held": h["preStatedHeld"],
        "n_positions": len(rows),
        "window": f"{cfg['startYM']} → {cfg['endYM']}",
        "hold_rule": f"min {cfg['minHoldMonths']}mo, max {cfg['maxHoldMonths']}mo (Phase O fixed-exit)",
        "return_measure": (
            "Zillow ZHVI metro price index (residential repeat-sales) — "
            "appreciation-only proxy for the CRE valuation channel, NOT deal-level prices"
        ),
        "key_finding": (
            "Pre-stated thesis FAILED. Strategy underperformed equal-weight by ~0.4 pp "
            "and momentum by ~1.7 pp on per-position annualized return. "
            "Worked 2019-22 (Sun Belt rebound, 15 take-gain exits at +20-50%); "
            "failed 2023 cohort (labor was right but rate cycle dominated valuations — "
            "Austin/Dallas 2023 entries at -10 to -17% as ZHVI corrected from the "
            "2022 peak). The honest read: this is an early-warning tool for the "
            "AVOID and BUILD decision types, NOT a trading signal for BUY-existing "
            "positions in illiquid CRE."
        ),
    }

    art = _artifact(
        "table",
        f"Rotation backtest — {len(rows)} positions · pre-stated thesis FAILED",
        columns=columns, rows=rows,
        summary_text=(
            f"Strategy {h['strategyMeanAnnualized'] * 100:.1f}% ann  vs  "
            f"equal-weight {h['equalWeightMeanAnnualized'] * 100:.1f}%  vs  "
            f"momentum {h['momentumMeanAnnualized'] * 100:.1f}%  →  thesis FAILED. "
            f"Worked 2019-22, failed 2023 (rate cycle dominated valuations)."
        ),
        confidence="moderate",
        sources=[_le_src(
            "backtest-rotation.json",
            "strategy.positions (Phase O fixed 2-4yr hold, walk-forward, no lookahead)",
            len(rows), date_range=f"{cfg['startYM']} → {cfg['endYM']}",
        )],
    )
    return {"summary": summary, "artifact": art}


# ─────────────────────────────────────────────────────────────────────────────
# DISPATCH — Salim's ES tools above + Laurie-engine JSON tools.
# ─────────────────────────────────────────────────────────────────────────────

DISPATCH = {
    "get_metro_overview": get_metro_overview,
    "get_market_snapshot": get_market_snapshot,
    "get_industry_mix": get_industry_mix,
    "get_timeseries": get_timeseries,
    "lead_lag": lead_lag,
    "compare_metros": compare_metros,
    "compare_market_board": compare_market_board,
    "get_zillow_metric": get_zillow_metric,
    "map_metric": map_metric,
    "get_warn_timeline": get_warn_timeline,
    "get_postings_timeline": get_postings_timeline,
    "search_warn": search_warn,
    "search_postings": search_postings,
    "get_live_comps": get_live_comps,
    # Laurie-engine (Path B, JSON-on-disk)
    "get_detection_summary": get_detection_summary,
    "get_signal_validation": get_signal_validation,
    "get_concessions_now": get_concessions_now,
    "get_rotation_cohort": get_rotation_cohort,
}


def run_tool(name, args):
    if name not in DISPATCH:
        return {"summary": {"error": f"unknown tool {name}"}, "artifact": None}
    try:
        return DISPATCH[name](**args)
    except Exception as e:  # noqa: BLE001
        return {"summary": {"error": f"{type(e).__name__}: {e}"}, "artifact": None}
