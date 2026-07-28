#!/usr/bin/env bash
# Local WSL bringup: Rust gateway :8013 (+ optional helper :19001 + static Web UI).
#
# LOCAL_MODE=full   (default) JWT auth, IMAGE_ENABLED=1, DATA_PLANE=upstream, web/out UI
# LOCAL_MODE=minimal          AUTH_DISABLE=1 smoke-only (helper kept for backward compat)
# UPSTREAM_ONLY=1             skip helper; gateway only (valid when DATA_PLANE=upstream)
#
# Usage:
#   bash scripts/local_bringup_wsl.sh
#   UPSTREAM_ONLY=1 bash scripts/local_bringup_wsl.sh
#   LOCAL_MODE=minimal bash scripts/local_bringup_wsl.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

LOCAL_MODE="${LOCAL_MODE:-full}"
UPSTREAM_ONLY="${UPSTREAM_ONLY:-0}"
GPTIMAGE_ROOT="${GPTIMAGE_ROOT:-$ROOT/../gptimage}"
BIN="${BIN:-$ROOT/target/release/gptimage-gateway-rs}"
PIN="${PIN_ACCOUNT_FILE:-$ROOT/secrets/pin_account.json}"
HELPER_NAME=gptimage-local-helper
LOGDIR="$ROOT/data/runlogs"
WEB_OUT="$ROOT/web/out"
mkdir -p "$LOGDIR" "$ROOT/secrets"

need_build() {
  [[ "${REBUILD:-0}" == "1" ]] || [[ ! -x "$BIN" ]]
}

need_web_build() {
  [[ "${REBUILD:-0}" == "1" ]] || [[ ! -f "$WEB_OUT/index.html" ]]
}

if need_build; then
  echo "==> cargo build --release -p gateway"
  cargo build --release -p gateway
fi
if [[ ! -x "$BIN" ]]; then
  echo "missing binary: $BIN"
  exit 2
fi

if [[ ! -f "$PIN" ]]; then
  for EX in "$ROOT/secrets/pin_account.json.example" "$ROOT/deploy/pin_account.json.example"; do
    if [[ -f "$EX" ]]; then
      cp "$EX" "$PIN"
      echo "seeded $PIN from $EX (upstream needs real access_token + proxy)"
      break
    fi
  done
fi
if [[ ! -f "$PIN" ]]; then
  echo "missing $PIN (copy deploy/pin_account.json.example)"
  exit 2
fi

# minimal always keeps helper for backward compat; full+upstream can skip via UPSTREAM_ONLY=1
START_HELPER=0
if [[ "$LOCAL_MODE" == "minimal" ]]; then
  START_HELPER=1
elif [[ "$UPSTREAM_ONLY" != "1" ]]; then
  START_HELPER=1
fi

if [[ "$START_HELPER" == "1" ]]; then
  if [[ ! -f "$ROOT/helper/protocol_bridge.py" ]]; then
    echo "missing helper/protocol_bridge.py"
    exit 2
  fi
  if [[ ! -d "$GPTIMAGE_ROOT/services" ]]; then
    echo "GPTIMAGE_ROOT invalid: $GPTIMAGE_ROOT"
    exit 2
  fi
fi

if [[ "$START_HELPER" == "1" ]] && [[ -z "${HELPER_INTERNAL_TOKEN:-}" ]]; then
  if [[ -f "$ROOT/secrets/helper_token" ]]; then
    HELPER_INTERNAL_TOKEN=$(tr -d '\r\n' <"$ROOT/secrets/helper_token")
  else
    HELPER_INTERNAL_TOKEN=$(openssl rand -hex 32)
    printf '%s' "$HELPER_INTERNAL_TOKEN" >"$ROOT/secrets/helper_token"
    chmod 600 "$ROOT/secrets/helper_token"
    echo "generated secrets/helper_token"
  fi
  export HELPER_INTERNAL_TOKEN
fi

export GATEWAY_LISTEN="${GATEWAY_LISTEN:-127.0.0.1:8013}"
export HELPER_URL="${HELPER_URL:-http://127.0.0.1:19001}"
export PIN_ACCOUNT_FILE="$PIN"
export MVP_MIN_IMAGE_QUOTA="${MVP_MIN_IMAGE_QUOTA:-1}"
export IMAGE_GLOBAL_CONCURRENCY="${IMAGE_GLOBAL_CONCURRENCY:-3}"

