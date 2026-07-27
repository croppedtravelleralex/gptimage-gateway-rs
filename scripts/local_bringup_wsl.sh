#!/usr/bin/env bash
# Local dev bringup (WSL/Linux): helper :19001 + Rust gateway :8013.
# Primary goal: replicate the implemented stack on loopback before panda deploy.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

GPTIMAGE_ROOT="${GPTIMAGE_ROOT:-$ROOT/../gptimage}"
BIN="${BIN:-$ROOT/target/release/gptimage-gateway-rs}"
PIN="${PIN_ACCOUNT_FILE:-$ROOT/secrets/pin_account.json}"
HELPER_NAME=gptimage-local-helper
LOGDIR="$ROOT/data/runlogs"
mkdir -p "$LOGDIR" "$ROOT/secrets"

if [[ ! -x "$BIN" ]]; then
  echo "missing binary: $BIN (run: cargo build --release -p gateway)"
  exit 2
fi
if [[ ! -f "$PIN" ]]; then
  if [[ -f "$ROOT/secrets/pin_account.json.example" ]]; then
    cp "$ROOT/secrets/pin_account.json.example" "$PIN"
    echo "seeded $PIN from example (chat upstream will fail without real token)"
  else
    echo "missing $PIN"
    exit 2
  fi
fi
if [[ ! -f "$ROOT/helper/protocol_bridge.py" ]]; then
  echo "missing helper/protocol_bridge.py"
  exit 2
fi
if [[ ! -d "$GPTIMAGE_ROOT/services" ]]; then
  echo "GPTIMAGE_ROOT invalid: $GPTIMAGE_ROOT"
  exit 2
fi

if [[ -z "${HELPER_INTERNAL_TOKEN:-}" ]]; then
  if [[ -f "$ROOT/secrets/helper_token" ]]; then
    HELPER_INTERNAL_TOKEN=$(tr -d '\r\n' <"$ROOT/secrets/helper_token")
  else
    HELPER_INTERNAL_TOKEN=$(openssl rand -hex 32)
    printf '%s' "$HELPER_INTERNAL_TOKEN" >"$ROOT/secrets/helper_token"
    chmod 600 "$ROOT/secrets/helper_token"
    echo "generated secrets/helper_token"
  fi
fi
export HELPER_INTERNAL_TOKEN

# Panda :8013 parity on loopback (no public bind).
export AUTH_DISABLE="${AUTH_DISABLE:-1}"
export IMAGE_ENABLED="${IMAGE_ENABLED:-0}"
export GATEWAY_LISTEN="${GATEWAY_LISTEN:-127.0.0.1:8013}"
export HELPER_URL="${HELPER_URL:-http://127.0.0.1:19001}"
export PIN_ACCOUNT_FILE="$PIN"

pkill -f "$BIN" 2>/dev/null || true
pkill -f "protocol_bridge.py" 2>/dev/null || true
sleep 1

if command -v docker >/dev/null 2>&1 && docker image inspect chatgpt2api:local >/dev/null 2>&1; then
  IMG=$(docker inspect chatgpt2api:local --format '{{.Id}}')
  docker rm -f "$HELPER_NAME" 2>/dev/null || true
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
    -w /opt/gws/helper \
    "$IMG" \
    /app/.venv/bin/python3 protocol_bridge.py
else
  echo "docker/chatgpt2api:local not found — starting helper via host python"
  if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "hint: pip3 install --break-system-packages fastapi uvicorn pillow curl-cffi (see gptimage/pyproject.toml)"
  fi
  (
    cd "$ROOT/helper"
    export GPTIMAGE_ROOT="$GPTIMAGE_ROOT"
    export HELPER_LISTEN=127.0.0.1:19001
    export HELPER_INTERNAL_TOKEN
    export PYTHONPATH="$ROOT/helper"
    nohup python3 protocol_bridge.py >"$LOGDIR/helper.log" 2>&1 &
    echo $! >"$LOGDIR/helper.pid"
  )
fi

nohup env \
  GATEWAY_LISTEN="$GATEWAY_LISTEN" \
  HELPER_URL="$HELPER_URL" \
  HELPER_INTERNAL_TOKEN="$HELPER_INTERNAL_TOKEN" \
  PIN_ACCOUNT_FILE="$PIN" \
  IMAGE_ENABLED="$IMAGE_ENABLED" \
  AUTH_DISABLE="$AUTH_DISABLE" \
  RUST_LOG=gateway=info \
  "$BIN" >"$LOGDIR/rust-gateway.log" 2>&1 &
echo $! >"$LOGDIR/rust-gateway.pid"

for _ in $(seq 1 20); do
  curl -fsS http://127.0.0.1:19001/health >/dev/null 2>&1 && break
  sleep 0.5
done

echo "=== helper ==="
curl -fsS http://127.0.0.1:19001/health || true
echo
echo "=== gateway ==="
curl -fsS "http://${GATEWAY_LISTEN}/health" || true
echo
echo "local stack: GATEWAY_LISTEN=$GATEWAY_LISTEN helper :19001 AUTH_DISABLE=$AUTH_DISABLE"
