# HomeStar Elasticsearch Recovery Strategy

This app currently keeps production Elasticsearch data in the Docker volume
`docker_esdata` on the `groundswell` GCE instance. Container rebuilds are safe as
long as this volume is not removed. Destructive commands such as
`docker-compose down -v`, `docker volume rm docker_esdata`, or reinitializing the
VM disk can delete the database.

## Current Production Data

- GCP project: `groundswell-497917`
- VM: `groundswell`
- Zone: `us-west2-c`
- Static IP: `34.20.157.155`
- Elasticsearch container: `groundswell-es`
- Elasticsearch URL on VM: `http://localhost:9201`
- Docker volume: `docker_esdata`
- Volume mount: `/usr/share/elasticsearch/data`

## Safe Operations

These should preserve the ES volume:

```bash
cd /opt/groundswell/docker
docker-compose -f docker-compose.prod.yml up -d --build
docker-compose -f docker-compose.prod.yml restart groundswell-web
docker-compose -f docker-compose.prod.yml restart groundswell-api
```

## Dangerous Operations

Do not run these unless a verified backup exists:

```bash
docker-compose -f docker-compose.prod.yml down -v
docker volume rm docker_esdata
docker system prune --volumes
gcloud compute instances delete groundswell
```

## Recommended Backup Design

Use native Elasticsearch snapshots stored in a GCS bucket. Native snapshots are
incremental, can be restored index-by-index, and avoid copying Docker internals.

Recommended bucket:

```bash
gsutil mb -p groundswell-497917 -l us-west2 gs://homestar-es-snapshots
gsutil versioning set on gs://homestar-es-snapshots
```

Install the GCS repository plugin in the Elasticsearch container image, then
register a snapshot repository:

```bash
curl -X PUT "http://localhost:9201/_snapshot/homestar_gcs" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "gcs",
    "settings": {
      "bucket": "homestar-es-snapshots",
      "base_path": "prod"
    }
  }'
```

Create a manual snapshot:

```bash
curl -X PUT "http://localhost:9201/_snapshot/homestar_gcs/manual-$(date -u +%Y%m%dT%H%M%SZ)?wait_for_completion=true"
```

List snapshots:

```bash
curl "http://localhost:9201/_snapshot/homestar_gcs/_all?pretty"
```

Restore a snapshot:

```bash
curl -X POST "http://localhost:9201/_snapshot/homestar_gcs/<snapshot_name>/_restore" \
  -H "Content-Type: application/json" \
  -d '{
    "indices": "groundswell-*",
    "include_global_state": false
  }'
```

## Interim Backup Until GCS Snapshots Are Configured

If the native GCS plugin is not installed yet, take a VM-local compressed copy
of the Docker volume and upload it to GCS:

```bash
sudo tar -C /var/lib/docker/volumes/docker_esdata/_data \
  -czf /tmp/homestar-esdata-$(date -u +%Y%m%dT%H%M%SZ).tar.gz .

gsutil cp /tmp/homestar-esdata-*.tar.gz gs://homestar-es-snapshots/interim/
```

Only use this tarball method while Elasticsearch is stopped or after forcing a
quiet period. Native ES snapshots are preferred because they are consistent while
the cluster is running.

## Restore From Interim Tarball

```bash
cd /opt/groundswell/docker
docker-compose -f docker-compose.prod.yml stop elasticsearch

sudo rm -rf /var/lib/docker/volumes/docker_esdata/_data/*
sudo tar -C /var/lib/docker/volumes/docker_esdata/_data \
  -xzf /tmp/<backup-file>.tar.gz

docker-compose -f docker-compose.prod.yml up -d elasticsearch
curl "http://localhost:9201/_cat/indices?v"
```

## Suggested Schedule

- Hourly during active scraping: snapshot live/search indices.
- Daily full production snapshot.
- Keep 7 daily snapshots and 4 weekly snapshots.
- Before any deployment that touches Elasticsearch, take a manual snapshot and
  confirm it appears in `_snapshot/homestar_gcs/_all`.

## Pre-Deployment Safety Checklist

1. Confirm `docker_esdata` exists:
   `docker volume inspect docker_esdata`
2. Confirm ES counts:
   `curl "http://localhost:9201/_cat/indices/groundswell-*?v&h=index,docs.count,store.size"`
3. Take or verify a fresh snapshot.
4. Do not use `down -v`.
5. Rebuild/restart containers only.
