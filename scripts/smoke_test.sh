#!/usr/bin/env bash
# Re-run the validated retrievals for each source (no DB writes). Reads .env.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'

echo "=== FRED (keyless) PAYEMS ==="
curl -s "https://fred.stlouisfed.org/graph/fredgraph.csv?id=PAYEMS" | tail -1

echo "=== ZORI metro (range request) ==="
curl -s -H "User-Agent: $UA" -r 0-120 \
  "https://files.zillowstatic.com/research/public_csvs/zori/Metro_zori_uc_sfrcondomfr_sm_month.csv" | head -1

echo "=== Census BPS CBSA monthly xls (HTTP) ==="
curl -s -o /dev/null -w "  http=%{http_code} bytes=%{size_download}\n" \
  "https://www.census.gov/construction/bps/xls/cbsamonthly_202604.xls"

echo "=== Bright Data Web Unlocker (welcome) ==="
curl -s https://api.brightdata.com/request \
  -H "Content-Type: application/json" -H "Authorization: Bearer $BRIGHTDATA_TOKEN" \
  -d '{"zone":"web_unlocker1","url":"https://geo.brdtest.com/welcome.txt?product=unlocker&method=api","format":"raw"}' | head -1

echo "=== Apify account ==="
curl -s "https://api.apify.com/v2/users/me?token=$APIFY_TOKEN" \
  | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print('  user:',d['username'],'plan:',d['plan']['id'])"
echo "smoke test ok."