GATEWAY_ENV=()
HELPER_ENV=(
  MVP_MIN_IMAGE_QUOTA="${MVP_MIN_IMAGE_QUOTA:-1}"
  MVP_IMAGE_POLL_TIMEOUT_SECS="${MVP_IMAGE_POLL_TIMEOUT_SECS:-120}"
  MVP_IMAGE_WALL_SECS="${MVP_IMAGE_WALL_SECS:-180}"
  MVP_IMAGE_SSE_POST_READY_SECS="${MVP_IMAGE_SSE_POST_READY_SECS:-90}"
)

if [[ "$LOCAL_MODE" == "full" ]]; then
  export DATA_PLANE="${DATA_PLANE:-upstream}"
  export AUTH_DISABLE=0
  export AUTH_MODE=jwt
  export IMAGE_ENABLED="${IMAGE_ENABLED:-1}"

  if [[ ! -f "$ROOT/secrets/jwt_secret" ]]; then
    openssl rand -hex 32 >"$ROOT/secrets/jwt_secret"
    chmod 600 "$ROOT/secrets/jwt_secret"
    echo "generated secrets/jwt_secret"
  fi
  export AUTH_JWT_SECRET=$(tr -d '\r\n' <"$ROOT/secrets/jwt_secret")
  export AUTH_BOOTSTRAP_ADMIN_USER="${AUTH_BOOTSTRAP_ADMIN_USER:-admin}"
  if [[ -z "${AUTH_BOOTSTRAP_ADMIN_PASSWORD:-}" ]]; then
    if [[ -f "$ROOT/secrets/local_admin_password" ]]; then
      AUTH_BOOTSTRAP_ADMIN_PASSWORD=$(tr -d '\r\n' <"$ROOT/secrets/local_admin_password")
    else
      AUTH_BOOTSTRAP_ADMIN_PASSWORD="local-admin-$(openssl rand -hex 4)"
      printf '%s' "$AUTH_BOOTSTRAP_ADMIN_PASSWORD" >"$ROOT/secrets/local_admin_password"
      chmod 600 "$ROOT/secrets/local_admin_password"
      echo "generated admin login -> secrets/local_admin_password"
    fi
  fi
  export AUTH_BOOTSTRAP_ADMIN_PASSWORD

  if need_web_build; then
    if [[ -f "$ROOT/web/package.json" ]]; then
      echo "==> npm install && npm run build (web/)"
      (cd "$ROOT/web" && npm install && npm run build)
    else
      echo "WARN: web/package.json missing — skipping UI build"
    fi
  fi
  if [[ -d "$WEB_OUT" ]]; then
    export GATEWAY_STATIC_DIR="$WEB_OUT"
    GATEWAY_ENV+=(GATEWAY_STATIC_DIR="$WEB_OUT")
  fi
  GATEWAY_ENV+=(
    AUTH_MODE=jwt
    AUTH_JWT_SECRET="$AUTH_JWT_SECRET"
    AUTH_BOOTSTRAP_ADMIN_USER="$AUTH_BOOTSTRAP_ADMIN_USER"
    AUTH_BOOTSTRAP_ADMIN_PASSWORD="$AUTH_BOOTSTRAP_ADMIN_PASSWORD"
  )
else
  export DATA_PLANE="${DATA_PLANE:-helper}"
  export AUTH_DISABLE="${AUTH_DISABLE:-1}"
  export IMAGE_ENABLED="${IMAGE_ENABLED:-0}"
fi

GATEWAY_ENV+=(
  GATEWAY_LISTEN="$GATEWAY_LISTEN"
  HELPER_URL="$HELPER_URL"
  PIN_ACCOUNT_FILE="$PIN"
  DATA_PLANE="$DATA_PLANE"
  IMAGE_ENABLED="$IMAGE_ENABLED"
  AUTH_DISABLE="$AUTH_DISABLE"
  IMAGE_GLOBAL_CONCURRENCY="$IMAGE_GLOBAL_CONCURRENCY"
  MVP_MIN_IMAGE_QUOTA="$MVP_MIN_IMAGE_QUOTA"
  RUST_LOG=gateway=info
)
if [[ -n "${HELPER_INTERNAL_TOKEN:-}" ]]; then
  GATEWAY_ENV+=(HELPER_INTERNAL_TOKEN="$HELPER_INTERNAL_TOKEN")
fi

pkill -f "$BIN" 2>/dev/null || true
if [[ "$START_HELPER" == "1" ]]; then
  pkill -f "protocol_bridge.py" 2>/dev/null || true
  docker rm -f "$HELPER_NAME" 2>/dev/null || true
fi
sleep 1

