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

SIGNAL_SERIES = ["rent_index", "nonfarm_emp", "permits", "postings", "warn_notices",
                 "warn_affected", "fhfa_hpi", "qcew_emp"]
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
    "get_industry_mix": get_industry_mix,
    "get_timeseries": get_timeseries,
    "lead_lag": lead_lag,
    "compare_metros": compare_metros,
    "get_zillow_metric": get_zillow_metric,
    "map_metric": map_metric,
    "search_warn": search_warn,
    "search_postings": search_postings,
}


def run_tool(name, args):
    if name not in DISPATCH:
        return {"summary": {"error": f"unknown tool {name}"}, "artifact": None}
    try:
        return DISPATCH[name](**args)
    except Exception as e:  # noqa: BLE001
        return {"summary": {"error": f"{type(e).__name__}: {e}"}, "artifact": None}
