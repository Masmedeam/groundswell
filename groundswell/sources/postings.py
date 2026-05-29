"""Indeed job postings — the expansion-side leading indicator (via Apify).

Counterpart to WARN (contraction). For each metro we query a spread of broad
occupations to approximate overall hiring demand, dedupe by job id, and roll up a
monthly `postings` count per metro (a hiring-activity nowcast that builds history
as it's re-run).

  - signals: canonical `postings` per metro (monthly count of fresh postings)
  - tables.job_postings: notice-level postings (title, company, location, salary, dates)
"""
import json

import pandas as pd
import requests

from ..config import APIFY_TOKEN, DATA_RAW, METROS

ACTOR = "misceres~indeed-scraper"
# broad occupations spanning sectors, to approximate total labor demand per metro
QUERIES = [
    "software engineer", "registered nurse", "sales associate",
    "accountant", "warehouse associate", "project manager",
]
KEEP = [
    "id", "positionName", "company", "location", "salary", "jobType",
    "postedAt", "postingDateParsed", "url", "scrapedAt", "isExpired", "searchInput",
]
RAW_PATH = DATA_RAW / "indeed_postings.json"


def _run(position, location, max_items, country="US"):
    inp = {
        "position": position, "country": country, "location": location,
        "maxItems": max_items, "parseCompanyDetails": False, "saveOnlyUniqueItems": True,
    }
    url = f"https://api.apify.com/v2/acts/{ACTOR}/run-sync-get-dataset-items?token={APIFY_TOKEN}&timeout=300"
    try:
        r = requests.post(url, json=inp, timeout=330)
        d = r.json()
    except Exception as e:  # noqa: BLE001
        print(f"      run failed ({position} @ {location}): {e}", flush=True)
        return []
    return [] if isinstance(d, dict) else d  # dict => error object


def ingest(max_items=75, refresh=False):
    if not APIFY_TOKEN:
        raise RuntimeError("APIFY_TOKEN not set; cannot run Indeed Apify actor")
    now = pd.Timestamp.utcnow()
    if RAW_PATH.exists() and not refresh:
        rows = json.loads(RAW_PATH.read_text())
        print(f"  using cached {RAW_PATH.name} ({len(rows)} postings); --refresh to re-pull")
    else:
        rows = []
        for m in METROS:
            loc = m["zori_region"]
            print(f"    metro {m['metro_id']} ({loc})…", flush=True)
            for q in QUERIES:
                for it in _run(q, loc, max_items):
                    rec = {k: it.get(k) for k in KEEP}
                    rec["metro_id"] = m["metro_id"]
                    rec["query"] = q
                    rows.append(rec)
            print(f"      {sum(1 for r in rows if r['metro_id'] == m['metro_id'])} postings so far", flush=True)
        RAW_PATH.write_text(json.dumps(rows))

    df = pd.DataFrame(rows)
    if df.empty:
        return {"signals": None, "tables": {}}
    df = df.drop_duplicates(subset=["metro_id", "id"]).copy()
    df["postingDateParsed"] = (
        pd.to_datetime(df.get("postingDateParsed"), errors="coerce", utc=True).dt.tz_localize(None)
    )
    df["ingested_at"] = now

    d = df.dropna(subset=["postingDateParsed"]).copy()
    sig = None
    if not d.empty:
        d["date"] = d["postingDateParsed"].dt.to_period("M").dt.to_timestamp()
        g = d.groupby(["metro_id", "date"]).agg(value=("id", "nunique")).reset_index()
        g["series"] = "postings"
        g["source"] = "Apify:Indeed"
        g["ingested_at"] = now
        sig = g[["metro_id", "date", "series", "value", "source", "ingested_at"]]

    return {"signals": sig, "tables": {"job_postings": df}, "n_postings": len(df)}
