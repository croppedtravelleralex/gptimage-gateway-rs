#!/usr/bin/env python3
"""Serial image stability before concurrent matrix. Quota-first."""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import uuid

BASE = os.environ.get("GATEWAY_BASE", "http://127.0.0.1:8013").rstrip("/")
N = int(os.environ.get("N_IMAGE", "3"))
TO = float(os.environ.get("IMAGE_TIMEOUT", "75"))
GAP = float(os.environ.get("IMAGE_GAP_SECS", "3"))


def call(method: str, path: str, body=None, timeout: float = 60.0):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, time.time() - t0, json.loads(resp.read()), None
    except Exception as e:
        st = getattr(e, "code", None)
        err = str(e)[:400]
        try:
            if hasattr(e, "read"):
                err = e.read().decode("utf-8", "replace")[:400]
        except Exception:
            pass
        return st, time.time() - t0, None, err


def main() -> int:
    q_st, q_el, q, q_err = call("POST", "/v1/quota/refresh", {}, timeout=60)
    qinfo = {
        "status": q_st,
        "el": round(q_el, 2),
        "err": q_err,
    }
    if isinstance(q, dict):
        for k in ("email", "remaining", "status", "imageable"):
            qinfo[k] = q.get(k)
    print("QUOTA", qinfo, flush=True)
    remaining = int((q or {}).get("remaining") or 0) if isinstance(q, dict) else 0
    if not isinstance(q, dict) or not q.get("imageable") or remaining < N:
        print("SKIP_INSUFFICIENT_QUOTA need", N, "have", remaining, flush=True)
        return 2

    oks = []
    els = []
    for i in range(N):
        uid = uuid.uuid4().hex[:6]
        st, el, j, err = call(
            "POST",
            "/v1/images/generations",
            {
                "model": "gpt-image-2",
                "prompt": f"a red apple on white plate, photo style {uid}",
                "n": 1,
                "size": "1024x1024",
                "response_format": "b64_json",
            },
            timeout=TO,
        )
        b64 = ""
        if isinstance(j, dict):
            try:
                b64 = ((j.get("data") or [{}])[0] or {}).get("b64_json") or ""
            except Exception:
                b64 = ""
        ok = st == 200 and len(b64) > 1000
        oks.append(ok)
        els.append(el)
        print(
            f"IMG[{i}] status={st} ok={ok} el={el:.1f}s b64={len(b64)} err={(err or '')[:120]}",
            flush=True,
        )
        if i + 1 < N and GAP > 0:
            time.sleep(GAP)

    _, _, q2, _ = call("POST", "/v1/quota/refresh", {}, timeout=60)
    summary = {
        "ok": f"{sum(oks)}/{N}",
        "elapsed": [round(x, 1) for x in els],
        "in_40_60": sum(1 for x, o in zip(els, oks) if o and 40 <= x <= 60),
        "in_40_70": sum(1 for x, o in zip(els, oks) if o and 40 <= x <= 70),
        "all_ok": all(oks),
        "quota_after": q2.get("remaining") if isinstance(q2, dict) else None,
    }
    print("SUMMARY", summary, flush=True)
    return 0 if all(oks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
