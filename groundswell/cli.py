"""Groundswell ingestion CLI.

  python -m groundswell.cli ingest --source all
  python -m groundswell.cli ingest --source warn --refresh
  python -m groundswell.cli load-es
  python -m groundswell.cli verify
"""
import argparse

import pandas as pd

from . import store
from .config import METROS
from .sources import apartment_list, context_docs, fhfa, fred, permits, postings, qcew, warn, zillow

SOURCES = [
    "fred", "zillow", "permits", "warn", "postings", "fhfa", "qcew",
    "apartment_list", "context_docs",
]


def _write_dim():
    cols = ["metro_id", "name", "zori_region", "fred_nonfarm_id", "warn_state", "cbsa"]
    store.write_table(pd.DataFrame([{k: m.get(k) for k in cols} for m in METROS]), "metros")


def _handle(result):
    """Persist a source result: signals -> upsert_signals, tables -> upsert/write."""
    sig = result.get("signals")
    if sig is not None and len(sig):
        store.upsert_signals(sig)
    for name, df in result.get("tables", {}).items():
        if df is None or not len(df):
            continue
        if name in store.TABLE_KEYS:
            store.upsert_table(df, name)
        else:
            store.write_table(df, name)


def cmd_ingest(args):
    _write_dim()
    todo = SOURCES if args.source == "all" else [args.source]
    for src in todo:
        print(f"[{src}] ingesting…", flush=True)
        if src == "fred":
            r = fred.ingest()
        elif src == "zillow":
            r = zillow.ingest()
            print(f"  shards: {len(r['written'])} written; skipped: {len(r['skipped'])}")
            for sh, n, meth, matched in r["written"]:
                print(f"    {sh}: {n:,} rows via {meth} ({matched:,} tagged to a metro)")
            if r["skipped"]:
                print(f"    skipped: {', '.join(r['skipped'])}")
        elif src == "permits":
            r = permits.ingest(census_months=args.census_months)
            print(f"  census xls files parsed: {r.get('census_files', 0)}")
        elif src == "warn":
            r = warn.ingest(since=args.since, refresh=args.refresh)
            print(f"  notices: {r.get('n_notices', 0):,}; matched to metro: {r.get('n_matched', 0):,}")
        elif src == "postings":
            r = postings.ingest(max_items=args.postings_max, refresh=args.refresh)
            print(f"  postings: {r.get('n_postings', 0):,}")
        elif src == "fhfa":
            r = fhfa.ingest()
            print(f"  FHFA HPI rows: {len(r.get('tables', {}).get('fhfa_hpi', [])):,}")
        elif src == "qcew":
            r = qcew.ingest()
            print(f"  QCEW rows: {len(r.get('tables', {}).get('qcew', [])):,}")
        elif src == "context_docs":
            r = context_docs.ingest()
            print(f"  context docs: {len(r.get('tables', {}).get('market_context_docs', [])):,}")
        elif src == "apartment_list":
            r = apartment_list.ingest()
            print(f"  Apartment List rows: {len(r.get('tables', {}).get('apartment_list_indices', [])):,}")
        _handle(r)
        sig = r.get("signals")
        if sig is not None:
            print(f"  signals rows: {len(sig):,}")
    print("ingest done.")


def cmd_load_es(args):
    from . import es

    res = es.load_all(batch=args.batch, only=args.only)
    for table, n in res.items():
        print(f"  groundswell-{table}: {n:,} docs")
    print("load-es done.")


def cmd_verify(args):
    con = store.connect()
    print("=== tables ===")
    for t in store.table_names():
        n = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        print(f"  {t}: {n:,} rows")
    print("\n=== signals by series ===")
    rows = con.execute(
        "SELECT series, count(*) n, count(distinct metro_id) metros, "
        "min(date) min_d, max(date) max_d FROM signals GROUP BY series ORDER BY series"
    ).fetchall()
    for r in rows:
        print(f"  {r[0]:<14} n={r[1]:>8,} metros={r[2]} range={r[3].date()}..{r[4].date()}")
    if "zillow_indices" in store.table_names():
        print("\n=== zillow_indices by dataset/level ===")
        for r in con.execute(
            "SELECT dataset, level, count(*) n FROM zillow_indices GROUP BY 1,2 ORDER BY 1,2"
        ).fetchall():
            print(f"  {r[0]:<22} {r[1]:<7} {r[2]:>10,}")


def main():
    p = argparse.ArgumentParser(prog="groundswell")
    sub = p.add_subparsers(dest="cmd", required=True)

    ing = sub.add_parser("ingest")
    ing.add_argument("--source", choices=["all", *SOURCES], default="all")
    ing.add_argument("--since", default="2015-01-01", help="WARN noticeDateFrom")
    ing.add_argument("--census-months", type=int, default=36, dest="census_months")
    ing.add_argument("--postings-max", type=int, default=75, dest="postings_max",
                     help="max Indeed items per query per metro")
    ing.add_argument("--refresh", action="store_true", help="re-pull WARN/postings (ignore cache)")
    ing.set_defaults(func=cmd_ingest)

    le = sub.add_parser("load-es")
    le.add_argument("--batch", type=int, default=5000)
    le.add_argument("--only", nargs="*", default=None)
    le.set_defaults(func=cmd_load_es)

    ver = sub.add_parser("verify")
    ver.set_defaults(func=cmd_verify)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
