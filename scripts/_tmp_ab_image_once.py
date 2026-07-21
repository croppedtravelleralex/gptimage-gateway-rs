#!/usr/bin/env python3
"""A/B one image: prod :8012 vs rust :8013 same preferred email."""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

EMAIL = sys.argv[1] if len(sys.argv) > 1 else "qaflowgq5wyuxhe9@proton.me"
AUTH = "Bearer mvp-test"
PROMPT = f"tiny green triangle icon flat no text ab-{int(time.time())}"


def call(base: str, path: str, body=None, headers=None, timeout=120.0):
    url = base.rstrip("/") + path
    data = None if body is None else json.dumps(body).encode()
    h = {"Authorization": AUTH, "Content-Type": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method="POST" if body is not None else "GET")
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            el = time.perf_counter() - t0
            try:
                j = json.loads(raw.decode())
            except Exception:
                j = {"raw": raw[:200].decode(errors="replace")}
            return resp.status, el, j
    except urllib.error.HTTPError as e:
        el = time.perf_counter() - t0
        raw = e.read()
        try:
            j = json.loads(raw.decode())
        except Exception:
            j = {"raw": raw[:300].decode(errors="replace")}
        return e.code, el, j
    except Exception as e:
        return 0, time.perf_counter() - t0, {"error": f"{type(e).__name__}: {e}"}


def summarize(tag: str, st, el, j):
    b64 = 0
    msg = ""
    if isinstance(j, dict):
        data = j.get("data") or []
        if data and isinstance(data[0], dict):
            b64 = len(str(data[0].get("b64_json") or ""))
        err = j.get("error") or {}
        if isinstance(err, dict):
            msg = str(err.get("message") or err.get("code") or "")[:180]
        elif j.get("error"):
            msg = str(j.get("error"))[:180]
    print(json.dumps({
        "tag": tag,
        "status": st,
        "elapsed_s": round(el, 2),
        "ok": st == 200 and b64 > 1000,
        "b64_len": b64,
        "msg": msg,
    }, ensure_ascii=False))


def main():
    headers = {"X-Preferred-Account-Email": EMAIL}
    body = {"model": "gpt-image-2", "prompt": PROMPT, "n": 1, "size": "1024x1024"}
    print("email", EMAIL)
    # quota first on rust
    st, el, j = call("http://127.0.0.1:8013", "/v1/quota/refresh", body={}, headers=headers, timeout=60)
    print("quota8013", st, round(el, 2), j.get("imageable") if isinstance(j, dict) else j)
    summarize("8013", *call("http://127.0.0.1:8013", "/v1/images/generations", body=body, headers=headers))
    summarize("8012", *call("http://127.0.0.1:8012", "/v1/images/generations", body=body, headers=headers))


if __name__ == "__main__":
    main()
