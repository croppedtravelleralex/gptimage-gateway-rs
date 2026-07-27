#!/usr/bin/env python3
"""One-round image generation probe against the Rust gateway.

Read-only diagnostic: does not deploy, build, or mutate service config.

Usage:
    GATEWAY=http://127.0.0.1:8013 \
    GATEWAY_TOKEN=<jwt> \
    PROBE_EMAIL=<pool-address> \
    python3 scripts/rust_image_round.py

`PROBE_EMAIL` is optional and admin-only — the gateway refuses the
`X-Preferred-Account-Email` override for member tokens. Omit it to use the pin
account. Never hardcode a real address here; this file is tracked in git.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

GATEWAY = os.environ.get("GATEWAY", "http://127.0.0.1:8013")
TOKEN = os.environ.get("GATEWAY_TOKEN", "")
PROBE_EMAIL = os.environ.get("PROBE_EMAIL", "")
OUT_DIR = Path(os.environ.get("OUT_DIR", "data/runlogs/rust-image-round"))


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}


def _curl(*args: str) -> str:
    cmd = ["curl", "-fsS", *args]
    for key, value in _auth_headers().items():
        cmd += ["-H", f"{key}: {value}"]
    return subprocess.check_output(cmd, text=True)


def _mask(email: str) -> str:
    """Runlogs are committed, and pool addresses are credentials."""
    if "@" not in email:
        return ""
    local, _, domain = email.partition("@")
    return f"{local[:3]}***@{domain}"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    health = json.loads(_curl(f"{GATEWAY}/health"))
    if health.get("image_enabled") is False:
        print(json.dumps({"ok": False, "error": "image_enabled_false", "health": health}))
        return 2

    quota = json.loads(
        _curl(
            "-X",
            "POST",
            f"{GATEWAY}/v1/quota/refresh",
            "-H",
            "Content-Type: application/json",
            "-d",
            "{}",
        )
    )
    email = str(quota.get("email") or PROBE_EMAIL)
    if not quota.get("imageable") or int(quota.get("remaining") or 0) < 1:
        print(json.dumps({"ok": False, "error": "no_quota", "remaining": quota.get("remaining")}))
        return 2

    body = json.dumps(
        {
            "model": "gpt-image-2",
            "prompt": "a simple red circle on white background",
            "n": 1,
            "response_format": "b64_json",
        }
    ).encode("utf-8")
    headers = {"Content-Type": "application/json", **_auth_headers()}
    if PROBE_EMAIL:
        headers["X-Preferred-Account-Email"] = PROBE_EMAIL

    request = urllib.request.Request(
        f"{GATEWAY}/v1/images/generations", data=body, method="POST", headers=headers
    )
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=240) as resp:
            raw = resp.read()
            code = resp.status
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        code = exc.code
    elapsed = time.time() - started

    out_path = OUT_DIR / "v1_images_response.json"
    out_path.write_bytes(raw)
    try:
        data = json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        data = {"raw": raw.decode("utf-8", errors="replace")[:800]}

    b64_len = 0
    images = data.get("data") if isinstance(data, dict) else None
    if isinstance(images, list) and images:
        b64_len = len(str(images[0].get("b64_json") or ""))

    summary = {
        "ok": code == 200 and b64_len > 1000,
        "gateway": GATEWAY,
        "http_code": code,
        "elapsed_secs": round(elapsed, 2),
        "email": _mask(email),
        "b64_len": b64_len,
        "error": data.get("error") if isinstance(data, dict) else None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "evidence": str(out_path),
    }
    (OUT_DIR / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
