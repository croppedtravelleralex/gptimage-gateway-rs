#!/usr/bin/env python3
"""Low-concurrency image matrix. Quota-first. Default concurrency=2."""
from __future__ import annotations

import concurrent.futures
import json
import os
import sys
import time
import urllib.request
import uuid

BASE = os.environ.get("GATEWAY_BASE", "http://127.0.0.1:8013").rstrip("/")
N = int(os.environ.get("N_IMAGE", "4"))
CONC = int(os.environ.get("CONCURRENCY", "2"))
TO = float(os.environ.get("IMAGE_TIMEOUT", "80"))
STAGGER = float(os.environ.get("STAGGER_SECS", "1.5"))


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


def one_image(i: int) -> dict:
    if STAGGER > 0 and i > 0:
        time.sleep(STAGGER * (i % CONC))
    uid = uuid.uuid4().hex[:6]
    st, el, j, err = call(
        "POST",
        "/v1/images/generations",
        {
            "model": "gpt-image-2",
            "prompt": f"a blue mug on wood table, photo style {uid}",
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
    row = {
        "i": i,
        "status": st,
        "ok": ok,
        "elapsed_s": round(el, 1),
        "b64_len": len(b64),
        "err": (err or "")[:160],
    }
    print(
        f"IMG[{i}] status={st} ok={ok} el={el:.1f}s b64={len(b64)} err={(err or '')[:100]}",
        flush=True,
    )
    return row


def main() -> int:
    q_st, q_el, q, q_err = call("POST", "/v1/quota/refresh", {}, timeout=60)
    remaining = int((q or {}).get("remaining") or 0) if isinstance(q, dict) else 0
    imageable = bool(isinstance(q, dict) and q.get("imageable"))
    print(
        "QUOTA",
        {
            "http": q_st,
            "el": round(q_el, 2),
            "email": (q or {}).get("email") if isinstance(q, dict) else None,
            "remaining": remaining,
            "account_status": (q or {}).get("status") if isinstance(q, dict) else None,
            "imageable": imageable,
            "err": q_err,
        },
        flush=True,
    )
    if not imageable or remaining < N:
        print("SKIP_INSUFFICIENT_QUOTA need", N, "have", remaining, flush=True)
        return 2

    print(f"START N={N} CONCURRENCY={CONC} TIMEOUT={TO}", flush=True)
    t0 = time.time()
    rows: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONC) as pool:
        futs = [pool.submit(one_image, i) for i in range(N)]
        for fut in concurrent.futures.as_completed(futs):
            rows.append(fut.result())
    rows.sort(key=lambda r: r["i"])
    wall = time.time() - t0
    oks = [r for r in rows if r["ok"]]
    els = [r["elapsed_s"] for r in rows if r["ok"]]
    _, _, q2, _ = call("POST", "/v1/quota/refresh", {}, timeout=60)
    summary = {
        "ok": f"{len(oks)}/{N}",
        "concurrency": CONC,
        "wall_s": round(wall, 1),
        "elapsed": [r["elapsed_s"] for r in rows],
        "in_40_60": sum(1 for x in els if 40 <= x <= 60),
        "in_40_70": sum(1 for x in els if 40 <= x <= 70),
        "all_ok": len(oks) == N,
        "quota_after": q2.get("remaining") if isinstance(q2, dict) else None,
        "self": 0,
    }
    print("SUMMARY", summary, flush=True)
    out = os.environ.get("OUT")
    if out:
        Path = __import__("pathlib").Path
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(
            json.dumps({"quota_before": q, "rows": rows, "summary": summary}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print("wrote", out, flush=True)
    return 0 if len(oks) == N else 1


if __name__ == "__main__":
    raise SystemExit(main())
