#!/usr/bin/env bash
set -euo pipefail
cd /root/gptimage-gateway-rs
BIN=run/target/release/gptimage-gateway-rs
WEB=run/web/out
ENV_FILE=secrets/gateway.env

if [[ ! -f "$ENV_FILE" ]]; then
  JWT=$(openssl rand -hex 32)
  ADMIN_PASS="panda-admin-$(openssl rand -hex 4)"
  cat >"$ENV_FILE" <<EOF
DATA_PLANE=upstream
IMAGE_ENABLED=1
GATEWAY_LISTEN=0.0.0.0:8014
PIN_ACCOUNT_FILE=/root/gptimage-gateway-rs/secrets/pin_account.json
ACCOUNTS_FILE=/root/gptimage-gateway-rs/secrets/accounts_pool.json
AUTH_DB_PATH=/root/gptimage-gateway-rs/data/auth.db
RUST_LOG=info
AUTH_DISABLE=0
AUTH_MODE=jwt
AUTH_JWT_SECRET=$JWT
AUTH_BOOTSTRAP_ADMIN_USER=admin
AUTH_BOOTSTRAP_ADMIN_PASSWORD=$ADMIN_PASS
GATEWAY_STATIC_DIR=$WEB
EOF
  chmod 600 "$ENV_FILE"
fi

pkill -f "$BIN" 2>/dev/null || true
sleep 1
mkdir -p data/runlogs
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a
nohup "$BIN" >data/runlogs/rust-gateway-8014.log 2>&1 &
echo $! >data/runlogs/rust-gateway-8014.pid
sleep 3
curl -fsS http://127.0.0.1:8014/health
echo
grep AUTH_BOOTSTRAP_ADMIN_PASSWORD "$ENV_FILE" | head -1
