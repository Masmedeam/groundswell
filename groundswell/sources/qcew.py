"""BLS QCEW — county industry employment and wages.

The Quarterly Census of Employment and Wages covers more than 95% of US jobs.
We ingest all demo-metro counties, all private-sector supersectors/sectors, plus
all-ownership county totals. This gives the agent industry-level labor context.
"""
import io

import pandas as pd

from ..config import METROS
from ..fetch import curl_get

API = "https://data.bls.gov/cew/data/api/{year}/{period}/area/{area}.csv"

COUNTY_FIPS = {
    "sf": {
        "San Francisco": "06075", "San Mateo": "06081", "Marin": "06041",
        "Alameda": "06001", "Contra Costa": "06013",
    },
    "austin": {
        "Travis": "48453", "Williamson": "48491", "Hays": "48209",
        "Bastrop": "48021", "Caldwell": "48055",
    },
    "phoenix": {"Maricopa": "04013", "Pinal": "04021"},
    "nyc": {
        "New York": "36061", "Kings": "36047", "Queens": "36081", "Bronx": "36005",
        "Richmond": "36085", "Nassau": "36059", "Suffolk": "36103",
        "Westchester": "36119", "Rockland": "36087", "Putnam": "36079",
        "Orange": "36071", "Dutchess": "36027",
    },
    "chicago": {
        "Cook": "17031", "DuPage": "17043", "Lake": "17097", "Will": "17197",
        "Kane": "17089", "McHenry": "17111", "Kendall": "17093",
        "Grundy": "17063", "DeKalb": "17037",
    },
}


def _read(area, year, period):
    url = API.format(area=area, year=year, period=period)
    code, body = curl_get(url, max_time=20)
    if code != "200" or not body.startswith('"area_fips"'):
        return None
    return pd.read_csv(io.StringIO(body), dtype={"area_fips": str, "own_code": str, "industry_code": str})


def _filter(df):
    df = df[df["size_code"].astype(str).eq("0")].copy()
    # All ownership total + private supersectors/sectors.
    total = df[(df["own_code"] == "0") & (df["industry_code"] == "10")]
    private = df[(df["own_code"] == "5") & (df["agglvl_code"].astype(str).isin(["71", "72", "73", "74"]))]
    return pd.concat([total, private], ignore_index=True)


def ingest():
    now = pd.Timestamp.utcnow()
    metro_rows = []
    metro_meta = {m["metro_id"]: m for m in METROS}
    jobs = []
    # Annual history first: much faster than all quarterly files and broad enough
    # for industry-composition context in the initial ES corpus.
    last_complete_year = min(2024, pd.Timestamp.utcnow().year - 2)
    for year in range(2020, last_complete_year + 1):
        jobs.append((year, "a"))

    for metro_id, counties in COUNTY_FIPS.items():
        for county_name, fips in counties.items():
            for year, period in jobs:
                raw = _read(fips, year, period)
                if raw is None or raw.empty:
                    continue
                df = _filter(raw)
                if df.empty:
                    continue
                df["metro_id"] = metro_id
                df["metro_name"] = metro_meta[metro_id]["name"]
                df["county_name"] = county_name
                df["county_fips"] = fips
                df["frequency"] = "annual" if period == "a" else "quarterly"
                if period == "a":
                    df["date"] = pd.Timestamp(year=int(year), month=1, day=1)
                else:
                    df["date"] = pd.Period(f"{year}Q{period}", freq="Q").to_timestamp()
                df["source"] = "BLS:QCEW"
                df["source_url"] = API.format(area=fips, year=year, period=period)
                df["ingested_at"] = now
                metro_rows.append(df)

    qcew = pd.concat(metro_rows, ignore_index=True) if metro_rows else pd.DataFrame()
    if qcew.empty:
        return {"signals": None, "tables": {}}

    cols = [
        "metro_id", "metro_name", "county_name", "county_fips", "date", "frequency",
        "area_fips", "own_code", "industry_code", "agglvl_code", "size_code",
        "year", "qtr", "source", "source_url", "ingested_at",
    ]
    metric_cols = [c for c in qcew.columns if c not in cols]
    qcew = qcew[cols + metric_cols].sort_values(
        ["metro_id", "county_fips", "date", "own_code", "industry_code"]
    )

    annual_total = qcew[
        (qcew["frequency"] == "annual")
        & (qcew["own_code"] == "0")
        & (qcew["industry_code"] == "10")
    ].copy()
    sig = None
    if not annual_total.empty:
        emp = annual_total.groupby(["metro_id", "date"], as_index=False).agg(
            value=("annual_avg_emplvl", "sum")
        )
        emp["series"] = "qcew_emp"
        emp["source"] = "BLS:QCEW"
        emp["ingested_at"] = now
        sig = emp[["metro_id", "date", "series", "value", "source", "ingested_at"]]

    return {"signals": sig, "tables": {"qcew": qcew}}
