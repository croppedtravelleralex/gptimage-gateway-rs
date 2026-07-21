#!/usr/bin/env bash
# Bring up Rust gateway (:8013) + Python protocol helper (:19001).
# Does NOT touch production :8012.
#
# Prereq on panda:
#   /root/gptimage-gateway-rs/bin/gptimage-gateway-rs   (linux amd64, built off-box)
#   /root/gptimage-gateway-rs/helper/protocol_bridge.py
#   /root/gptimage-gateway-rs/secrets/pin_account.json
#   /root/gptimage/{api,services,utils,config.json,data} mounted RO into helper
set -euo pipefail

ROOT=/root/gptimage-gateway-rs
BIN="$ROOT/bin/gptimage-gateway-rs"
PIN="$ROOT/secrets/pin_account.json"
IMG=$(docker inspect chatgpt2api-local --format '{{.Config.Image}}')
HELPER_NAME=gptimage-gateway-rs-helper
FACE_NAME=gptimage-gateway-rs-mvp
LOGDIR="$ROOT/data/runlogs"
mkdir -p "$ROOT/bin" "$ROOT/secrets" "$LOGDIR"

if [[ ! -x "$BIN" ]]; then
  echo "missing linux binary: $BIN (build off-box; do not cargo build on panda)"
  exit 2
fi
if [[ ! -f "$PIN" ]]; then
  echo "missing pin: $PIN"
  exit 2
fi
if [[ ! -f "$ROOT/helper/protocol_bridge.py" ]]; then
  echo "missing helper: $ROOT/helper/protocol_bridge.py"
  exit 2
fi

# Stop Python face (old MVP) and any prior helper/rust face.
docker rm -f "$FACE_NAME" "$HELPER_NAME" 2>/dev/null || true
pkill -f "$BIN" 2>/dev/null || true
sleep 1

# 1) Helper — curl_cffi / PoW / SSE (loopback :19001)
docker run -d --name "$HELPER_NAME" --network host \
  -v /root/gptimage/api:/app/api:ro \
  -v /root/gptimage/services:/app/services:ro \
  -v /root/gptimage/utils:/app/utils:ro \
  -v /root/gptimage/scripts:/app/scripts:ro \
  -v /root/gptimage/config.json:/app/config.json:ro \
  -v /root/gptimage/data:/app/data:ro \
  -v "$ROOT:/opt/gws" \
  -e GPTIMAGE_ROOT=/app \
  -e HELPER_LISTEN=127.0.0.1:19001 \
  -e MVP_MIN_IMAGE_QUOTA="${MVP_MIN_IMAGE_QUOTA:-1}" \
  -e PYTHONPATH=/opt/gws/helper \
  -w /opt/gws/helper \
  "$IMG" \
  /app/.venv/bin/python3 protocol_bridge.py

# 2) Rust face — OpenAI HTTP + image semaphore (public :8013)
nohup env \
  GATEWAY_LISTEN=0.0.0.0:8013 \
  HELPER_URL=http://127.0.0.1:19001 \
  PIN_ACCOUNT_FILE="$PIN" \
  MVP_MIN_IMAGE_QUOTA="${MVP_MIN_IMAGE_QUOTA:-1}" \
  IMAGE_GLOBAL_CONCURRENCY="${IMAGE_GLOBAL_CONCURRENCY:-3}" \
  RUST_LOG=gateway=info,tower_http=info \
  "$BIN" >"$LOGDIR/rust-gateway.log" 2>&1 &
echo $! >"$LOGDIR/rust-gateway.pid"

sleep 2
echo "=== helper health ==="
curl -fsS http://127.0.0.1:19001/health | tee "$LOGDIR/helper-health-$(date +%Y%m%d-%H%M%S).json"
echo
echo "=== rust face health ==="
curl -fsS http://127.0.0.1:8013/health | tee "$LOGDIR/rust-health-$(date +%Y%m%d-%H%M%S).json"
echo
echo "Rust MVP up: face :8013 + helper :19001 (prod :8012 untouched)"
