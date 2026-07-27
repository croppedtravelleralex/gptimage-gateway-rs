#!/usr/bin/env bash
# Bring up Rust gateway (:8013) + Python protocol helper (:19001).
# Does NOT touch production :8012.
#
# Prereq on panda:
#   /root/gptimage-gateway-rs/bin/gptimage-gateway-rs   (linux amd64, built off-box)
#   /root/gptimage-gateway-rs/helper/protocol_bridge.py
#   /root/gptimage-gateway-rs/secrets/pin_account.json
#   /root/gptimage/{api,services,utils,config.json,data} mounted RO into helper
#
# Secure by default: binds loopback with auth on. Exposing :8013 publicly or
# disabling auth now takes a deliberate opt-in, because the previous defaults
# put an unauthenticated account-pool API on the public internet.
set -euo pipefail

ROOT=/root/gptimage-gateway-rs
BIN="$ROOT/bin/gptimage-gateway-rs"
PIN="$ROOT/secrets/pin_account.json"
IMG=$(docker inspect chatgpt2api-local --format '{{.Config.Image}}')
HELPER_NAME=gptimage-gateway-rs-helper
FACE_NAME=gptimage-gateway-rs-mvp
LOGDIR="$ROOT/data/runlogs"
mkdir -p "$ROOT/bin" "$ROOT/secrets" "$LOGDIR"

if [[ ! -f "$BIN" ]]; then
  echo "missing linux binary: $BIN (build off-box; do not cargo build on panda)"
  exit 2
fi
chmod +x "$BIN" || true
if [[ ! -x "$BIN" ]]; then
  echo "binary not executable after chmod: $BIN"
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

# --- required secrets -------------------------------------------------------
# The helper refuses every /v1/internal/* call without this shared secret, so a
# missing value would leave the face up but unable to serve chat or image.
if [[ -z "${HELPER_INTERNAL_TOKEN:-}" ]]; then
  if [[ -f "$ROOT/secrets/helper_token" ]]; then
    HELPER_INTERNAL_TOKEN=$(tr -d '\r\n' <"$ROOT/secrets/helper_token")
  else
    echo "FATAL: HELPER_INTERNAL_TOKEN unset and $ROOT/secrets/helper_token missing."
    echo "  generate: openssl rand -hex 32 > $ROOT/secrets/helper_token && chmod 600 \$_"
    exit 2
  fi
fi
export HELPER_INTERNAL_TOKEN

AUTH_DISABLE="${AUTH_DISABLE:-0}"
GATEWAY_LISTEN="${GATEWAY_LISTEN:-127.0.0.1:8013}"

# Panda :8013 parity preset (docs/28-decisions-20260727.md §2).
if [[ "${PANDA_ALIGN:-}" == "1" ]]; then
  AUTH_DISABLE=1
  IMAGE_ENABLED=1
  GATEWAY_LISTEN=0.0.0.0:8013
  echo "PANDA_ALIGN=1: AUTH_DISABLE=1 IMAGE_ENABLED=1 GATEWAY_LISTEN=0.0.0.0:8013"
fi

if [[ "$AUTH_DISABLE" != "1" ]]; then
  if [[ -z "${AUTH_JWT_SECRET:-}" ]]; then
    if [[ -f "$ROOT/secrets/jwt_secret" ]]; then
      AUTH_JWT_SECRET=$(tr -d '\r\n' <"$ROOT/secrets/jwt_secret")
    else
      echo "FATAL: AUTH_JWT_SECRET unset and $ROOT/secrets/jwt_secret missing."
      echo "  generate: openssl rand -hex 32 > $ROOT/secrets/jwt_secret && chmod 600 \$_"
      exit 2
    fi
  fi
  export AUTH_JWT_SECRET
fi

