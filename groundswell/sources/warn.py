"""WARN layoff filings — the hero leading indicator.

Runs the Apify multi-state WARN actor across all states + DC, full history, caches
the raw JSON (so we never re-pay), tags each notice to a metro, and rolls matched
notices up to monthly `warn_notices` / `warn_affected` signals.

  - signals: canonical warn_notices / warn_affected per metro (monthly)
  - tables.warn_notices: full national notice-level dataset (the big layoff table)
"""
import json
import hashlib
import html
import io
import re
import time
from urllib.parse import urljoin

import pandas as pd
import requests

from ..config import APIFY_TOKEN, DATA_RAW
from ..crosswalk import to_metro
from ..fetch import download_brightdata

ACTOR = "jungle_synthesizer~warn-layoffs-aggregator"
ALL_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL",
    "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT",
    "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI",
    "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
]
RAW_PATH = DATA_RAW / "warn_notices.json"
TX_BASE = "https://www.twc.texas.gov"
AZ_BASE = "https://www.azjobconnection.gov"


def _notice_id(*parts):
    raw = "|".join("" if p is None else str(p) for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _texas_items():
    """Official Texas TWC WARN Excel files. Current public page exposes 2020+."""
    rows = []
    out = DATA_RAW / "warn_tx"
    out.mkdir(parents=True, exist_ok=True)
    for year in range(2020, pd.Timestamp.utcnow().year + 1):
        url = f"{TX_BASE}/sites/default/files/oei/docs/warn-act-listings-{year}-twc.xlsx"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=90)
        data = r.content if r.status_code == 200 and len(r.content) > 1000 else None
        if not data:
            continue
        path = out / f"tx_warn_{year}.xlsx"
        path.write_bytes(data)
        df = pd.read_excel(io.BytesIO(data))
        df.columns = [str(c).strip() for c in df.columns]
        for _, r in df.iterrows():
            notice_date = pd.to_datetime(r.get("NOTICE_DATE"), errors="coerce")
            effective_date = pd.to_datetime(r.get("LayOff_Date"), errors="coerce")
            employer = r.get("JOB_SITE_NAME")
            city = r.get("CITY_NAME")
            county = r.get("COUNTY_NAME")
            affected = r.get("TOTAL_LAYOFF_NUMBER")
            rows.append({
                "notice_id": _notice_id("TX", notice_date, employer, city, county, affected),
                "source_state": "TX",
                "source_url": url,
                "employer_name": employer,
                "employer_address": None,
                "city": city,
                "county": county,
                "state": "TX",
                "zip": None,
                "notice_date": None if pd.isna(notice_date) else notice_date.date().isoformat(),
                "effective_date": None if pd.isna(effective_date) else effective_date.date().isoformat(),
                "affected_workers": affected,
                "layoff_type": "layoff",
                "layoff_type_raw": None,
                "closure_permanent": None,
                "region": r.get("WDA_NAME"),
                "scraped_at": pd.Timestamp.utcnow().isoformat(),
            })
    return rows


def _strip_tags(s):
    return html.unescape(re.sub(r"<[^>]+>", "\n", s or ""))


def _az_items():
    """Arizona Job Connection public WARN search pages.

    The list pages expose employer/city/zip/notice date for all pages. Some detail
    pages are public and include affected workers; newer records can 401, so list
    rows are still kept as WARN notice evidence.
    """
    rows = []
    empty_pages = 0
    for page in range(1, 80):
        url = f"{AZ_BASE}/search/warn_lookups?q%5Bnotice_eq%5D=true"
        if page > 1:
            url = f"{AZ_BASE}/search/warn_lookups?page={page}&q%5Bnotice_eq%5D=true"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        text = r.text if r.status_code == 200 else ""
        if "/search/warn_lookups/" not in text:
            text = download_brightdata(url, timeout=120)
        found = 0
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", text or "", flags=re.S | re.I):
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.S | re.I)
            if len(cells) < 6:
                continue
            m = re.search(r'href="([^"]*?/search/warn_lookups/(\d+))"', cells[0])
            if not m:
                continue
            found += 1
            detail_url = urljoin(AZ_BASE, m.group(1))
            employer = _strip_tags(cells[0]).strip()
            city = _strip_tags(cells[1]).strip() or None
            zip_code = _strip_tags(cells[2]).strip() or None
            region = _strip_tags(cells[3]).strip() or None
            notice_date = _strip_tags(cells[4]).strip() or None
            layoff_type = _strip_tags(cells[5]).strip() or None
            nd = pd.to_datetime(notice_date, errors="coerce")
            rows.append({
                "notice_id": _notice_id("AZ", m.group(2), notice_date, employer, city, zip_code),
                "source_state": "AZ",
                "source_url": detail_url,
                "employer_name": employer,
                "employer_address": None,
                "city": city,
                "county": None,
                "state": "AZ",
                "zip": zip_code,
                "notice_date": None if pd.isna(nd) else nd.date().isoformat(),
                "effective_date": None,
                "affected_workers": None,
                "layoff_type": layoff_type,
                "layoff_type_raw": layoff_type,
                "closure_permanent": None,
                "region": region,
                "scraped_at": pd.Timestamp.utcnow().isoformat(),
            })
        if found == 0:
            empty_pages += 1
            if page > 30 and empty_pages >= 5:
                break
        else:
            empty_pages = 0
        if page > 30 and found < 25:
            break
    return rows


