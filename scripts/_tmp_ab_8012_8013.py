#!/usr/bin/env python3
"""A/B: same 2 accounts concurrent on :8012 vs :8013."""
from __future__ import annotations

import concurrent.futures
import json
import time
import urllib.request
import uuid

EMAILS = [
    "qaflowwrg2ptcd05@proton.me",
    "qaflowxwy83tivv5@proton.me",
]


def call(base, method, path, body=None, timeout=80, email=None, auth=None):
    data = None if body is None else json.dumps(body).encode()
    h = {"Content-Type": "application/json"}
    if email:
        h["X-Preferred-Account-Email"] = email
    if auth:
        h["Authorization"] = f"Bearer {auth}"
    req = urllib.request.Request(base + path, data=data, method=method, headers=h)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, time.time() - t0, json.loads(r.read()), None
    except Exception as e:
        err = str(e)[:300]
        try:
            if hasattr(e, "read"):
                err = e.read().decode("utf-8", "replace")[:300]
        except Exception:
            pass
        return getattr(e, "code", None), time.time() - t0, None, err


def load_auth():
    try:
        cfg = json.loads(open("/root/gptimage/config.json", encoding="utf-8").read())
        return str(cfg.get("auth-key") or "").strip() or None
    except Exception:
        return None


def run_base(name, base, auth=None):
    print(f"=== {name} {base} ===", flush=True)
    # quota first
    for email in EMAILS:
        st, el, q, err = call(base, "POST", "/v1/quota/refresh", {}, timeout=45, email=email, auth=auth)
        # prod may not have /v1/quota/refresh — try skip
        if st == 404:
            print("  no quota endpoint, skip precheck", email, flush=True)
            continue
        rem = q.get("remaining") if isinstance(q, dict) else None
        print(f"  QUOTA {email} st={st} rem={rem} el={el:.1f} err={(err or '')[:80]}", flush=True)

    def one(i, email):
        time.sleep(i * 0.3)
        uid = uuid.uuid4().hex[:6]
        st, el, j, err = call(
            base,
            "POST",
            "/v1/images/generations",
            {
                "model": "gpt-image-2",
                "prompt": f"ab test lemon {uid}",
                "n": 1,
                "size": "1024x1024",
                "response_format": "b64_json",
            },
            timeout=90,
            email=email,
            auth=auth,
        )
        b64 = ""
        if isinstance(j, dict):
            try:
                b64 = ((j.get("data") or [{}])[0] or {}).get("b64_json") or ""
            except Exception:
                b64 = ""
        # prod async task shape?
        ok = st == 200 and len(b64) > 1000
        if not ok and isinstance(j, dict) and j.get("data"):
            # maybe url mode
            ok = st == 200
        print(
            f"  IMG[{i}] {email} st={st} ok={ok} el={el:.1f}s b64={len(b64)} err={(err or '')[:120]}",
            flush=True,
        )
        return ok, el, st

    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        futs = [ex.submit(one, i, e) for i, e in enumerate(EMAILS)]
        rows = [f.result() for f in futs]
    print(
        "SUMMARY",
        name,
        {
            "ok": f"{sum(1 for r in rows if r[0])}/2",
            "wall": round(time.time() - t0, 1),
            "elapsed": [round(r[1], 1) for r in rows],
            "status": [r[2] for r in rows],
        },
        flush=True,
    )
    return rows


def main():
    auth = load_auth()
    print("auth", bool(auth), flush=True)
    # MVP first (less likely to disturb prod long-running)
    mvp = run_base("MVP8013", "http://127.0.0.1:8013", auth=None)
    time.sleep(2)
    prod = run_base("PROD8012", "http://127.0.0.1:8012", auth=auth)
    print(
        "COMPARE",
        {
            "mvp_ok": sum(1 for r in mvp if r[0]),
            "prod_ok": sum(1 for r in prod if r[0]),
        },
        flush=True,
    )


if __name__ == "__main__":
    main()
