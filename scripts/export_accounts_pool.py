#!/usr/bin/env python3
"""Export eligible accounts from gptimage sqlite to ACCOUNTS_FILE JSON array.

Usage (on panda after copying accounts.db):
  ACCOUNTS_DB=/root/gptimage-gateway-rs/data/gptimage/accounts.db \
  OUT_PATH=/root/gptimage-gateway-rs/secrets/accounts_pool.json \
  python3 scripts/export_accounts_pool.py

Env:
  ACCOUNTS_DB   path to accounts.db (default /app/data/accounts.db)
  OUT_PATH      output JSON array (default /tmp/accounts_pool.json)
  LIMIT         max accounts (default 50)
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys


def main() -> int:
    db = os.environ.get("ACCOUNTS_DB", "/app/data/accounts.db")
    out = os.environ.get("OUT_PATH", "/tmp/accounts_pool.json")
    limit = int(os.environ.get("LIMIT", "50"))

    conn = sqlite3.connect(db)
    rows = list(conn.execute("select id, access_token, data from accounts"))
    conn.close()

    candidates: list[tuple[int, dict]] = []
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
        if st and st not in {"verified_ready", "verified"}:
            continue
        score = 10 if st == "verified_ready" else 0
        candidates.append((score, {
            "email": email,
            "access_token": token,
            "device_id": str(
                d.get("oai-device-id") or (d.get("fp") or {}).get("oai-device-id") or ""
            ),
            "proxy": proxy,
            "user_agent": str(
                d.get("user-agent") or (d.get("fp") or {}).get("user-agent") or ""
            ),
        }))

    if not candidates:
        print("NO_CANDIDATES", file=sys.stderr)
        return 2

    candidates.sort(key=lambda x: (-x[0], x[1]["email"]))
    pool = [item for _, item in candidates[:limit]]
    with open(out, "w", encoding="utf-8") as f:
        json.dump(pool, f, ensure_ascii=False, indent=2)

    print(json.dumps({
        "ok": True,
        "out": out,
        "count": len(pool),
        "emails": [a["email"] for a in pool[:5]],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
