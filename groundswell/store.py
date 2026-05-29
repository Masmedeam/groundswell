"""Local store: Parquet files + DuckDB views over data/normalized/."""
import fcntl
from contextlib import contextmanager

import duckdb
import pandas as pd

from .config import DATA_NORM

SIGNALS_PATH = DATA_NORM / "signals.parquet"
_LOCK_PATH = DATA_NORM / ".write.lock"


@contextmanager
def _filelock():
    """Cross-process exclusive lock so concurrent ingests can't clobber each other's
    read-modify-write on shared parquet (signals.parquet, family tables)."""
    f = open(_LOCK_PATH, "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(f, fcntl.LOCK_UN)
        f.close()

# canonical column order for the unified long signals table
SIGNAL_COLS = ["metro_id", "date", "series", "value", "source", "ingested_at"]


def write_table(df: pd.DataFrame, name: str):
    """Overwrite a normalized table."""
    path = DATA_NORM / f"{name}.parquet"
    df.to_parquet(path, index=False)
    return path


# natural keys for tables multiple sources contribute to (used by upsert_table)
TABLE_KEYS = {
    "fred_series": ["series_id", "metro_id", "date"],
    "permits_raw": ["cbsa", "date"],
    "warn_notices": ["notice_id"],
    "job_postings": ["metro_id", "id"],
    "fhfa_hpi": ["place_id", "date", "hpi_type", "hpi_flavor"],
    "qcew": ["county_fips", "date", "frequency", "own_code", "industry_code"],
    "market_context_docs": ["doc_id"],
    "apartment_list_indices": ["dataset", "location_type", "location_fips_code", "bed_size", "date"],
    "apartments_com_properties": ["listingKey"],
    "redfin_listings": ["listingId"],
    "linkedin_job_postings": ["id", "metro_id"],
}


def upsert_table(df: pd.DataFrame, name: str):
    """Append rows and de-duplicate on the table's natural key (idempotent reruns)."""
    path = DATA_NORM / f"{name}.parquet"
    if path.exists():
        combined = pd.concat([pd.read_parquet(path), df], ignore_index=True)
    else:
        combined = df
    keys = TABLE_KEYS.get(name)
    if keys and all(k in combined.columns for k in keys):
        combined = combined.drop_duplicates(subset=keys, keep="last")
    combined.to_parquet(path, index=False)
    return path


def write_shard(df: pd.DataFrame, base: str, shard: str):
    """Write one shard of a large logical table. Files are named `base__shard.parquet`
    and unioned into a single `base` view by connect()."""
    path = DATA_NORM / f"{base}__{shard}.parquet"
    df.to_parquet(path, index=False)
    return path


def table_names():
    """Logical table names = distinct base names across plain + sharded parquet."""
    bases = set()
    for p in DATA_NORM.glob("*.parquet"):
        bases.add(p.stem.split("__")[0])
    return sorted(bases)


def upsert_signals(df_new: pd.DataFrame):
    """Replace the rows for whatever `series` appear in df_new, keep the rest.

    Makes re-running a single source idempotent without clobbering others.
    """
    df_new = df_new[SIGNAL_COLS].copy()
    series_written = set(df_new["series"].unique())
    with _filelock():
        if SIGNALS_PATH.exists():
            existing = pd.read_parquet(SIGNALS_PATH)
            existing = existing[~existing["series"].isin(series_written)]
            combined = pd.concat([existing, df_new], ignore_index=True)
        else:
            combined = df_new
        combined = combined.sort_values(["series", "metro_id", "date"]).reset_index(drop=True)
        combined.to_parquet(SIGNALS_PATH, index=False)
    return SIGNALS_PATH


def connect() -> duckdb.DuckDBPyConnection:
    """Open a DuckDB connection with one view per logical table.

    Plain files (`name.parquet`) and shard sets (`name__*.parquet`) both become a
    single view `name`.
    """
    con = duckdb.connect()
    groups = {}
    for p in sorted(DATA_NORM.glob("*.parquet")):
        groups.setdefault(p.stem.split("__")[0], []).append(p.as_posix())
    for base, files in groups.items():
        arr = "[" + ",".join(f"'{f}'" for f in files) + "]"
        con.execute(
            f"CREATE OR REPLACE VIEW {base} AS "
            f"SELECT * FROM read_parquet({arr}, union_by_name=true)"
        )
    return con
