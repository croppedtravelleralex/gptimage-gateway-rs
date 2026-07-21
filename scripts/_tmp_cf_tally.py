#!/usr/bin/env python3
"""Tally CF/403 from mvp docker logs."""
from __future__ import annotations

import json
import re
import subprocess
from collections import Counter


def main() -> None:
    raw = subprocess.check_output(
        ["docker", "logs", "--since", "6h", "gptimage-gateway-rs-mvp"],
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
    )
    events = Counter()
    by_ctx = Counter()
    by_phase = Counter()
    by_proxy = Counter()
    by_account = Counter()
    status_codes = Counter()
    samples = []
    for line in raw.splitlines():
        i = line.find("{")
        if i < 0:
            continue
        try:
            o = json.loads(line[i:])
        except Exception:
            continue
        ev = str(o.get("event") or "")
        err = str(o.get("error") or o.get("detail") or o.get("message") or "")
        low = (ev + " " + err).lower()
        sc = o.get("status_code")
        is_cf = (
            "cloudflare" in low
            or "cf_edge" in low
            or "html challenge" in low
            or "upstream_403" in low
            or ev in {"image_cf_edge_retry", "bootstrap_soft_failed", "conversation_cf_edge_retry"}
        )
        is_4xx = False
        if sc is not None:
            try:
                is_4xx = 400 <= int(sc) < 500
            except Exception:
                pass
        if re.search(r"status=4\d\d", err):
            is_4xx = True
        if not (is_cf or is_4xx or "403" in low or o.get("error_type") == "UpstreamHTTPError"):
            continue
        events[ev or "no_event"] += 1
        if sc is not None:
            status_codes[str(sc)] += 1
        ctx = "unknown"
        if "chat_requirements_prepare" in err:
            ctx = "chat_requirements_prepare"
        elif "chat_requirements_finalize" in err:
            ctx = "chat_requirements_finalize"
        elif "/backend-api/f/conversation" in err or "conversation failed" in err:
            ctx = "conversation"
        elif "bootstrap" in err or ev == "bootstrap_soft_failed":
            ctx = "bootstrap"
        elif "quota" in err or "get_user_info" in err:
            ctx = "quota_or_me"
        by_ctx[ctx] += 1
        if o.get("failed_phase"):
            by_phase[str(o.get("failed_phase"))] += 1
        if o.get("node_hash"):
            by_proxy[str(o.get("node_hash"))] += 1
        if o.get("account_hash"):
            by_account[str(o.get("account_hash"))] += 1
        if len(samples) < 10 and (is_cf or is_4xx):
            samples.append(
                {
                    k: o.get(k)
                    for k in (
                        "event",
                        "status_code",
                        "attempt",
                        "failed_phase",
                        "error_type",
                        "account_hash",
                        "node_hash",
                        "reason",
                        "error",
                        "detail",
                    )
                    if o.get(k) is not None
                }
            )

    print("=== CF/4xx event counts (6h mvp) ===")
    for k, v in events.most_common(25):
        print(f"  {k}: {v}")
    print("=== status_code ===")
    for k, v in status_codes.most_common():
        print(f"  {k}: {v}")
    print("=== by context ===")
    for k, v in by_ctx.most_common():
        print(f"  {k}: {v}")
    print("=== by failed_phase ===")
    for k, v in by_phase.most_common():
        print(f"  {k}: {v}")
    print("=== top node_hash ===")
    for k, v in by_proxy.most_common(10):
        print(f"  {k}: {v}")
    print("=== top account_hash ===")
    for k, v in by_account.most_common(10):
        print(f"  {k}: {v}")
    print("=== samples ===")
    for s in samples:
        e = s.get("error") or s.get("detail") or ""
        if isinstance(e, str) and len(e) > 180:
            s = dict(s)
            s["error" if "error" in s else "detail"] = e[:180]
        print(s)


if __name__ == "__main__":
    main()
