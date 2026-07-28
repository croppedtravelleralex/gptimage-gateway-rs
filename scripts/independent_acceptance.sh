#!/usr/bin/env bash
# Independent deployment acceptance — upstream-only gateway on a dedicated port.
#
# Usage:
#   # After compose up on :8014 (or local bringup on :8013):
#   bash scripts/independent_acceptance.sh
#   GATEWAY_LISTEN=127.0.0.1:8014 IMAGE_ENABLED=1 bash scripts/independent_acceptance.sh
#   STREAM_ENABLED=1 IMAGE_ENABLED=1 bash scripts/independent_acceptance.sh
#
# Exit 0 when all mandatory checks pass. Image/stream legs accept 502 when pin token invalid.
set -euo pipefail

LISTEN="${GATEWAY_LISTEN:-127.0.0.1:8014}"
BASE="http://${LISTEN}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export GATEWAY_LISTEN="$LISTEN"
export IMAGE_ENABLED="${IMAGE_ENABLED:-1}"
export STREAM_ENABLED="${STREAM_ENABLED:-1}"

echo "==> independent acceptance on $BASE"
echo "    IMAGE_ENABLED=$IMAGE_ENABLED STREAM_ENABLED=$STREAM_ENABLED"
echo

bash "$ROOT/scripts/local_smoke_upstream.sh"

echo
echo "INDEPENDENT_ACCEPTANCE_OK listen=$LISTEN"
echo "  UI: open $BASE/showcase after login (LOCAL_MODE=full or compose with static UI)"
echo "  docs: docs/32-independent-deploy.md"
