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
}


def run_tool(name, args):
    if name not in DISPATCH:
        return {"summary": {"error": f"unknown tool {name}"}, "artifact": None}
    try:
        return DISPATCH[name](**args)
    except Exception as e:  # noqa: BLE001
        return {"summary": {"error": f"{type(e).__name__}: {e}"}, "artifact": None}
