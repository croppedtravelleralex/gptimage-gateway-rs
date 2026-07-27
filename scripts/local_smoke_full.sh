#!/usr/bin/env bash
# Full-stack smoke after LOCAL_MODE=full bringup.
set -euo pipefail

LISTEN="${GATEWAY_LISTEN:-127.0.0.1:8013}"
BASE="http://${LISTEN}"
COOKIE_JAR="${TMPDIR:-/tmp}/gws-smoke-cookies.txt"
ADMIN_USER="${AUTH_BOOTSTRAP_ADMIN_USER:-admin}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

fail() { echo "FAIL: $*" >&2; exit 1; }

if [[ -f "$ROOT/secrets/local_admin_password" ]]; then
  ADMIN_PASS=$(tr -d '\r\n' <"$ROOT/secrets/local_admin_password")
else
  ADMIN_PASS="${AUTH_BOOTSTRAP_ADMIN_PASSWORD:-}"
fi
[[ -n "$ADMIN_PASS" ]] || fail "missing secrets/local_admin_password (run local_bringup_wsl.sh first)"

rm -f "$COOKIE_JAR"

code=$(curl -s -o /tmp/gws-health.json -w '%{http_code}' "$BASE/health")
[[ "$code" == "200" ]] || fail "/health -> $code"
grep -q '"runtime":"rust"' /tmp/gws-health.json || fail "health missing runtime rust"
grep -q '"static_ui":true' /tmp/gws-health.json || echo "WARN: static_ui=false (web/out not built?)"

code=$(curl -s -o /tmp/gws-root.html -w '%{http_code}' "$BASE/")
[[ "$code" == "200" ]] || echo "WARN: GET / -> $code (static UI may be missing)"

code=$(curl -s -c "$COOKIE_JAR" -b "$COOKIE_JAR" -o /tmp/gws-login.json -w '%{http_code}' \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"$ADMIN_USER\",\"password\":\"$ADMIN_PASS\"}" \
  "$BASE/api/auth/login")
[[ "$code" == "200" ]] || fail "/api/auth/login -> $code"

code=$(curl -s -b "$COOKIE_JAR" -o /tmp/gws-me.json -w '%{http_code}' "$BASE/api/auth/me")
[[ "$code" == "200" ]] || fail "/api/auth/me -> $code"
grep -q '"username"' /tmp/gws-me.json || fail "/me missing user"

code=$(curl -s -b "$COOKIE_JAR" -o /tmp/gws-cap.json -w '%{http_code}' "$BASE/api/backend/capabilities")
[[ "$code" == "200" ]] || fail "/api/backend/capabilities -> $code"
grep -q '"image_generations":true' /tmp/gws-cap.json || echo "WARN: image_generations not true"

code=$(curl -s -b "$COOKIE_JAR" -o /tmp/gws-models.json -w '%{http_code}' "$BASE/v1/models")
[[ "$code" == "200" ]] || fail "/v1/models -> $code"

code=$(curl -s -b "$COOKIE_JAR" -o /tmp/gws-admin.json -w '%{http_code}' "$BASE/api/admin/status")
[[ "$code" == "200" ]] || fail "/api/admin/status -> $code"

code=$(curl -s -b "$COOKIE_JAR" -o /tmp/gws-quota.json -w '%{http_code}' "$BASE/v1/quota")
[[ "$code" == "200" || "$code" == "502" ]] || fail "/v1/quota -> $code (502 ok if pin token invalid)"

code=$(curl -s -b "$COOKIE_JAR" -o /tmp/gws-img.json -w '%{http_code}' \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"smoke test","model":"gpt-image-2","n":1,"size":"1024x1024","response_format":"b64_json"}' \
  "$BASE/v1/images/generations")
[[ "$code" == "200" || "$code" == "502" || "$code" == "504" ]] || fail "/v1/images/generations -> $code"

echo "SMOKE_FULL_OK listen=$LISTEN user=$ADMIN_USER"
