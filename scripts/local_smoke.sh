#!/usr/bin/env bash
# Smoke-check local gateway matches implemented routes (post local_bringup_wsl.sh).
set -euo pipefail

LISTEN="${GATEWAY_LISTEN:-127.0.0.1:8013}"
BASE="http://${LISTEN}"
IMAGE_EXPECT="${IMAGE_SMOKE_EXPECT:-501}"

fail() { echo "FAIL: $*" >&2; exit 1; }

code=$(curl -s -o /tmp/gws-health.json -w '%{http_code}' "$BASE/health")
[[ "$code" == "200" ]] || fail "/health -> $code"
grep -q '"runtime":"rust"' /tmp/gws-health.json || fail "health missing runtime rust"

code=$(curl -s -o /tmp/gws-cap.json -w '%{http_code}' "$BASE/api/backend/capabilities")
[[ "$code" == "200" ]] || fail "/api/backend/capabilities -> $code"

code=$(curl -s -o /tmp/gws-models.json -w '%{http_code}' "$BASE/v1/models")
[[ "$code" == "200" ]] || fail "/v1/models -> $code (AUTH_DISABLE=1 expected)"

code=$(curl -s -o /tmp/gws-img.json -w '%{http_code}' \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"smoke","model":"gpt-image-2"}' \
  "$BASE/v1/images/generations")
[[ "$code" == "$IMAGE_EXPECT" ]] || fail "/v1/images/generations -> $code (want $IMAGE_EXPECT)"

echo "SMOKE_OK listen=$LISTEN"
