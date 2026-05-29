"""Building permits — the supply blade.

  - signals: canonical `permits` per metro (FRED BPPRIV, full history, reliable)
  - tables.fred_series: metro permits family (BPPRIV + SA)
  - tables.permits_raw: national CBSA monthly permits from Census BPS xls (best effort)
"""
import io

import pandas as pd

from ..config import METROS
from ..fetch import download_bytes
from .fred import _fredgraph

PERMIT_SUFFIXES = ["BPPRIV", "BPPRIVSA"]
CBSA_XLS = "https://www.census.gov/construction/bps/xls/cbsamonthly_{ym}.xls"


def _metro_permits(now):
    sig_rows, fam_rows = [], []
    for m in METROS:
        prefix = m["fred_nonfarm_id"][:-2]
        for suf in PERMIT_SUFFIXES:
            sid = prefix + suf
            df = _fredgraph(sid)
            if df is None:
                continue
            fam_rows.append(df.assign(series_id=sid, metro_id=m["metro_id"], source=f"FRED:{sid}"))
            if suf == "BPPRIV":
                sig_rows.append(
                    df.assign(series="permits", metro_id=m["metro_id"], source=f"FRED:{sid}")[
                        ["metro_id", "date", "series", "value", "source"]
                    ]
                )
    signals = pd.concat(sig_rows, ignore_index=True) if sig_rows else None
    if signals is not None:
        signals["ingested_at"] = now
    fam = pd.concat(fam_rows, ignore_index=True) if fam_rows else None
    if fam is not None:
        fam["ingested_at"] = now
        fam = fam[["series_id", "metro_id", "date", "value", "source", "ingested_at"]]
    return signals, fam


# Exact cbsamonthly.xls layout (verified): header at row 7, data from row 8, 17 cols.
BPS_COLS = [
    "csa", "cbsa", "name", "metro_micro",
    "cm_total", "cm_1u", "cm_2u", "cm_34u", "cm_5plus", "cm_struct5plus",
    "_blank",
    "ytd_total", "ytd_1u", "ytd_2u", "ytd_34u", "ytd_5plus", "ytd_struct5plus",
]


def _census_national(now, months=36):
    """Pull recent monthly CBSA permit xls files from Census BPS (Metropolitan rows)."""
    rows, got = [], 0
    end = pd.Timestamp.now().to_period("M")
    for i in range(1, months + 1):
        ym = (end - i).strftime("%Y%m")
        url = CBSA_XLS.format(ym=ym)
        try:
            content = download_bytes(url, timeout=90)
            if content is None:
                continue
            df = pd.read_excel(
                io.BytesIO(content), engine="xlrd", header=None, skiprows=8, names=BPS_COLS
            )
            df = df[pd.to_numeric(df["cbsa"], errors="coerce").notna()]
            # keep all CBSAs (metro_micro: 2=Metropolitan, 5=Micropolitan); store the code
            out = pd.DataFrame({
                "cbsa": pd.to_numeric(df["cbsa"]).astype(int).astype(str),
                "name": df["name"].astype(str).str.strip(),
                "metro_micro": pd.to_numeric(df["metro_micro"], errors="coerce"),
                "total_units": pd.to_numeric(df["cm_total"], errors="coerce"),
                "units_1u": pd.to_numeric(df["cm_1u"], errors="coerce"),
                "units_5plus": pd.to_numeric(df["cm_5plus"], errors="coerce"),
            }).dropna(subset=["total_units"])
            out["date"] = pd.Period(f"{ym[:4]}-{ym[4:]}", freq="M").to_timestamp()
            out["source"] = "CensusBPS:cbsamonthly"
            rows.append(out)
            got += 1
        except Exception:  # noqa: BLE001
            continue
    if not rows:
        return None, 0
    out = pd.concat(rows, ignore_index=True)
    out["ingested_at"] = now
    return out, got


def ingest(census_months=36):
    now = pd.Timestamp.utcnow()
    signals, fam = _metro_permits(now)
    tables = {}
    if fam is not None:
        tables["fred_series"] = fam  # appended to FRED family table
    nat, nfiles = _census_national(now, months=census_months)
    if nat is not None:
        tables["permits_raw"] = nat
    return {"signals": signals, "tables": tables, "census_files": nfiles}