start_helper_host() {
  if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "hint: bash scripts/setup_wsl_helper_deps.sh"
    return 1
  fi
  (
    cd "$ROOT/helper"
    export GPTIMAGE_ROOT="$GPTIMAGE_ROOT"
    export HELPER_LISTEN=127.0.0.1:19001
    export HELPER_INTERNAL_TOKEN
    export PYTHONPATH="$ROOT/helper"
    for kv in "${HELPER_ENV[@]}"; do export "$kv"; done
    nohup python3 protocol_bridge.py >"$LOGDIR/helper.log" 2>&1 &
    echo $! >"$LOGDIR/helper.pid"
  )
}

if [[ "$START_HELPER" == "1" ]]; then
  if command -v docker >/dev/null 2>&1 && docker image inspect chatgpt2api:local >/dev/null 2>&1; then
    IMG=$(docker inspect chatgpt2api:local --format '{{.Id}}')
    docker run -d --name "$HELPER_NAME" --network host \
      -v "$GPTIMAGE_ROOT/api:/app/api:ro" \
      -v "$GPTIMAGE_ROOT/services:/app/services:ro" \
      -v "$GPTIMAGE_ROOT/utils:/app/utils:ro" \
      -v "$GPTIMAGE_ROOT/scripts:/app/scripts:ro" \
      -v "$GPTIMAGE_ROOT/config.json:/app/config.json:ro" \
      -v "$GPTIMAGE_ROOT/data:/app/data" \
      -v "$ROOT:/opt/gws" \
      -e GPTIMAGE_ROOT=/app \
      -e HELPER_LISTEN=127.0.0.1:19001 \
      -e HELPER_INTERNAL_TOKEN="$HELPER_INTERNAL_TOKEN" \
      -e PYTHONPATH=/opt/gws/helper \
      -e MVP_MIN_IMAGE_QUOTA="${MVP_MIN_IMAGE_QUOTA:-1}" \
      -e MVP_IMAGE_POLL_TIMEOUT_SECS="${MVP_IMAGE_POLL_TIMEOUT_SECS:-120}" \
      -e MVP_IMAGE_WALL_SECS="${MVP_IMAGE_WALL_SECS:-180}" \
      -e MVP_IMAGE_SSE_POST_READY_SECS="${MVP_IMAGE_SSE_POST_READY_SECS:-90}" \
      -w /opt/gws/helper \
      "$IMG" \
      /app/.venv/bin/python3 protocol_bridge.py
  else
    echo "docker/chatgpt2api:local not found — starting helper via host python"
    start_helper_host || exit 2
  fi
else
  echo "UPSTREAM_ONLY=1 / DATA_PLANE=upstream — skipping helper"
fi

nohup env "${GATEWAY_ENV[@]}" "$BIN" >"$LOGDIR/rust-gateway.log" 2>&1 &
echo $! >"$LOGDIR/rust-gateway.pid"

if [[ "$START_HELPER" == "1" ]]; then
  for _ in $(seq 1 40); do
    curl -fsS http://127.0.0.1:19001/health >/dev/null 2>&1 && break
    sleep 0.5
  done
fi
for _ in $(seq 1 40); do
  curl -fsS "http://${GATEWAY_LISTEN}/health" >/dev/null 2>&1 && break
  sleep 0.5
done

if [[ "$START_HELPER" == "1" ]]; then
  echo "=== helper ==="
  curl -fsS http://127.0.0.1:19001/health || true
  echo
fi
echo "=== gateway ==="
if ! curl -fsS "http://${GATEWAY_LISTEN}/health"; then
  echo
  echo "FATAL: gateway unhealthy — tail $LOGDIR/rust-gateway.log"
  tail -30 "$LOGDIR/rust-gateway.log" 2>/dev/null || true
  exit 1
fi
echo
echo "LOCAL_MODE=$LOCAL_MODE DATA_PLANE=$DATA_PLANE UPSTREAM_ONLY=$UPSTREAM_ONLY GATEWAY_LISTEN=$GATEWAY_LISTEN IMAGE_ENABLED=$IMAGE_ENABLED AUTH_DISABLE=$AUTH_DISABLE"
if [[ "$LOCAL_MODE" == "full" ]]; then
  echo "Web UI: http://${GATEWAY_LISTEN}/"
  echo "Admin:  ${AUTH_BOOTSTRAP_ADMIN_USER:-admin} / (see secrets/local_admin_password)"
  if [[ "$DATA_PLANE" == "upstream" ]]; then
    echo "Smoke:  bash scripts/local_smoke_upstream.sh"
    echo "        UPSTREAM_ONLY=1 bash scripts/local_bringup_wsl.sh  # gateway only, no helper"
  else
    echo "Smoke:  bash scripts/local_smoke_full.sh"
  fi
fi
