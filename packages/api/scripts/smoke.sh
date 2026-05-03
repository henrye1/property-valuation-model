#!/usr/bin/env bash
# Post-deploy smoke test.
# Usage: scripts/smoke.sh https://api.example.com <VALID_JWT>
set -euo pipefail

BASE="${1:?BASE_URL required}"
TOKEN="${2:?JWT required}"
AUTH="Authorization: Bearer ${TOKEN}"

fail() { echo "FAIL: $*" >&2; exit 1; }
ok() { echo "ok: $*"; }

code=$(curl -s -o /tmp/health.json -w '%{http_code}' "${BASE}/healthz")
[ "${code}" = "200" ] || fail "/healthz returned ${code}"
grep -q '"status":"ok"' /tmp/health.json || fail "/healthz body missing status"
ok "/healthz"

code=$(curl -s -o /tmp/me.json -w '%{http_code}' -H "${AUTH}" "${BASE}/me")
[ "${code}" = "200" ] || fail "/me returned ${code}"
grep -q '"role"' /tmp/me.json || fail "/me body missing role"
ok "/me"

code=$(curl -s -o /tmp/ents.json -w '%{http_code}' -H "${AUTH}" "${BASE}/entities")
[ "${code}" = "200" ] || fail "/entities returned ${code}"
ok "/entities"

# ----- Plan 3: /imports + exports smoke -----

echo "[smoke] GET /imports"
curl -fsSL "${BASE}/imports" -H "${AUTH}" -o /tmp/imports.json
echo "  total = $(jq -r .total /tmp/imports.json)"
ok "/imports"

# If a known snapshot UUID is in env, smoke the exports.
if [ -n "${SMOKE_SNAPSHOT_ID:-}" ]; then
  echo "[smoke] GET /snapshots/${SMOKE_SNAPSHOT_ID}/export.pdf"
  curl -fsSL "${BASE}/snapshots/${SMOKE_SNAPSHOT_ID}/export.pdf" \
       -H "${AUTH}" -o /tmp/snapshot.pdf
  test "$(head -c 4 /tmp/snapshot.pdf)" = "%PDF" \
    || fail "PDF magic bytes missing"
  echo "  PDF: $(wc -c < /tmp/snapshot.pdf) bytes"
  ok "/snapshots/{id}/export.pdf"

  echo "[smoke] GET /snapshots/${SMOKE_SNAPSHOT_ID}/export.xlsx"
  curl -fsSL "${BASE}/snapshots/${SMOKE_SNAPSHOT_ID}/export.xlsx" \
       -H "${AUTH}" -o /tmp/snapshot.xlsx
  echo "  XLSX: $(wc -c < /tmp/snapshot.xlsx) bytes"
  ok "/snapshots/{id}/export.xlsx"
else
  echo "[smoke] SKIP exports (set SMOKE_SNAPSHOT_ID to enable)"
fi

echo "all smoke checks passed"
