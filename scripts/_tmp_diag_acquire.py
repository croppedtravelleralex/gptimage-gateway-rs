#!/usr/bin/env python3
"""Diagnose preferred-email image acquire on gptimage account_service."""
from __future__ import annotations

import json
import sys

from services.account_service import account_service


def main() -> int:
    emails = sys.argv[1:] or [
        "qaflowakjewai6ps@proton.me",
        "qaflowud630wbo2a@proton.me",
        "qaflowgq5wyuxhe9@proton.me",
    ]
    try:
        with account_service._image_slot_condition:
            inflight = dict(account_service._image_inflight)
            total = sum(int(v) for v in inflight.values())
    except Exception as e:
        inflight, total = {}, f"err:{e}"
    print(json.dumps({"inflight_total": total, "inflight_n": len(inflight)}, ensure_ascii=False))

    for e in emails:
        acc = None
        for a in account_service.list_accounts():
            if str(a.get("email") or "").lower() == e.lower():
                acc = a
                break
        if not acc:
            print(json.dumps({"email": e, "miss": True}, ensure_ascii=False))
            continue
        row = {
            "email": e,
            "quota": acc.get("quota"),
            "status": acc.get("status"),
            "sched": account_service._is_image_account_schedulable(acc),
            "avail": account_service._is_image_account_available(acc),
            "panda": acc.get("panda_receive_state"),
            "unknown": acc.get("image_quota_unknown"),
            "proxy": (str(acc.get("proxy") or "").split("@")[-1].split(":")[0]),
        }
        try:
            t = account_service.get_available_access_token(preferred_email=e)
            got = account_service.get_account(t) or {}
            row["acquire"] = "ok"
            row["got"] = got.get("email")
            account_service.release_image_slot(t)
        except Exception as ex:
            row["acquire"] = "fail"
            row["err"] = f"{type(ex).__name__}: {ex}"[:240]
        print(json.dumps(row, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
