#!/usr/bin/env python3
"""Export one pin account JSON from panda gptimage sqlite (desensitize printed fields).

Usage (on panda):
  docker exec chatgpt2api-local python3 - < scripts/export_pin_account.py
or copy into container with GPTIMAGE data path.

Env:
  PIN_EMAIL   preferred email; else first verified_ready with proxy
  OUT_PATH    default /tmp/pin_account.json
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys


def main() -> int:
    db = os.environ.get("ACCOUNTS_DB", "/app/data/accounts.db")
    prefer = (os.environ.get("PIN_EMAIL") or "").strip().lower()
    out = os.environ.get("OUT_PATH", "/tmp/pin_account.json")
    conn = sqlite3.connect(db)
    rows = list(conn.execute("select id, access_token, data from accounts"))
    conn.close()
    candidates = []
    for _id, token, data in rows:
        try:
            d = json.loads(data) if isinstance(data, str) else (data or {})
        except Exception:
            d = {}
        if not isinstance(d, dict):
            d = {}
        email = str(d.get("email") or "").strip()
        proxy = str(d.get("proxy") or "").strip()
        st = str(d.get("panda_receive_state") or "").lower()
        status = str(d.get("status") or "")
        if not email or not token or not proxy:
            continue
        if status in {"禁用", "异常"}:
            continue
        if st and st not in {"verified_ready", "verified", "local_verified"}:
            continue
        score = 0
        if prefer and email.lower() == prefer:
            score += 100
        if st == "verified_ready":
            score += 10
        candidates.append((score, {
            "email": email,
            "access_token": token,
            "device_id": str(d.get("oai-device-id") or (d.get("fp") or {}).get("oai-device-id") or ""),
            "proxy": proxy,
            "user_agent": str(d.get("user-agent") or (d.get("fp") or {}).get("user-agent") or ""),
        }))
    if not candidates:
        print("NO_CANDIDATE", file=sys.stderr)
        return 2
    candidates.sort(key=lambda x: -x[0])
    acc = candidates[0][1]
    with open(out, "w", encoding="utf-8") as f:
        json.dump(acc, f, ensure_ascii=False)
    print(json.dumps({
        "ok": True,
        "out": out,
        "email": acc["email"],
        "proxy_host": acc["proxy"].split("@")[-1].split(":")[0],
        "token_prefix": str(acc["access_token"])[:12] + "...",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
