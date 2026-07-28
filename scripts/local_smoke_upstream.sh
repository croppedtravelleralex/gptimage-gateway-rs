#!/usr/bin/env bash
# Smoke gateway with DATA_PLANE=upstream (helper optional / not required for chat+image).
#
# Prereq: gateway running with DATA_PLANE=upstream (see local_bringup_wsl.sh).
# Optional: IMAGE_ENABLED=1 UPSTREAM_IMAGE_TIMEOUT_SECS=90 for image leg.
set -euo pipefail

LISTEN="${GATEWAY_LISTEN:-127.0.0.1:8013}"
BASE="http://${LISTEN}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COOKIE_JAR="${TMPDIR:-/tmp}/gws-upstream-smoke-cookies.txt"
ADMIN_USER="${AUTH_BOOTSTRAP_ADMIN_USER:-admin}"
IMAGE_ENABLED="${IMAGE_ENABLED:-0}"
CHAT_TIMEOUT="${UPSTREAM_CHAT_TIMEOUT_SECS:-120}"
IMAGE_TIMEOUT="${UPSTREAM_IMAGE_TIMEOUT_SECS:-90}"

fail() { echo "FAIL: $*" >&2; exit 1; }

curl_auth=()
rm -f "$COOKIE_JAR"

code=$(curl -s -o /tmp/gws-health.json -w '%{http_code}' "$BASE/health")
[[ "$code" == "200" ]] || fail "/health -> $code"
grep -q '"runtime":"rust"' /tmp/gws-health.json || fail "health missing runtime rust"

auth_disabled=$(python3 -c 'import json; print(json.load(open("/tmp/gws-health.json")).get("auth_disabled", False))' 2>/dev/null || echo "false")
if [[ "$auth_disabled" == "True" || "$auth_disabled" == "true" ]]; then
  :
else
  if [[ -f "$ROOT/secrets/local_admin_password" ]]; then
    ADMIN_PASS=$(tr -d '\r\n' <"$ROOT/secrets/local_admin_password")
  else
    ADMIN_PASS="${AUTH_BOOTSTRAP_ADMIN_PASSWORD:-}"
  fi
  [[ -n "$ADMIN_PASS" ]] || fail "missing secrets/local_admin_password (run local_bringup_wsl.sh first)"

  code=$(curl -s -c "$COOKIE_JAR" -b "$COOKIE_JAR" -o /tmp/gws-login.json -w '%{http_code}' \
    -H 'Content-Type: application/json' \
    -d "{\"username\":\"$ADMIN_USER\",\"password\":\"$ADMIN_PASS\"}" \
    "$BASE/api/auth/login")
  [[ "$code" == "200" ]] || fail "/api/auth/login -> $code"
  curl_auth=(-b "$COOKIE_JAR")
fi

code=$(curl -s "${curl_auth[@]}" -o /tmp/gws-cap.json -w '%{http_code}' "$BASE/api/backend/capabilities")
[[ "$code" == "200" ]] || fail "/api/backend/capabilities -> $code"
grep -qE '"data_plane"[[:space:]]*:[[:space:]]*"upstream"' /tmp/gws-cap.json \
  || fail "capabilities missing data_plane=upstream (got: $(tr -d '\n' </tmp/gws-cap.json | head -c 200))"

code=$(curl -s "${curl_auth[@]}" --max-time "$CHAT_TIMEOUT" \
  -o /tmp/gws-chat.json -w '%{http_code}' \
  -H 'Content-Type: application/json' \
  -d '{"model":"gpt-4o-mini","stream":false,"messages":[{"role":"user","content":"upstream smoke: reply with ok"}]}' \
  "$BASE/v1/chat/completions")
[[ "$code" == "200" || "$code" == "502" || "$code" == "504" ]] \
  || fail "/v1/chat/completions -> $code (200/502/504 expected; 502 ok if pin token invalid)"
if [[ "$code" == "200" ]]; then
  grep -q '"choices"' /tmp/gws-chat.json || fail "chat response missing choices"
fi

if [[ "$IMAGE_ENABLED" == "1" || "$IMAGE_ENABLED" == "true" ]]; then
  code=$(curl -s "${curl_auth[@]}" --max-time "$IMAGE_TIMEOUT" \
    -o /tmp/gws-img.json -w '%{http_code}' \
    -H 'Content-Type: application/json' \
    -d '{"prompt":"upstream smoke","model":"gpt-image-2","n":1,"size":"1024x1024","response_format":"b64_json"}' \
    "$BASE/v1/images/generations")
  [[ "$code" == "200" || "$code" == "502" || "$code" == "504" ]] \
    || fail "/v1/images/generations -> $code"
  echo "image leg: HTTP $code (timeout=${IMAGE_TIMEOUT}s)"
fi

echo "SMOKE_UPSTREAM_OK listen=$LISTEN data_plane=upstream auth_disabled=$auth_disabled image=$IMAGE_ENABLED"
