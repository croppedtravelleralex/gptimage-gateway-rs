#!/usr/bin/env bash
# Independent upstream gateway on panda (:8014). Run ON panda after git pull.
#
# Prereq:
#   - docker login ghcr.io (read:packages PAT) OR secrets/ghcr_token present
#   - chatgpt2api-local :8012 running (for db copy / pin export)
#
# Usage:
#   cd /root/gptimage-gateway-rs
#   git pull origin main
#   bash scripts/panda_deploy_independent.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SECRETS="$ROOT/secrets"
DATA="$ROOT/data"
COMPOSE_FILE="$ROOT/deploy/independent-compose.yml"
IMAGE="ghcr.io/croppedtravelleralex/gptimage-gateway-rs:latest"

fail() { echo "FATAL: $*" >&2; exit 1; }

echo "==> [1/7] sync gptimage databases (read-only copy)"
bash "$ROOT/scripts/panda_sync_gptimage_db.sh"

echo "==> [2/7] export pin + accounts pool from copied accounts.db"
mkdir -p "$SECRETS"
ACCOUNTS_DB="$DATA/gptimage/accounts.db"
[[ -f "$ACCOUNTS_DB" ]] || fail "missing $ACCOUNTS_DB — run panda_sync_gptimage_db.sh"

ACCOUNTS_DB="$ACCOUNTS_DB" OUT_PATH="$SECRETS/pin_account.json" \
  python3 "$ROOT/scripts/export_pin_account.py"
ACCOUNTS_DB="$ACCOUNTS_DB" OUT_PATH="$SECRETS/accounts_pool.json" LIMIT="${ACCOUNTS_POOL_LIMIT:-20}" \
  python3 "$ROOT/scripts/export_accounts_pool.py"
chmod 600 "$SECRETS/pin_account.json" "$SECRETS/accounts_pool.json"

echo "==> [3/7] ensure gateway.env (container paths)"
ENV_FILE="$SECRETS/gateway.env"
if [[ ! -f "$ENV_FILE" ]]; then
  JWT="$(openssl rand -hex 32)"
  ADMIN_PASS="panda-admin-$(openssl rand -hex 4)"
  cat >"$ENV_FILE" <<EOF
DATA_PLANE=upstream
IMAGE_ENABLED=1
GATEWAY_LISTEN=0.0.0.0:8014
PIN_ACCOUNT_FILE=/secrets/pin_account.json
ACCOUNTS_FILE=/secrets/accounts_pool.json
AUTH_DB_PATH=/data/auth.db
RUST_LOG=info
AUTH_DISABLE=0
AUTH_MODE=jwt
AUTH_JWT_SECRET=$JWT
AUTH_BOOTSTRAP_ADMIN_USER=admin
AUTH_BOOTSTRAP_ADMIN_PASSWORD=$ADMIN_PASS
GATEWAY_STATIC_DIR=/var/www/gateway-ui
EOF
  chmod 600 "$ENV_FILE"
  echo "created $ENV_FILE (admin password in file)"
else
  # migrate host-mode paths from earlier bringup
  sed -i 's|^PIN_ACCOUNT_FILE=.*|PIN_ACCOUNT_FILE=/secrets/pin_account.json|' "$ENV_FILE"
  sed -i 's|^ACCOUNTS_FILE=.*|ACCOUNTS_FILE=/secrets/accounts_pool.json|' "$ENV_FILE"
  sed -i 's|^AUTH_DB_PATH=.*|AUTH_DB_PATH=/data/auth.db|' "$ENV_FILE"
  sed -i 's|^GATEWAY_STATIC_DIR=.*|GATEWAY_STATIC_DIR=/var/www/gateway-ui|' "$ENV_FILE"
  echo "reuse $ENV_FILE (normalized for compose)"
fi

echo "==> [4/7] ghcr login"
if [[ -f "$SECRETS/ghcr_token" ]]; then
  tr -d '\r\n' <"$SECRETS/ghcr_token" | docker login ghcr.io -u croppedtravelleralex --password-stdin
fi

echo "==> [5/7] pull image"
if ! docker pull "$IMAGE"; then
  fail "docker pull unauthorized — add secrets/ghcr_token (GitHub PAT read:packages) or run: docker login ghcr.io"
fi

echo "==> [6/7] compose up"
mkdir -p "$DATA"
docker compose -f "$COMPOSE_FILE" down 2>/dev/null || true
docker compose -f "$COMPOSE_FILE" up -d

echo "==> [7/7] acceptance smoke"
sleep 3
GATEWAY_LISTEN=127.0.0.1:8014 IMAGE_ENABLED=1 STREAM_ENABLED=1 \
  UPSTREAM_IMAGE_TIMEOUT_SECS=180 \
  bash "$ROOT/scripts/independent_acceptance.sh" || {
    echo "WARN: smoke failed — check docker logs and pin token"
    docker compose -f "$COMPOSE_FILE" logs --tail=40 gateway || true
    exit 1
  }

echo
echo "PANDA_DEPLOY_OK"
echo "  health:  curl -s http://127.0.0.1:8014/health"
echo "  UI:      http://<panda-host>:8014/showcase  (login: see secrets/gateway.env)"
echo "  :8012    untouched (chatgpt2api-local)"
