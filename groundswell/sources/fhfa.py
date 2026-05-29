"""FHFA House Price Index — ownership affordability / buy-vs-rent pressure.

Pulls the public FHFA HPI master CSV and keeps quarterly MSA rows for the demo
metros. This complements Zillow with an independent federal repeat-sales index.
"""
import pandas as pd

from ..config import METROS

URL = "https://www.fhfa.gov/hpi/download/monthly/hpi_master.csv"

# FHFA reports some demo markets as metropolitan divisions rather than full CBSAs.
FHFA_PLACE_IDS = {
    "sf": ["41884"],
    "austin": ["12420"],
    "phoenix": ["38060"],
    "nyc": ["35614"],
    "chicago": ["16984"],
}


def ingest():
    now = pd.Timestamp.utcnow()
    keep_ids = {pid for ids in FHFA_PLACE_IDS.values() for pid in ids}
    metro_for = {pid: mid for mid, ids in FHFA_PLACE_IDS.items() for pid in ids}
    cbsa_for = {m["metro_id"]: m.get("cbsa") for m in METROS}

    df = pd.read_csv(
        URL,
        dtype={"place_id": str, "note": str},
        low_memory=False,
        usecols=[
            "hpi_type", "hpi_flavor", "frequency", "level", "place_name", "place_id",
            "yr", "period", "index_nsa", "index_sa", "rstderr", "note",
        ],
    )
    df = df[(df["level"] == "MSA") & (df["place_id"].isin(keep_ids))].copy()
    df["metro_id"] = df["place_id"].map(metro_for)
    df["cbsa"] = df["metro_id"].map(cbsa_for)
    df["date"] = [
        pd.Period(f"{int(y)}Q{int(q)}", freq="Q").to_timestamp()
        for y, q in zip(df["yr"], df["period"])
    ]
    df["index_nsa"] = pd.to_numeric(df["index_nsa"], errors="coerce")
    df["index_sa"] = pd.to_numeric(df["index_sa"], errors="coerce")
    df["rstderr"] = pd.to_numeric(df["rstderr"], errors="coerce")
    df["source"] = "FHFA:HPI"
    df["source_url"] = URL
    df["ingested_at"] = now
    df = df[
        [
            "metro_id", "cbsa", "date", "hpi_type", "hpi_flavor", "frequency", "level",
            "place_name", "place_id", "yr", "period", "index_nsa", "index_sa",
            "rstderr", "note", "source", "source_url", "ingested_at",
        ]
    ].sort_values(["metro_id", "hpi_type", "hpi_flavor", "date"])

    sig_base = df[
        (df["hpi_type"] == "traditional")
        & (df["hpi_flavor"] == "all-transactions")
        & df["index_nsa"].notna()
    ].copy()
    sig = sig_base.rename(columns={"index_nsa": "value"})
    sig["series"] = "fhfa_hpi"
    sig = sig[["metro_id", "date", "series", "value", "source", "ingested_at"]]

    return {"signals": sig, "tables": {"fhfa_hpi": df}}
