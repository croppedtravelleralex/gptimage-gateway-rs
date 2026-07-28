#!/usr/bin/env bash
# DEPRECATED (2026-07-28): Panda :8013 MVP stack is retired.
#
# Strategy: complete implementation locally (WSL), then ship as an independent
# deployment — do NOT bring up :8013 on Panda during development.
#
# Local bringup:
#   bash scripts/local_bringup_wsl.sh
#
# One-shot upstream probe (optional, read-only on Panda):
#   see docs/30-phase1-probe-panda.md § 已验证结果
#
# Production :8012 is untouched.

echo "FATAL: panda_bringup_rust_face.sh is disabled (8013 MVP retired 2026-07-28)." >&2
echo "  Use: bash scripts/local_bringup_wsl.sh" >&2
echo "  See: HANDOFF.md § 部署策略" >&2
exit 1
