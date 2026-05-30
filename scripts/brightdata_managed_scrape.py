#!/usr/bin/env python3
"""Use Bright Data hosted Scraper APIs and index results into Elasticsearch.

This path is for Bright Data's managed scraper infrastructure: the API returns
structured JSON, so this machine only triggers, downloads, normalizes, and
indexes records.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = ROOT / "data" / "raw" / "brightdata_managed"
ES_URL = os.getenv("ES_URL", "http://localhost:9201").rstrip("/")
INDEX_PREFIX = os.getenv("INDEX_PREFIX", "groundswell-")
BD_API = "https://api.brightdata.com/datasets/v3"
LINKEDIN_JOBS_DATASET_ID = "gd_lpfll7v5hcqtkxl6l"
APARTMENTS_COLLECTOR_ID = os.getenv("BRIGHTDATA_APARTMENTS_COLLECTOR_ID", "c_mpspx4t3p0f90ylra")

METROS = {
    "nyc": "New York",
    "la": "Los Angeles",
    "chicago": "Chicago",
    "dallas": "Dallas",
    "houston": "Houston",
    "washington_dc": "Washington DC",
    "philadelphia": "Philadelphia",
    "miami": "Miami",
    "atlanta": "Atlanta",
    "boston": "Boston",
    "phoenix": "Phoenix",
    "sf": "San Francisco",
    "riverside": "Riverside",
    "detroit": "Detroit",
    "seattle": "Seattle",
    "minneapolis": "Minneapolis",
    "san_diego": "San Diego",
    "tampa": "Tampa",
    "denver": "Denver",
    "baltimore": "Baltimore",
    "st_louis": "St. Louis",
    "charlotte": "Charlotte",
    "orlando": "Orlando",
    "san_antonio": "San Antonio",
    "portland": "Portland",
    "sacramento": "Sacramento",
    "pittsburgh": "Pittsburgh",
    "austin": "Austin",
    "las_vegas": "Las Vegas",
    "cincinnati": "Cincinnati",
    "kansas_city": "Kansas City",
    "columbus": "Columbus",
    "indianapolis": "Indianapolis",
    "cleveland": "Cleveland",
    "san_jose": "San Jose",
    "nashville": "Nashville",
    "virginia_beach": "Virginia Beach",
    "providence": "Providence",
    "milwaukee": "Milwaukee",
    "jacksonville": "Jacksonville",
    "oklahoma_city": "Oklahoma City",
    "raleigh": "Raleigh",
    "memphis": "Memphis",
    "richmond": "Richmond",
    "new_orleans": "New Orleans",
    "louisville": "Louisville",
    "salt_lake_city": "Salt Lake City",
    "hartford": "Hartford",
    "buffalo": "Buffalo",
    "birmingham": "Birmingham",
}

DEMO_METROS = ["sf", "austin", "phoenix", "nyc", "chicago"]
TOP25_METROS = [
    "nyc", "la", "chicago", "dallas", "houston", "washington_dc", "philadelphia",
    "miami", "atlanta", "boston", "phoenix", "sf", "riverside", "detroit",
    "seattle", "minneapolis", "san_diego", "tampa", "denver", "baltimore",
    "st_louis", "charlotte", "orlando", "san_antonio", "portland",
]
TOP50_METROS = TOP25_METROS + [
    "sacramento", "pittsburgh", "austin", "las_vegas", "cincinnati",
    "kansas_city", "columbus", "indianapolis", "cleveland", "san_jose",
    "nashville", "virginia_beach", "providence", "milwaukee", "jacksonville",
    "oklahoma_city", "raleigh", "memphis", "richmond", "new_orleans",
    "louisville", "salt_lake_city", "hartford", "buffalo", "birmingham",
]
PRESETS = {"demo": DEMO_METROS, "top25": TOP25_METROS, "top50": TOP50_METROS}

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

LINKEDIN_HIGH_VALUE_QUERIES = [
    "property manager",
    "leasing consultant",
    "construction manager",
    "registered nurse",
    "warehouse associate",
    "software engineer",
]

APARTMENTS_URLS = {
    "nyc": "https://www.apartments.com/new-york-ny/",
    "la": "https://www.apartments.com/los-angeles-ca/",
    "chicago": "https://www.apartments.com/chicago-il/",
    "dallas": "https://www.apartments.com/dallas-tx/",
    "houston": "https://www.apartments.com/houston-tx/",
    "washington_dc": "https://www.apartments.com/washington-dc/",
    "philadelphia": "https://www.apartments.com/philadelphia-pa/",
    "miami": "https://www.apartments.com/miami-fl/",
    "atlanta": "https://www.apartments.com/atlanta-ga/",
    "boston": "https://www.apartments.com/boston-ma/",
    "phoenix": "https://www.apartments.com/phoenix-az/",
    "sf": "https://www.apartments.com/san-francisco-ca/",
    "riverside": "https://www.apartments.com/riverside-ca/",
    "detroit": "https://www.apartments.com/detroit-mi/",
    "seattle": "https://www.apartments.com/seattle-wa/",
    "minneapolis": "https://www.apartments.com/minneapolis-mn/",
    "san_diego": "https://www.apartments.com/san-diego-ca/",
    "tampa": "https://www.apartments.com/tampa-fl/",
    "denver": "https://www.apartments.com/denver-co/",
    "baltimore": "https://www.apartments.com/baltimore-md/",
    "st_louis": "https://www.apartments.com/saint-louis-mo/",
    "charlotte": "https://www.apartments.com/charlotte-nc/",
    "orlando": "https://www.apartments.com/orlando-fl/",
    "san_antonio": "https://www.apartments.com/san-antonio-tx/",
    "portland": "https://www.apartments.com/portland-or/",
    "sacramento": "https://www.apartments.com/sacramento-ca/",
    "pittsburgh": "https://www.apartments.com/pittsburgh-pa/",
    "austin": "https://www.apartments.com/austin-tx/",
    "las_vegas": "https://www.apartments.com/las-vegas-nv/",
    "cincinnati": "https://www.apartments.com/cincinnati-oh/",
    "kansas_city": "https://www.apartments.com/kansas-city-mo/",
    "columbus": "https://www.apartments.com/columbus-oh/",
    "indianapolis": "https://www.apartments.com/indianapolis-in/",
    "cleveland": "https://www.apartments.com/cleveland-oh/",
    "san_jose": "https://www.apartments.com/san-jose-ca/",
    "nashville": "https://www.apartments.com/nashville-tn/",
    "virginia_beach": "https://www.apartments.com/virginia-beach-va/",
    "providence": "https://www.apartments.com/providence-ri/",
    "milwaukee": "https://www.apartments.com/milwaukee-wi/",
    "jacksonville": "https://www.apartments.com/jacksonville-fl/",
    "oklahoma_city": "https://www.apartments.com/oklahoma-city-ok/",
    "raleigh": "https://www.apartments.com/raleigh-nc/",
    "memphis": "https://www.apartments.com/memphis-tn/",
    "richmond": "https://www.apartments.com/richmond-va/",
    "new_orleans": "https://www.apartments.com/new-orleans-la/",
    "louisville": "https://www.apartments.com/louisville-ky/",
    "salt_lake_city": "https://www.apartments.com/salt-lake-city-ut/",
    "hartford": "https://www.apartments.com/hartford-ct/",
    "buffalo": "https://www.apartments.com/buffalo-ny/",
    "birmingham": "https://www.apartments.com/birmingham-al/",
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


def bd_headers() -> dict[str, str]:
    token = os.getenv("BRIGHTDATA_TOKEN")
    if not token:
        raise RuntimeError("BRIGHTDATA_TOKEN is not set")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def run_id() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str))


def es_json(method: str, path: str, body: dict | None = None) -> dict:
    kwargs = {"timeout": 120}
    if body is not None:
        kwargs["json"] = body
    res = requests.request(method, ES_URL + path, **kwargs)
    if res.status_code >= 400:
        raise RuntimeError(f"ES {method} {path} failed: {res.status_code} {res.text[:300]}")
    return res.json() if res.text else {}


def ensure_index(index: str) -> None:
    res = requests.head(f"{ES_URL}/{index}", timeout=30)
    if res.status_code == 404:
        es_json("PUT", f"/{index}", {"mappings": {"dynamic": True}})
    elif res.status_code >= 400:
        raise RuntimeError(f"ES HEAD {index} failed: {res.status_code}")


def bulk_upsert(index: str, docs: list[dict], id_fields: list[str]) -> int:
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
    res = requests.post(
        f"{ES_URL}/_bulk",
        data=("\n".join(lines) + "\n").encode(),
        headers={"Content-Type": "application/x-ndjson"},
        timeout=180,
    )
    if res.status_code >= 400:
        raise RuntimeError(f"ES bulk failed: {res.status_code} {res.text[:300]}")
    out = res.json()
    if out.get("errors"):
        errors = [i for i in out["items"] if i.get("update", {}).get("error")]
        raise RuntimeError(f"ES bulk had {len(errors)} errors, first={errors[:1]}")
    return len(docs)


def count(index: str) -> int:
    try:
        return es_json("GET", f"/{index}/_count").get("count", 0)
    except Exception:
        return -1


def trigger_linkedin(inputs: list[dict]) -> str:
    params = {
        "dataset_id": LINKEDIN_JOBS_DATASET_ID,
        "type": "discover_new",
        "discover_by": "keyword",
        "format": "json",
        "include_errors": "true",
    }
    res = requests.post(
        f"{BD_API}/trigger",
        params=params,
        headers=bd_headers(),
        json={"input": inputs},
        timeout=90,
    )
    if res.status_code >= 400:
        raise RuntimeError(f"Bright Data trigger failed: {res.status_code} {res.text[:1000]}")
    data = res.json()
    snapshot_id = data.get("snapshot_id") or data.get("id")
    if not snapshot_id:
        raise RuntimeError(f"Bright Data trigger did not return snapshot_id: {data}")
    return snapshot_id


def poll_snapshot(snapshot_id: str, poll_seconds: int, timeout_minutes: int) -> dict:
    deadline = time.time() + timeout_minutes * 60
    while time.time() < deadline:
        res = requests.get(f"{BD_API}/progress/{snapshot_id}", headers=bd_headers(), timeout=60)
        if res.status_code >= 400:
            raise RuntimeError(f"Bright Data progress failed: {res.status_code} {res.text[:500]}")
        data = res.json()
        status = data.get("status")
        print(f"snapshot {snapshot_id}: {status}")
        if status == "ready":
            return data
        if status == "failed":
            raise RuntimeError(f"Bright Data snapshot failed: {data}")
        time.sleep(poll_seconds)
    raise TimeoutError(f"Timed out waiting for Bright Data snapshot {snapshot_id}")


def download_snapshot(snapshot_id: str) -> list[dict]:
    res = requests.get(
        f"{BD_API}/snapshot/{snapshot_id}",
        params={"format": "json"},
        headers=bd_headers(),
        timeout=300,
    )
    if res.status_code >= 400:
        raise RuntimeError(f"Bright Data download failed: {res.status_code} {res.text[:500]}")
    data = res.json()
    if not isinstance(data, list):
        raise RuntimeError(f"Bright Data snapshot was not a list: {type(data).__name__}")
    return data


def trigger_studio_batch(collector_id: str, inputs: list[dict], version: str | None) -> str:
    params = {"collector": collector_id, "queue_next": "1", "name": "homestar-apartments"}
    if version:
        params["version"] = version
    res = requests.post(
        f"{BD_API.rsplit('/datasets/v3', 1)[0]}/dca/trigger",
        params=params,
        headers=bd_headers(),
        json=inputs,
        timeout=90,
    )
    if res.status_code >= 400:
        raise RuntimeError(f"Bright Data Studio trigger failed: {res.status_code} {res.text[:1000]}")
    data = res.json()
    collection_id = data.get("collection_id") or data.get("id")
    if not collection_id:
        raise RuntimeError(f"Bright Data Studio trigger did not return collection_id: {data}")
    return collection_id


def poll_studio_dataset(collection_id: str, poll_seconds: int, timeout_minutes: int) -> list[dict]:
    deadline = time.time() + timeout_minutes * 60
    url = f"{BD_API.rsplit('/datasets/v3', 1)[0]}/dca/dataset"
    while time.time() < deadline:
        res = requests.get(url, params={"id": collection_id}, headers=bd_headers(), timeout=120)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list):
                return data
            print(f"collection {collection_id}: {data}")
        elif res.status_code == 202:
            try:
                data = res.json()
            except Exception:
                data = {"status": "building"}
            print(f"collection {collection_id}: {data.get('status', 'building')}")
        else:
            raise RuntimeError(f"Bright Data Studio dataset failed: {res.status_code} {res.text[:500]}")
        time.sleep(poll_seconds)
    raise TimeoutError(f"Timed out waiting for Bright Data Studio collection {collection_id}")


def linkedin_inputs(metros: list[str], queries: list[str], time_range: str) -> list[dict]:
    return [
        {
            "location": METROS[metro_id],
            "keyword": query,
            "country": "US",
            "time_range": time_range,
            "selective_search": True,
        }
        for metro_id in metros
        for query in queries
    ]


def normalize_linkedin(items: list[dict], metro_lookup: dict[tuple[str, str], str]) -> list[dict]:
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    docs = []
    for item in items:
        discovery = item.get("discovery_input") or {}
        location = discovery.get("location") or item.get("input", {}).get("location")
        keyword = discovery.get("keyword") or item.get("input", {}).get("keyword")
        metro_id = metro_lookup.get((location, keyword))
        if not metro_id:
            for candidate, display in METROS.items():
                if location and display.lower() in str(location).lower():
                    metro_id = candidate
                    break
        doc = {
            "id": item.get("job_posting_id") or item.get("id") or item.get("url"),
            "title": item.get("job_title"),
            "company": item.get("company_name"),
            "location": item.get("job_location"),
            "postedAt": item.get("job_posted_date"),
            "url": item.get("url"),
            "metro_id": metro_id,
            "query": keyword,
            "source": "BrightData:LinkedInJobsAPI",
            "scraped_at": now,
            "job_summary": item.get("job_summary"),
            "job_seniority_level": item.get("job_seniority_level"),
            "job_function": item.get("job_function"),
            "job_employment_type": item.get("job_employment_type"),
            "job_industries": item.get("job_industries"),
            "job_base_pay_range": item.get("job_base_pay_range"),
            "job_num_applicants": item.get("job_num_applicants"),
            "country_code": item.get("country_code"),
            "apply_link": item.get("apply_link"),
        }
        doc = {k: v for k, v in doc.items() if v not in (None, "")}
        if doc.get("id") and doc.get("title"):
            docs.append(doc)
    return docs


def first_present(item: dict, names: list[str]):
    lower = {str(k).lower().replace(" ", "_"): v for k, v in item.items()}
    for name in names:
        if name in item and item[name] not in (None, ""):
            return item[name]
        key = name.lower().replace(" ", "_")
        if lower.get(key) not in (None, ""):
            return lower[key]
    return None


def apartments_inputs(metros: list[str], pages: int, page_offset: int) -> list[dict]:
    inputs = []
    for metro_id in metros:
        base = APARTMENTS_URLS[metro_id]
        for offset in range(page_offset, page_offset + pages):
            page = offset + 1
            url = base if page == 1 else base.rstrip("/") + f"/{page}/"
            inputs.append({"url": url, "metro_id": metro_id, "page": page})
    return inputs


def normalize_apartments(items: list[dict]) -> list[dict]:
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    docs = []
    for item in items:
        source_input = item.get("input") or {}
        prop_url = first_present(item, ["url", "property_url", "listing_url", "link", "href"])
        if isinstance(prop_url, dict):
            prop_url = prop_url.get("url") or prop_url.get("href")
        title = first_present(item, ["listingTitle", "listing_title", "title", "property_name", "building_name", "name"])
        address = first_present(item, ["address_full", "address", "full_address", "property_address", "street_address"])
        source_url = source_input.get("url") or first_present(item, ["source_url", "search_url"])
        metro_id = source_input.get("metro_id")
        if not metro_id and source_url:
            for candidate, base in APARTMENTS_URLS.items():
                if base.rstrip("/") in str(source_url):
                    metro_id = candidate
                    break
        key_seed = prop_url or "|".join(str(v or "") for v in (title, address, metro_id))
        if not key_seed.strip("|"):
            continue
        doc = {
            "listingKey": hashlib.sha1(str(key_seed).encode()).hexdigest()[:16],
            "listingTitle": title,
            "pricing_rentRange": first_present(item, ["pricing_rentRange", "rent_text", "rent", "price", "price_range", "rent_range"]),
            "address_full": address,
            "url": prop_url,
            "metro_id": metro_id,
            "source": "BrightData:ApartmentsStudio",
            "source_url": source_url,
            "scraped_at": now,
            "specs_bedRange": first_present(item, ["beds", "bedrooms", "bed_range", "bed_counts_visible"]),
            "market_availabilityText": first_present(item, ["availability", "availability_text", "available_units"]),
            "market_rating": first_present(item, ["rating", "property_rating"]),
            "media_primaryImage": first_present(item, ["image", "image_url", "primary_image", "photo"]),
            "contact_phone": first_present(item, ["phone", "contact_phone"]),
            "concession_text": first_present(item, ["concession", "concessions", "specials", "special_offer"]),
            "location_latitude": first_present(item, ["latitude", "lat"]),
            "location_longitude": first_present(item, ["longitude", "lng", "lon"]),
        }
        docs.append({k: v for k, v in doc.items() if v not in (None, "")})
    return docs


def main() -> None:
    load_env()
    p = argparse.ArgumentParser()
    p.add_argument("--source", choices=["linkedin", "apartments"], default="linkedin")
    p.add_argument("--preset", choices=sorted(PRESETS), default=None)
    p.add_argument("--metros", nargs="+", choices=sorted(METROS), default=None)
    p.add_argument("--queries", nargs="*", default=None)
    p.add_argument("--query-preset", choices=["full", "high-value"], default="full")
    p.add_argument("--time-range", default="Past week")
    p.add_argument("--pages", type=int, default=1)
    p.add_argument("--page-offset", type=int, default=0)
    p.add_argument("--apartments-collector-id", default=APARTMENTS_COLLECTOR_ID)
    p.add_argument("--studio-version", default="dev")
    p.add_argument("--snapshot-id", default=None)
    p.add_argument("--collection-id", default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--poll-seconds", type=int, default=30)
    p.add_argument("--timeout-minutes", type=int, default=60)
    args = p.parse_args()

    rid = run_id()
    out_dir = RAW_ROOT / rid
    out_dir.mkdir(parents=True, exist_ok=True)
    metros = args.metros or PRESETS.get(args.preset or "top50")
    if args.source == "linkedin":
        default_queries = LINKEDIN_HIGH_VALUE_QUERIES if args.query_preset == "high-value" else LINKEDIN_QUERIES
        queries = args.queries or default_queries
        inputs = linkedin_inputs(metros, queries, args.time_range)
        metro_lookup = {(METROS[m], q): m for m in metros for q in queries}

        print(f"run_id={rid} source=linkedin inputs={len(inputs)} es={ES_URL}")
        print("before linkedin", count(INDEX_PREFIX + "linkedin_job_postings"))
        write_json(out_dir / "inputs.json", inputs)
        if args.dry_run:
            print("dry_run=true")
            print(f"metros={len(metros)} queries={len(queries)} inputs={len(inputs)}")
            print(f"out={out_dir.relative_to(ROOT)}")
            return

        snapshot_id = args.snapshot_id or trigger_linkedin(inputs)
        write_json(out_dir / "snapshot.json", {"snapshot_id": snapshot_id})
        poll_snapshot(snapshot_id, args.poll_seconds, args.timeout_minutes)
        items = download_snapshot(snapshot_id)
        write_json(out_dir / "linkedin_raw.json", items)
        docs = normalize_linkedin(items, metro_lookup)
        write_json(out_dir / "linkedin_normalized.json", docs)
        indexed = bulk_upsert(INDEX_PREFIX + "linkedin_job_postings", docs, ["id", "metro_id"])
        requests.post(f"{ES_URL}/{INDEX_PREFIX}linkedin_job_postings/_refresh", timeout=60)
        print(f"snapshot={snapshot_id} raw={len(items)} normalized={len(docs)} indexed={indexed}")
        print("after linkedin", count(INDEX_PREFIX + "linkedin_job_postings"))
    elif args.source == "apartments":
        inputs = apartments_inputs(metros, args.pages, args.page_offset)
        print(f"run_id={rid} source=apartments inputs={len(inputs)} es={ES_URL}")
        print("before apartments", count(INDEX_PREFIX + "apartments_com_properties"))
        write_json(out_dir / "inputs.json", inputs)
        if args.dry_run:
            print("dry_run=true")
            print(f"metros={len(metros)} pages={args.pages} inputs={len(inputs)}")
            print(f"out={out_dir.relative_to(ROOT)}")
            return
        collection_id = args.collection_id or trigger_studio_batch(args.apartments_collector_id, inputs, args.studio_version)
        write_json(out_dir / "collection.json", {"collection_id": collection_id, "collector_id": args.apartments_collector_id})
        items = poll_studio_dataset(collection_id, args.poll_seconds, args.timeout_minutes)
        write_json(out_dir / "apartments_raw.json", items)
        docs = normalize_apartments(items)
        write_json(out_dir / "apartments_normalized.json", docs)
        indexed = bulk_upsert(INDEX_PREFIX + "apartments_com_properties", docs, ["listingKey"])
        requests.post(f"{ES_URL}/{INDEX_PREFIX}apartments_com_properties/_refresh", timeout=60)
        print(f"collection={collection_id} raw={len(items)} normalized={len(docs)} indexed={indexed}")
        print("after apartments", count(INDEX_PREFIX + "apartments_com_properties"))
    print(f"out={out_dir.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