def _official_items():
    rows = []
    for name, fn in (("TX", _texas_items), ("AZ", _az_items)):
        try:
            got = fn()
            print(f"  official {name} WARN rows: {len(got):,}")
            rows.extend(got)
        except Exception as e:  # noqa: BLE001
            print(f"  official {name} WARN failed: {e}")
    return rows


def _run_actor(states, since, max_items, poll_secs=10, max_minutes=90):
    if not APIFY_TOKEN:
        raise RuntimeError("APIFY_TOKEN is not set; cannot run WARN Apify actor")
    base = f"https://api.apify.com/v2/acts/{ACTOR}"
    payload = {
        "sp_intended_usage": "Real estate market-signal research (rent-growth leading indicators)",
        "sp_improvement_suggestions": "Metro-level rollups; daily refresh",
        "sp_contact": "masmoudimedsalim@gmail.com",
        "states": states,
        "noticeDateFrom": since,
        "noticeDateTo": "",
        "minAffectedWorkers": 0,
        "onlyClosures": False,
        "maxItems": max_items,
    }
    r = requests.post(f"{base}/runs?token={APIFY_TOKEN}", json=payload, timeout=60)
    r.raise_for_status()
    run = r.json()["data"]
    run_id, ds = run["id"], run["defaultDatasetId"]
    deadline = time.time() + max_minutes * 60
    status = run["status"]
    while time.time() < deadline:
        s = requests.get(
            f"https://api.apify.com/v2/actor-runs/{run_id}?token={APIFY_TOKEN}", timeout=30
        ).json()["data"]
        status = s["status"]
        if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            break
        print(f"    warn actor status={status} (elapsed {int(s.get('stats',{}).get('runTimeSecs',0))}s)…", flush=True)
        time.sleep(poll_secs)
    if status != "SUCCEEDED":
        raise RuntimeError(f"WARN Apify actor did not succeed: status={status}, run_id={run_id}")
    items = requests.get(
        f"https://api.apify.com/v2/datasets/{ds}/items?token={APIFY_TOKEN}&format=json&clean=true",
        timeout=300,
    ).json()
    return items, status


def ingest(states=None, since="2015-01-01", max_items=200000, refresh=False):
    now = pd.Timestamp.utcnow()
    states = states or ALL_STATES
    if RAW_PATH.exists() and not refresh:
        items = json.loads(RAW_PATH.read_text())
        print(f"  using cached {RAW_PATH.name} ({len(items)} notices); --refresh to re-pull")
    else:
        items, status = _run_actor(states, since, max_items)
        print(f"  warn actor finished status={status}, {len(items)} notices")
    items = items + _official_items()
    if refresh:
        RAW_PATH.write_text(json.dumps(items))

    df = pd.DataFrame(items)
    if df.empty:
        return {"signals": None, "tables": {}}

    df["metro_id"] = df.apply(lambda r: to_metro(r.get("state"), r.get("county")), axis=1)
    df["notice_date"] = pd.to_datetime(df.get("notice_date"), errors="coerce")
    df["affected_workers"] = pd.to_numeric(df.get("affected_workers"), errors="coerce")
    df["ingested_at"] = now

    matched = df.dropna(subset=["metro_id", "notice_date"]).copy()
    sig = None
    if not matched.empty:
        matched["date"] = matched["notice_date"].dt.to_period("M").dt.to_timestamp()
        matched["aff"] = pd.to_numeric(matched.get("affected_workers"), errors="coerce")
        g = (
            matched.groupby(["metro_id", "date"])
            .agg(warn_notices=("notice_id", "count"), warn_affected=("aff", "sum"))
            .reset_index()
        )
        sig = g.melt(
            id_vars=["metro_id", "date"],
            value_vars=["warn_notices", "warn_affected"],
            var_name="series",
            value_name="value",
        )
        sig["source"] = "Apify:WARN"
        sig["ingested_at"] = now

    return {
        "signals": sig,
        "tables": {"warn_notices": df},
        "n_notices": len(df),
        "n_matched": int(df["metro_id"].notna().sum()),
    }
