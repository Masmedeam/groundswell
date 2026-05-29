"""Apartment List public rent, vacancy, and time-on-market data.

Apartment List publishes monthly CSVs for rent estimates, rent growth, vacancy,
and time on market at national/state/metro/county/city levels.
"""
import json
import re
from urllib.parse import urljoin

import pandas as pd
import requests

from ..config import DATA_RAW, METROS
from ..fetch import UA

PAGE = "https://www.apartmentlist.com/research/category/data-rent-estimates"
RAW_DIR = DATA_RAW / "apartment_list"

DATASET_BY_LABEL = {
    "Historic Rent Estimates": "rent_estimate",
    "Historic Rent Growth, Month-over-Month": "rent_growth_mom",
    "Historic Rent Growth, Year-over-Year": "rent_growth_yoy",
    "Apartment List Vacancy Index": "vacancy_index",
    "Time On Market": "time_on_market",
}


def _assets():
    html = requests.get(PAGE, headers={"User-Agent": UA}, timeout=30).text
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
    if not m:
        raise RuntimeError("Apartment List page did not expose __NEXT_DATA__ assets")
    data = json.loads(m.group(1))
    assets = data["props"]["pageProps"]["component"]["searchResults"][0]["downloadableAssets"]
    out = []
    for a in assets:
        label = a["label"]
        for prefix, dataset in DATASET_BY_LABEL.items():
            if label.startswith(prefix):
                out.append((dataset, label, urljoin("https:", a["url"])))
    return out


def _metro_id(row):
    code = str(row.get("location_fips_code") or "").split(".")[0]
    name = row.get("location_name")
    metro = row.get("metro")
    for m in METROS:
        if code == str(m.get("cbsa")) or name == m.get("zori_region") or metro == m.get("zori_region"):
            return m["metro_id"]
    return None


def _read_asset(dataset, label, url):
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / url.rsplit("/", 1)[-1]
    if not path.exists():
        r = requests.get(url, headers={"User-Agent": UA}, timeout=120)
        r.raise_for_status()
        path.write_bytes(r.content)
    wide = pd.read_csv(path)
    wide["dataset"] = dataset
    wide["source_label"] = label
    wide["source_url"] = url
    id_cols = [
        c for c in [
            "dataset", "source_label", "source_url", "location_name", "location_type",
            "location_fips_code", "population", "state", "county", "metro", "bed_size",
        ] if c in wide.columns
    ]
    date_cols = [c for c in wide.columns if re.fullmatch(r"\d{4}_\d{2}", str(c))]
    long = wide.melt(id_vars=id_cols, value_vars=date_cols, var_name="period", value_name="value")
    long["date"] = pd.to_datetime(long["period"].str.replace("_", "-") + "-01", errors="coerce")
    long["value"] = pd.to_numeric(long["value"], errors="coerce")
    long["metro_id"] = long.apply(_metro_id, axis=1)
    long["ingested_at"] = pd.Timestamp.utcnow()
    return long.dropna(subset=["date", "value"])


def ingest():
    frames = []
    for dataset, label, url in _assets():
        df = _read_asset(dataset, label, url)
        print(f"    {dataset}: {len(df):,} rows")
        frames.append(df)
    idx = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if idx.empty:
        return {"signals": None, "tables": {}}

    sig_rows = []
    signal_map = {
        "rent_estimate": "apartment_list_rent",
        "vacancy_index": "apartment_list_vacancy",
        "time_on_market": "apartment_list_time_on_market",
    }
    for dataset, series in signal_map.items():
        d = idx[
            (idx["dataset"] == dataset)
            & (idx["location_type"] == "Metro")
            & idx["metro_id"].notna()
        ].copy()
        if "bed_size" in d.columns:
            d = d[d["bed_size"].fillna("overall").eq("overall")]
        if d.empty:
            continue
        d["series"] = series
        d["source"] = "Apartment List"
        sig_rows.append(d.rename(columns={"value": "value"})[
            ["metro_id", "date", "series", "value", "source", "ingested_at"]
        ])
    sig = pd.concat(sig_rows, ignore_index=True) if sig_rows else None
    return {"signals": sig, "tables": {"apartment_list_indices": idx}}
