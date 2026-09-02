#!/usr/bin/env bash
# 探测 API 就绪：Postgres 不通则失败；MinIO 降级仍视为通过。
set -euo pipefail
BASE="${OPS_PROBE_URL:-http://127.0.0.1:18000}"
resp="$(curl -sfS "${BASE}/ready")"
status="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("status",""))' "$resp")"
if [[ "$status" == "fail" ]]; then
  echo "not ready: $resp" >&2
  exit 1
fi
echo "ready: $resp"