# Refuse the one combination that puts an unauthenticated pool API on the wire,
# unless explicitly reproducing Panda (:8013) or opting in.
if [[ "$AUTH_DISABLE" == "1" && "$GATEWAY_LISTEN" != 127.0.0.1:* && "$GATEWAY_LISTEN" != localhost:* ]]; then
  if [[ "${PANDA_ALIGN:-}" != "1" && "${ALLOW_INSECURE_PUBLIC:-}" != "1" ]]; then
    echo "FATAL: AUTH_DISABLE=1 with non-loopback GATEWAY_LISTEN=$GATEWAY_LISTEN"
    echo "  That exposes the account pool with no authentication. Refusing."
    echo "  To reproduce Panda :8013: PANDA_ALIGN=1 bash $0"
    exit 2
  fi
  echo "WARNING: unauthenticated public bind (PANDA_ALIGN or ALLOW_INSECURE_PUBLIC)"
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
  -v /root/gptimage/data:/app/data \
  -v "$ROOT:/opt/gws" \
  -e GPTIMAGE_ROOT=/app \
  -e HELPER_LISTEN=127.0.0.1:19001 \
  -e HELPER_INTERNAL_TOKEN="$HELPER_INTERNAL_TOKEN" \
  -e MVP_MIN_IMAGE_QUOTA="${MVP_MIN_IMAGE_QUOTA:-1}" \
  -e MVP_IMAGE_POLL_TIMEOUT_SECS="${MVP_IMAGE_POLL_TIMEOUT_SECS:-120}" \
  -e MVP_IMAGE_WALL_SECS="${MVP_IMAGE_WALL_SECS:-180}" \
  -e MVP_IMAGE_SSE_POST_READY_SECS="${MVP_IMAGE_SSE_POST_READY_SECS:-90}" \
  -e PYTHONPATH=/opt/gws/helper \
  -w /opt/gws/helper \
  "$IMG" \
  /app/.venv/bin/python3 protocol_bridge.py

# 2) Rust face — OpenAI HTTP + image semaphore (loopback :8013 by default)
nohup env \
  GATEWAY_LISTEN="$GATEWAY_LISTEN" \
  HELPER_URL=http://127.0.0.1:19001 \
  HELPER_INTERNAL_TOKEN="$HELPER_INTERNAL_TOKEN" \
  PIN_ACCOUNT_FILE="$PIN" \
  MVP_MIN_IMAGE_QUOTA="${MVP_MIN_IMAGE_QUOTA:-1}" \
  IMAGE_GLOBAL_CONCURRENCY="${IMAGE_GLOBAL_CONCURRENCY:-3}" \
  IMAGE_ENABLED="${IMAGE_ENABLED:-0}" \
  AUTH_DISABLE="$AUTH_DISABLE" \
  ${AUTH_JWT_SECRET:+AUTH_JWT_SECRET="$AUTH_JWT_SECRET"} \
  ${AUTH_BOOTSTRAP_ADMIN_USER:+AUTH_BOOTSTRAP_ADMIN_USER="$AUTH_BOOTSTRAP_ADMIN_USER"} \
  ${AUTH_BOOTSTRAP_ADMIN_PASSWORD:+AUTH_BOOTSTRAP_ADMIN_PASSWORD="$AUTH_BOOTSTRAP_ADMIN_PASSWORD"} \
  ${GATEWAY_STATIC_DIR:+GATEWAY_STATIC_DIR="$GATEWAY_STATIC_DIR"} \
  ${GATEWAY_CORS_ORIGINS:+GATEWAY_CORS_ORIGINS="$GATEWAY_CORS_ORIGINS"} \
  RUST_LOG=gateway=info,tower_http=info \
  "$BIN" >"$LOGDIR/rust-gateway.log" 2>&1 &
echo $! >"$LOGDIR/rust-gateway.pid"

sleep 2
for i in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsS http://127.0.0.1:19001/health >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
echo "=== helper health ==="
curl -fsS http://127.0.0.1:19001/health | tee "$LOGDIR/helper-health-$(date +%Y%m%d-%H%M%S).json"
echo
echo "=== rust face health ==="
curl -fsS "http://${GATEWAY_LISTEN}/health" | tee "$LOGDIR/rust-health-$(date +%Y%m%d-%H%M%S).json"
echo
echo "Rust face up: $GATEWAY_LISTEN + helper :19001 (prod :8012 untouched)"
echo "  auth_disabled=$AUTH_DISABLE  image_enabled=${IMAGE_ENABLED:-0}"
