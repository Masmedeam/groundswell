"""Market context documents derived from structured signals.

These records are compact retrieval documents for the chat app. They summarize
the latest evidence by metro and topic while preserving source/series fields so
the backend can cite the underlying structured indices.
"""
import pandas as pd

from .. import store
from ..config import METROS


TOPICS = {
    "rent_index": ("rent momentum", "Zillow rent index"),
    "nonfarm_emp": ("labor demand", "FRED nonfarm employment"),
    "permits": ("supply pressure", "building permits"),
    "warn_notices": ("layoff risk", "WARN notice count"),
    "warn_affected": ("layoff risk", "WARN affected workers"),
    "fhfa_hpi": ("ownership pressure", "FHFA house price index"),
    "qcew_emp": ("industry labor base", "BLS QCEW covered employment"),
    "postings": ("hiring demand", "Indeed job posting count"),
    "linkedin_postings": ("hiring demand", "LinkedIn job posting count"),
    "apartment_list_rent": ("rent level", "Apartment List rent estimate"),
    "apartment_list_vacancy": ("vacancy", "Apartment List vacancy index"),
    "apartment_list_time_on_market": ("leasing velocity", "Apartment List time on market"),
}


def _fmt(v):
    if pd.isna(v):
        return "unknown"
    if abs(v) >= 1000:
        return f"{v:,.0f}"
    return f"{v:.2f}".rstrip("0").rstrip(".")


def ingest():
    now = pd.Timestamp.utcnow()
    con = store.connect()
    if "signals" not in store.table_names():
        return {"signals": None, "tables": {}}
    sig = con.execute("SELECT * FROM signals").df()
    sig["date"] = pd.to_datetime(sig["date"], errors="coerce")
    docs = []
    metro_names = {m["metro_id"]: m["name"] for m in METROS}

    for (metro_id, series), g in sig.dropna(subset=["date"]).groupby(["metro_id", "series"]):
        if series not in TOPICS:
            continue
        g = g.sort_values("date")
        latest = g.iloc[-1]
        prev = g[g["date"] <= latest["date"] - pd.DateOffset(years=1)]
        yoy = None
        if not prev.empty and pd.notna(prev.iloc[-1]["value"]) and prev.iloc[-1]["value"] != 0:
            yoy = (latest["value"] / prev.iloc[-1]["value"] - 1) * 100
        topic, label = TOPICS[series]
        metro = metro_names.get(metro_id, metro_id)
        parts = [
            f"{metro} {topic}: latest {label} is {_fmt(latest['value'])}",
            f"for {latest['date'].date().isoformat()}",
        ]
        if yoy is not None and pd.notna(yoy):
            parts.append(f"with year-over-year change of {yoy:.1f}%")
        text = " ".join(parts) + "."
        docs.append({
            "doc_id": f"{metro_id}:{series}:{latest['date'].date().isoformat()}",
            "doc_type": "market_signal_summary",
            "metro_id": metro_id,
            "metro_name": metro,
            "topic": topic,
            "series": series,
            "date": latest["date"],
            "value": latest["value"],
            "source": latest.get("source"),
            "text": text,
            "ingested_at": now,
        })

    df = pd.DataFrame(docs)
    return {"signals": None, "tables": {"market_context_docs": df}}
