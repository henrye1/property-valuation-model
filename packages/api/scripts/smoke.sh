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

echo "all smoke checks passed"
