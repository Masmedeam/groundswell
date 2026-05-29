"""Zillow Research family ingester — catalog-driven, all levels.

Downloads every (dataset x level) in config/zillow_datasets.yaml (skipping dead
URLs), normalizes wide->long, tags rows to one of our metros where possible, and
writes one parquet shard per (dataset, level) into the `zillow_indices` table.

Canonical metro-level ZORI also feeds the `signals` table as `rent_index`.
"""
import io
import re

import pandas as pd
import yaml

from ..config import DATA_RAW, ROOT
from ..crosswalk import metro_for_region_name, to_metro
from ..fetch import fetch_text, url_exists
from .. import store

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SHARD_COLS = [
    "dataset", "level", "region_id", "region_name", "state",
    "metro_name", "county_name", "city", "metro_id", "date", "value",
    "source", "ingested_at",
]
RAW_DIR = DATA_RAW / "zillow"


def _catalog():
    with open(ROOT / "config" / "zillow_datasets.yaml") as f:
        return yaml.safe_load(f)


def _tag_metro(level, row):
    if level == "Metro":
        return metro_for_region_name(row.get("region_name"))
    if level == "County":
        return to_metro(row.get("state"), row.get("region_name"))
    # City / Zip carry a CountyName
    return to_metro(row.get("state"), row.get("county_name"))


def _normalize(text, dataset, level, now):
    df = pd.read_csv(io.StringIO(text))
    date_cols = [c for c in df.columns if DATE_RE.match(str(c))]
    id_cols = [c for c in df.columns if c not in date_cols]
    keep = {c: c for c in id_cols}
    long = df.melt(
        id_vars=id_cols, value_vars=date_cols, var_name="date", value_name="value"
    )
    long["value"] = pd.to_numeric(long["value"], errors="coerce")
    long = long.dropna(subset=["value"])
    if long.empty:
        return None
    long["date"] = pd.to_datetime(long["date"], errors="coerce").dt.to_period("M").dt.to_timestamp()
    out = pd.DataFrame({
        "dataset": dataset,
        "level": level,
        "region_id": long.get("RegionID"),
        "region_name": long.get("RegionName").astype(str),
        "state": long["State"] if "State" in long else None,
        "metro_name": long["Metro"] if "Metro" in long else None,
        "county_name": long["CountyName"] if "CountyName" in long else None,
        "city": long["City"] if "City" in long else None,
        "date": long["date"],
        "value": long["value"],
        "source": f"Zillow:{dataset}:{level}",
        "ingested_at": now,
    })
    out["metro_id"] = out.apply(lambda r: _tag_metro(level, r), axis=1)
    return out[SHARD_COLS]


def ingest():
    now = pd.Timestamp.utcnow()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cat = _catalog()
    base = cat["base"]
    written, signal_rows, skipped = [], [], []

    for ds in cat["datasets"]:
        for level in ds["levels"]:
            fname = f"{level}_{ds['file']}"
            url = f"{base}/{ds['slug']}/{fname}"
            if not url_exists(url):
                skipped.append(f"{ds['dataset']}/{level}")
                continue
            try:
                text, method = fetch_text(url, expect_prefix="RegionID")
            except Exception as e:  # noqa: BLE001
                skipped.append(f"{ds['dataset']}/{level} (dl: {e})")
                continue
            (RAW_DIR / fname).write_text(text)
            out = _normalize(text, ds["dataset"], level, now)
            if out is None or out.empty:
                skipped.append(f"{ds['dataset']}/{level} (empty)")
                continue
            shard = f"{ds['dataset']}__{level}"
            store.write_shard(out, "zillow_indices", shard)
            written.append((shard, len(out), method, int(out["metro_id"].notna().sum())))
            # canonical rent_index from smoothed all-homes metro ZORI
            if ds["dataset"] == "zori_allhomes_sm" and level == "Metro":
                sig = out.dropna(subset=["metro_id"]).copy()
                sig["series"] = "rent_index"
                signal_rows.append(sig[["metro_id", "date", "series", "value", "source"]])

    signals = pd.concat(signal_rows, ignore_index=True) if signal_rows else None
    if signals is not None:
        signals["ingested_at"] = now
    return {"signals": signals, "tables": {}, "written": written, "skipped": skipped}
