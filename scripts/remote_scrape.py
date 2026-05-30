#!/usr/bin/env python3
"""Remote live scrapes for HomeStar.

Runs on the VM. Writes raw JSON under data/raw/remote_live/<run_id>/ and upserts
directly into the VM-local Elasticsearch instance. This deliberately avoids the
repo's load-es path because that loader deletes indices before reloading.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote_plus

import requests

ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = ROOT / "data" / "raw" / "remote_live"
ES_URL = os.getenv("ES_URL", "http://localhost:9201").rstrip("/")
INDEX_PREFIX = os.getenv("INDEX_PREFIX", "groundswell-")

METROS = {
    "sf": "San Francisco, CA",
    "austin": "Austin, TX",
    "phoenix": "Phoenix, AZ",
    "nyc": "New York, NY",
    "chicago": "Chicago, IL",
}

LINKEDIN_QUERIES = [
    "software engineer",
    "registered nurse",
    "sales associate",
    "accountant",
    "warehouse associate",
    "project manager",
    "property manager",
    "leasing consultant",
    "construction manager",
    "data analyst",
]

APARTMENTS_URLS = {
    "sf": ["https://www.apartments.com/san-francisco-ca/"],
    "austin": ["https://www.apartments.com/austin-tx/"],
    "phoenix": ["https://www.apartments.com/phoenix-az/"],
    "nyc": ["https://www.apartments.com/new-york-ny/"],
    "chicago": ["https://www.apartments.com/chicago-il/"],
}

APIFY_ACTORS = {
    "apartments": "sian.agency~apartments-com-property-scraper",
}


def load_env() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k, v.strip().strip('"').strip("'"))


def run_id() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value).strip()
    return value or None


def brightdata_raw(url: str, timeout: int = 120) -> str:
    token = os.getenv("BRIGHTDATA_TOKEN")
    if not token:
        raise RuntimeError("BRIGHTDATA_TOKEN is not set")
    payload = json.dumps({
        "zone": os.getenv("BRIGHTDATA_ZONE", "web_unlocker1"),
        "url": url,
        "format": "raw",
    })
    res = subprocess.run(
        [
            "curl", "-s", "--max-time", str(timeout),
            "https://api.brightdata.com/request",
            "-H", "Content-Type: application/json",
            "-H", f"Authorization: Bearer {token}",
            "-d", payload,
        ],
        capture_output=True,
        text=True,
        timeout=timeout + 20,
    )
    return res.stdout


def apify_items(actor: str, payload: dict, timeout: int = 360) -> list[dict]:
    token = os.getenv("APIFY_TOKEN")
    if not token:
        raise RuntimeError("APIFY_TOKEN is not set")
    url = f"https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"
    res = requests.post(
        url,
        params={"token": token, "timeout": timeout, "clean": "true"},
        json=payload,
        timeout=timeout + 30,
    )
    if res.status_code >= 400:
        raise RuntimeError(f"Apify {actor} failed: {res.status_code} {res.text[:300]}")
    data = res.json()
    if isinstance(data, dict):
        raise RuntimeError(f"Apify {actor} returned error object: {json.dumps(data)[:300]}")
    return data


def es_json(method: str, path: str, body: dict | None = None) -> dict:
    url = ES_URL + path
    kwargs = {"timeout": 120}
    if body is not None:
        kwargs["json"] = body
    res = requests.request(method, url, **kwargs)
    if res.status_code >= 400:
        raise RuntimeError(f"ES {method} {path} failed: {res.status_code} {res.text[:300]}")
    return res.json() if res.text else {}


def ensure_index(index: str) -> None:
    res = requests.head(f"{ES_URL}/{index}", timeout=30)
    if res.status_code == 404:
        es_json("PUT", f"/{index}", {"mappings": {"dynamic": True}})
    elif res.status_code >= 400:
        raise RuntimeError(f"ES HEAD {index} failed: {res.status_code}")


def bulk_upsert(index: str, docs: list[dict], id_fields: list[str], refresh: bool = False) -> int:
    if not docs:
        return 0
    ensure_index(index)
    lines = []
    for doc in docs:
        raw_id = "|".join(str(doc.get(f) or "") for f in id_fields)
        if not raw_id.strip("|"):
            raw_id = json.dumps(doc, sort_keys=True)[:500]
        doc_id = hashlib.sha1(raw_id.encode()).hexdigest()
        lines.append(json.dumps({"update": {"_index": index, "_id": doc_id}}))
        lines.append(json.dumps({"doc": doc, "doc_as_upsert": True}, default=str))
    payload = "\n".join(lines) + "\n"
    res = requests.post(
        f"{ES_URL}/_bulk",
        data=payload.encode(),
        headers={"Content-Type": "application/x-ndjson"},
        timeout=180,
    )
    if res.status_code >= 400:
        raise RuntimeError(f"ES bulk failed: {res.status_code} {res.text[:300]}")
    out = res.json()
    if out.get("errors"):
        errors = [i for i in out["items"] if i.get("update", {}).get("error")]
        raise RuntimeError(f"ES bulk had {len(errors)} errors, first={errors[:1]}")
    if refresh:
        requests.post(f"{ES_URL}/{index}/_refresh", timeout=60)
    return len(docs)


def refresh_index(index: str) -> None:
    requests.post(f"{ES_URL}/{index}/_refresh", timeout=60)


def parse_linkedin(html_text: str, metro_id: str, query: str, url: str, raw_file: str) -> list[dict]:
    docs = []
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    links = re.findall(r'href="(https://www\.linkedin\.com/jobs/view/[^"]+)"', html_text, re.I)
    titles = re.findall(r'class="[^"]*base-search-card__title[^"]*"[^>]*>(.*?)</', html_text, re.I | re.S)
    companies = re.findall(
        r'class="[^"]*base-search-card__subtitle[^"]*".*?<a[^>]*>(.*?)</a>',
        html_text,
        re.I | re.S,
    )
    locations = re.findall(r'class="[^"]*job-search-card__location[^"]*"[^>]*>(.*?)</', html_text, re.I | re.S)
    dates = re.findall(r'<time[^>]+datetime="([^"]+)"', html_text, re.I)
    seen = set()
    for i, raw_link in enumerate(links):
        job_url = html.unescape(raw_link).split("?")[0]
        if job_url in seen:
            continue
        seen.add(job_url)
        job_id_m = re.search(r'-(\d{8,})(?:/)?$', job_url or "")
        title = clean_text(titles[i]) if i < len(titles) else None
        company = clean_text(companies[i]) if i < len(companies) else None
        location = clean_text(locations[i]) if i < len(locations) else None
        if not (job_url and title):
            continue
        docs.append({
            "id": job_id_m.group(1) if job_id_m else hashlib.sha1(job_url.encode()).hexdigest()[:16],
            "title": title,
            "company": company,
            "location": location,
            "postedAt": dates[i] if i < len(dates) else None,
            "url": job_url,
            "metro_id": metro_id,
            "query": query,
            "source": "BrightData:LinkedIn",
            "source_url": url,
            "raw_file": raw_file,
            "scraped_at": now,
        })
    return docs


def linkedin_url(location: str, query: str, page: int) -> str:
    start = page * 25
    return (
        "https://www.linkedin.com/jobs/search/"
        f"?keywords={quote_plus(query)}&location={quote_plus(location)}"
        f"&f_TPR=r604800&start={start}"
    )


def parse_apartments(html_text: str, metro_id: str, url: str, raw_file: str) -> list[dict]:
    docs = []
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    for m in re.finditer(r'<article[^>]+class="[^"]*placard[^"]*".*?</article>', html_text, re.I | re.S):
        card = m.group(0)
        href_m = re.search(r'<a[^>]+href="([^"]+)"', card, re.I)
        name_m = re.search(r'class="[^"]*property-title[^"]*"[^>]*>(.*?)</', card, re.I | re.S)
        price_m = re.search(r'class="[^"]*property-pricing[^"]*"[^>]*>(.*?)</', card, re.I | re.S)
        addr_m = re.search(r'class="[^"]*property-address[^"]*"[^>]*>(.*?)</', card, re.I | re.S)
        prop_url = html.unescape(href_m.group(1)).split("?")[0] if href_m else None
        name = clean_text(name_m.group(1)) if name_m else None
        if not (prop_url and name):
            continue
        key = hashlib.sha1(prop_url.encode()).hexdigest()[:16]
        docs.append({
            "listingKey": key,
            "listingTitle": name,
            "pricing_rentRange": clean_text(price_m.group(1)) if price_m else None,
            "address_full": clean_text(addr_m.group(1)) if addr_m else None,
            "url": prop_url,
            "metro_id": metro_id,
            "source": "BrightData:Apartments.com",
            "source_url": url,
            "raw_file": raw_file,
            "scraped_at": now,
        })
    return docs


def normalize_apify_apartments(items: list[dict], metro_id: str, raw_file: str) -> list[dict]:
    docs = []
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    for item in items:
        key = item.get("listingKey") or item.get("id") or item.get("url")
        if not key:
            continue
        address = item.get("address") or {}
        pricing = item.get("pricing") or {}
        specs = item.get("specs") or {}
        location = item.get("location") or {}
        market = item.get("market") or {}
        media = item.get("media") or {}
        manager = item.get("propertyManager") or {}
        contact = item.get("contact") or {}
        doc = {
            "listingKey": str(key),
            "listingTitle": item.get("listingTitle") or item.get("title") or item.get("name"),
            "metro_id": metro_id,
            "source": "Apify:Apartments.com",
            "raw_file": raw_file,
            "scraped_at": item.get("scrapedAt") or now,
            "sourceLabel": item.get("sourceLabel"),
            "address_street": address.get("street"),
            "address_city": address.get("city"),
            "address_state": address.get("state"),
            "address_postalCode": address.get("postalCode"),
            "address_countryCode": address.get("countryCode"),
            "address_full": address.get("full"),
            "pricing_rentRange": pricing.get("rentRange"),
            "pricing_rentMin": pricing.get("rentMin"),
            "pricing_rentMax": pricing.get("rentMax"),
            "pricing_rentMidpoint": pricing.get("rentMidpoint"),
            "specs_bedRange": specs.get("bedRange"),
            "specs_bedsMin": specs.get("bedsMin"),
            "specs_bedsMax": specs.get("bedsMax"),
            "specs_isMultifamily": specs.get("isMultifamily"),
            "specs_isFurnished": specs.get("isFurnished"),
            "location_latitude": location.get("latitude"),
            "location_longitude": location.get("longitude"),
            "market_availabilityText": market.get("availabilityText"),
            "market_hasAvailabilities": market.get("hasAvailabilities"),
            "market_rating": market.get("rating"),
            "media_primaryImage": media.get("primaryImage"),
            "media_multimediaUrl": media.get("multimediaUrl"),
            "propertyManager_name": manager.get("name"),
            "propertyManager_companyId": manager.get("companyId"),
            "contact_phone": contact.get("phone"),
            "contact_hasLeadEmail": contact.get("hasLeadEmail"),
        }
        docs.append({k: v for k, v in doc.items() if v is not None})
    return docs


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str))


def append_manifest(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "source", "metro_id", "query", "url", "raw_path", "raw_bytes",
            "parsed_rows", "indexed_rows", "status", "error",
        ])
        if not exists:
            w.writeheader()
        w.writerow(row)


def scrape_linkedin(args, out_dir: Path, manifest: Path) -> None:
    index = INDEX_PREFIX + "linkedin_job_postings"
    queries = args.queries or LINKEDIN_QUERIES
    for metro_id in args.metros:
        location = METROS[metro_id]
        for query in queries:
            for page in range(args.page_offset, args.page_offset + args.pages):
                url = linkedin_url(location, query, page)
                raw_path = out_dir / f"linkedin__{metro_id}__{query.replace(' ', '_')}__p{page}.html"
                parsed_path = out_dir / f"linkedin__{metro_id}__{query.replace(' ', '_')}__p{page}.json"
                row = {
                    "source": "linkedin", "metro_id": metro_id, "query": query,
                    "url": url, "raw_path": str(raw_path.relative_to(ROOT)),
                    "raw_bytes": 0, "parsed_rows": 0, "indexed_rows": 0,
                    "status": "error", "error": "",
                }
                try:
                    text = brightdata_raw(url, timeout=args.timeout)
                    raw_path.write_text(text)
                    docs = parse_linkedin(text, metro_id, query, url, str(raw_path.relative_to(ROOT)))
                    write_json(parsed_path, docs)
                    indexed = bulk_upsert(index, docs, ["id", "metro_id"], refresh=args.refresh_each_bulk)
                    row.update(raw_bytes=len(text), parsed_rows=len(docs), indexed_rows=indexed, status="ok")
                    print(f"linkedin {metro_id} {query} p{page}: {len(docs)} rows")
                except Exception as e:  # noqa: BLE001
                    row["error"] = f"{type(e).__name__}: {e}"[:500]
                    print(f"linkedin {metro_id} {query} p{page}: ERROR {row['error']}", file=sys.stderr)
                append_manifest(manifest, row)
                time.sleep(args.sleep)
    if not args.refresh_each_bulk:
        refresh_index(index)


def scrape_apartments(args, out_dir: Path, manifest: Path) -> None:
    index = INDEX_PREFIX + "apartments_com_properties"
    for metro_id in args.metros:
        for base_url in APARTMENTS_URLS[metro_id]:
            for page_offset in range(args.page_offset, args.page_offset + args.pages):
                page = page_offset + 1
                url = base_url if page == 1 else base_url.rstrip("/") + f"/{page}/"
                raw_path = out_dir / f"apartments__{metro_id}__p{page}.html"
                parsed_path = out_dir / f"apartments__{metro_id}__p{page}.json"
                row = {
                    "source": "apartments", "metro_id": metro_id, "query": "",
                    "url": url, "raw_path": str(raw_path.relative_to(ROOT)),
                    "raw_bytes": 0, "parsed_rows": 0, "indexed_rows": 0,
                    "status": "error", "error": "",
                }
                try:
                    text = brightdata_raw(url, timeout=args.timeout)
                    raw_path.write_text(text)
                    docs = parse_apartments(text, metro_id, url, str(raw_path.relative_to(ROOT)))
                    if not docs and args.apify_fallback:
                        apify_payload = {
                            "location": METROS[metro_id],
                            "maxItems": args.apartments_max_items,
                            "maxListings": args.apartments_max_items,
                            "search": METROS[metro_id],
                            "startUrls": [{"url": url}],
                        }
                        apify_raw_path = out_dir / f"apartments_apify__{metro_id}__p{page}.json"
                        items = apify_items(APIFY_ACTORS["apartments"], apify_payload, timeout=420)
                        write_json(apify_raw_path, items)
                        docs = normalize_apify_apartments(
                            items, metro_id, str(apify_raw_path.relative_to(ROOT))
                        )
                    write_json(parsed_path, docs)
                    indexed = bulk_upsert(index, docs, ["listingKey"], refresh=args.refresh_each_bulk)
                    row.update(raw_bytes=len(text), parsed_rows=len(docs), indexed_rows=indexed, status="ok")
                    print(f"apartments {metro_id} p{page}: {len(docs)} rows")
                except Exception as e:  # noqa: BLE001
                    row["error"] = f"{type(e).__name__}: {e}"[:500]
                    print(f"apartments {metro_id} p{page}: ERROR {row['error']}", file=sys.stderr)
                append_manifest(manifest, row)
                time.sleep(args.sleep)
    if not args.refresh_each_bulk:
        refresh_index(index)


def count(index: str) -> int:
    try:
        return es_json("GET", f"/{index}/_count").get("count", 0)
    except Exception:
        return -1


def main() -> None:
    load_env()
    p = argparse.ArgumentParser()
    p.add_argument("--source", choices=["linkedin", "apartments", "all"], default="linkedin")
    p.add_argument("--metros", nargs="+", choices=sorted(METROS), default=["sf", "austin", "phoenix", "nyc", "chicago"])
    p.add_argument("--queries", nargs="*", default=None)
    p.add_argument("--pages", type=int, default=1)
    p.add_argument("--page-offset", type=int, default=0)
    p.add_argument("--sleep", type=float, default=1.5)
    p.add_argument("--timeout", type=int, default=120)
    p.add_argument("--apify-fallback", action="store_true")
    p.add_argument("--apartments-max-items", type=int, default=100)
    p.add_argument("--refresh-each-bulk", action="store_true")
    args = p.parse_args()

    rid = run_id()
    out_dir = RAW_ROOT / rid
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = out_dir / "manifest.csv"
    print(f"run_id={rid} out={out_dir.relative_to(ROOT)} es={ES_URL}")
    print("before linkedin", count(INDEX_PREFIX + "linkedin_job_postings"))
    print("before apartments", count(INDEX_PREFIX + "apartments_com_properties"))

    if args.source in ("linkedin", "all"):
        scrape_linkedin(args, out_dir, manifest)
    if args.source in ("apartments", "all"):
        scrape_apartments(args, out_dir, manifest)

    print("after linkedin", count(INDEX_PREFIX + "linkedin_job_postings"))
    print("after apartments", count(INDEX_PREFIX + "apartments_com_properties"))
    print(f"manifest={manifest.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
