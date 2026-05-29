"""FRED ingester — keyless fredgraph CSV, optionally enriched via the FRED API.

Produces:
  - signals: canonical `nonfarm_emp` per metro (aligned series for modeling)
  - tables.fred_series: the broad labor/housing/rent family (national + per-metro)

Set FRED_API_KEY in .env to expand each metro with many more series via search.
"""
import io
import time

import pandas as pd
import requests

from ..config import FRED_API_KEY, METROS
from ..fetch import curl_get, download_brightdata

GRAPH = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={id}"
API = "https://api.stlouisfed.org/fred"

# Rich national context, all keyless via fredgraph.
NATIONAL = [
    "PAYEMS", "UNRATE", "CIVPART", "EMRATIO", "U6RATE",
    "JTSJOL", "JTSHIL", "JTSQUL", "JTSLDL", "JTSTSL",
    "ICSA", "CCSA", "AWHAETP", "CES0500000003",
    "PERMIT", "HOUST", "RRVRUSQ156N",
    "CUSR0000SEHA", "CUUR0000SEHA", "CPIAUCSL",
]
# candidate per-metro suffixes appended to the 7-char metro prefix (verified at runtime).
# Suffix set confirmed by catalog research; metro GDP (RGMP/NGMP{cbsa}) added separately.
METRO_SUFFIXES = [
    "NA", "NAN", "URN", "UR", "LFN", "LF",
    "MFG", "MFGN", "INFO", "INFON", "BPPRIV", "BPPRIVSA", "PCPI",
]


def _fred_text(series_id):
    """Fetch a fredgraph CSV. Fail-fast (short timeout + 1 retry); on throttle/block
    fall back to Bright Data. Clean 404 -> None (invalid series id)."""
    url = GRAPH.format(id=series_id)
    code, body = curl_get(url, max_time=15)
    if code == "200" and body.lstrip().lower().startswith("observation_date"):
        return body
    if code in ("400", "404"):
        return None  # invalid series id
    try:  # transient/block -> Bright Data
        bd = download_brightdata(url, timeout=30)
        if bd.lstrip().lower().startswith("observation_date"):
            return bd
    except Exception:  # noqa: BLE001
        pass
    return None


def _fredgraph(series_id):
    text = _fred_text(series_id)
    if text is None:
        return None
    df = pd.read_csv(io.StringIO(text))
    df.columns = ["date", "value"]
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.to_period("M").dt.to_timestamp()
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.dropna(subset=["date", "value"])


def _api_search(metro_name, limit=120):
    """Return series IDs matching a metro name (monthly), if an API key is set."""
    if not FRED_API_KEY:
        return []
    try:
        r = requests.get(
            f"{API}/series/search",
            params={
                "search_text": metro_name,
                "api_key": FRED_API_KEY,
                "file_type": "json",
                "limit": limit,
                "order_by": "popularity",
                "sort_order": "desc",
                "filter_variable": "frequency",
                "filter_value": "Monthly",
            },
            timeout=60,
        )
        r.raise_for_status()
        return [s["id"] for s in r.json().get("seriess", [])]
    except Exception:  # noqa: BLE001
        return []


def ingest():
    now = pd.Timestamp.utcnow()
    signal_rows, family_rows = [], []

    # national family
    print(f"    national: {len(NATIONAL)} series…", flush=True)
    for sid in NATIONAL:
        df = _fredgraph(sid)
        if df is None:
            continue
        df = df.assign(series_id=sid, metro_id="_national", source=f"FRED:{sid}")
        family_rows.append(df)

    # per-metro
    for m in METROS:
        print(f"    metro {m['metro_id']}…", flush=True)
        prefix = m["fred_nonfarm_id"][:-2]
        candidates = {prefix + suf for suf in METRO_SUFFIXES}
        candidates.add(m["fred_nonfarm_id"])
        candidates |= {f"RGMP{m['cbsa']}", f"NGMP{m['cbsa']}"}  # metro real/nominal GDP
        candidates |= set(_api_search(m["name"]))
        for sid in sorted(candidates):
            df = _fredgraph(sid)
            if df is None:
                continue
            df = df.assign(series_id=sid, metro_id=m["metro_id"], source=f"FRED:{sid}")
            family_rows.append(df)
            # canonical nonfarm -> signals
            if sid == m["fred_nonfarm_id"]:
                signal_rows.append(
                    df.assign(series="nonfarm_emp")[["metro_id", "date", "series", "value", "source"]]
                )

    fred_series = pd.concat(family_rows, ignore_index=True)
    fred_series["ingested_at"] = now
    fred_series = fred_series[["series_id", "metro_id", "date", "value", "source", "ingested_at"]]

    signals = pd.concat(signal_rows, ignore_index=True) if signal_rows else None
    if signals is not None:
        signals["ingested_at"] = now

    return {"signals": signals, "tables": {"fred_series": fred_series}}
