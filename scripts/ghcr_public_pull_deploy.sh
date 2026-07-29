#!/usr/bin/env bash
# Temporary public GHCR → Panda docker pull → restore private.
#
# Prereq (local):
#   GHCR_TOKEN file with PAT (packages:read+write, or classic all scopes)
#   ssh panda works
#
# Usage:
#   GHCR_TOKEN_FILE=~/Desktop/ghcr.txt bash scripts/ghcr_public_pull_deploy.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOKEN_FILE="${GHCR_TOKEN_FILE:-$ROOT/secrets/ghcr_token}"
PACKAGE="gptimage-gateway-rs"
OWNER="croppedtravelleralex"
IMAGE="ghcr.io/${OWNER}/${PACKAGE}:latest"
API="https://api.github.com/user/packages/container/${PACKAGE}"

if [[ ! -f "$TOKEN_FILE" ]]; then
  echo "missing token file: $TOKEN_FILE" >&2
  exit 2
fi
TOKEN=$(tr -d '\r\n' <"$TOKEN_FILE")

ghcr_api() {
  curl -sS -X "$1" -H "Authorization: Bearer $TOKEN" \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "$API" "${@:2}"
}

restore_private() {
  echo "==> restore GHCR package visibility: private"
  ghcr_api PATCH -d '{"visibility":"private"}' >/dev/null || true
}

trap restore_private EXIT

echo "==> [1/5] set GHCR package public (temporary)"
ghcr_api PATCH -d '{"visibility":"public"}' | python3 -c 'import sys,json; d=json.load(sys.stdin); print("visibility:", d.get("visibility", d))'

echo "==> [2/5] panda git pull + stop host gateway"
ssh panda "cd /root/gptimage-gateway-rs && git pull origin main && pkill -f run/target/release/gptimage-gateway-rs 2>/dev/null || true; docker compose -f deploy/independent-compose.yml down 2>/dev/null || true"

echo "==> [3/5] panda docker pull (no login needed while public)"
ssh panda "docker pull $IMAGE"

echo "==> [4/5] normalize gateway.env + compose up"
ssh panda "cd /root/gptimage-gateway-rs && \
  sed -i 's|^PIN_ACCOUNT_FILE=.*|PIN_ACCOUNT_FILE=/secrets/pin_account.json|' secrets/gateway.env && \
  sed -i 's|^ACCOUNTS_FILE=.*|ACCOUNTS_FILE=/secrets/accounts_pool.json|' secrets/gateway.env && \
  sed -i 's|^AUTH_DB_PATH=.*|AUTH_DB_PATH=/data/auth.db|' secrets/gateway.env && \
  sed -i 's|^GATEWAY_STATIC_DIR=.*|GATEWAY_STATIC_DIR=/var/www/gateway-ui|' secrets/gateway.env && \
  docker compose -f deploy/independent-compose.yml up -d && sleep 4 && curl -fsS http://127.0.0.1:8014/health"

echo "==> [5/5] smoke"
ssh panda "cd /root/gptimage-gateway-rs && GATEWAY_LISTEN=127.0.0.1:8014 IMAGE_ENABLED=1 STREAM_ENABLED=1 bash scripts/independent_acceptance.sh"

echo "GHCR_PUBLIC_PULL_DEPLOY_OK"
