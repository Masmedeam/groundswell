"""Load the normalized Parquet/DuckDB tables into local Elasticsearch."""
import datetime as dt
import math
import os

import pandas as pd
from elasticsearch import Elasticsearch, helpers

from . import store

ES_URL = os.getenv("ES_URL", "http://localhost:9201")
PREFIX = "groundswell-"
DATE_FIELDS = {"date", "ingested_at", "notice_date", "effective_date", "scraped_at"}
NUM_FIELDS = {"value", "total_units", "affected_workers", "warn_notices", "warn_affected"}


def client():
    return Elasticsearch(ES_URL, request_timeout=120)


def _mapping():
    props = {f: {"type": "date"} for f in DATE_FIELDS}
    props.update({f: {"type": "double"} for f in NUM_FIELDS})
    return {"mappings": {"dynamic": True, "properties": props}}


def ensure_index(es, index):
    if es.indices.exists(index=index):
        es.indices.delete(index=index)
    es.indices.create(index=index, **_mapping())


def _clean(rec):
    out = {}
    for k, v in rec.items():
        if v is None:
            continue
        if isinstance(v, float) and math.isnan(v):
            continue
        if isinstance(v, str) and not v.strip():
            continue  # drop empty strings (e.g. NY effective_date="") — breaks date mapping
        if isinstance(v, (pd.Timestamp, dt.datetime, dt.date)):
            if pd.isna(v):
                continue
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


def load_table(es, con, table, batch=5000):
    index = PREFIX + table
    ensure_index(es, index)
    cur = con.execute(f"SELECT * FROM {table}")
    cols = [d[0] for d in cur.description]
    total, errors = 0, 0
    while True:
        rows = cur.fetchmany(batch)
        if not rows:
            break
        actions = [{"_index": index, "_source": _clean(dict(zip(cols, r)))} for r in rows]
        ok, errs = helpers.bulk(
            es, actions, request_timeout=180, raise_on_error=False, stats_only=False,
            max_retries=4, initial_backoff=2, max_backoff=60,
        )
        total += ok
        errors += len(errs)
        if errs:
            print(f"    [{index}] {len(errs)} bulk errors, e.g. {errs[0]}"[:300])
        if total % 500_000 < batch:
            print(f"    [{index}] {total:,} docs indexed…", flush=True)
    es.indices.refresh(index=index)
    return total


def load_all(batch=5000, only=None):
    es = client()
    if not es.ping():
        raise RuntimeError("Elasticsearch not reachable at " + ES_URL + " (is the Docker stack up?)")
    con = store.connect()
    results = {}
    for table in store.table_names():
        if only and table not in only:
            continue
        results[table] = load_table(es, con, table, batch)
    return results
