#!/usr/bin/env python3
"""Probe quota vs image path CF per unique-proxy account."""
from __future__ import annotations

import json
import time
import urllib.request


BASE = "http://127.0.0.1:8013"


def call(method, path, body=None, timeout=45, email=None):
    data = None if body is None else json.dumps(body).encode()
    h = {"Content-Type": "application/json"}
    if email:
        h["X-Preferred-Account-Email"] = email
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=h)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, time.time() - t0, json.loads(r.read()), None
    except Exception as e:
        err = str(e)[:400]
        body_j = None
        try:
            if hasattr(e, "read"):
                raw = e.read().decode("utf-8", "replace")
                err = raw[:400]
                try:
                    body_j = json.loads(raw)
                except Exception:
                    pass
        except Exception:
            pass
        return getattr(e, "code", None), time.time() - t0, body_j, err


def classify(err: str | None, body) -> str:
    text = (err or "") + " " + json.dumps(body or {}, ensure_ascii=False)
    low = text.lower()
    if "cloudflare" in low or "cf_edge" in low or "html challenge" in low:
        return "cf403"
    if "timeout" in low or "timed out" in low:
        return "timeout"
    if "status=401" in low or "token" in low and "invalid" in low:
        return "auth401"
    if "429" in low or "quota" in low:
        return "quota"
    if "status=4" in low or (isinstance(body, dict) and str((body.get("error") or {})).find("4") >= 0):
        return "http4xx"
    return "other"


def main() -> int:
    st, _, cand, err = call("GET", "/v1/accounts/candidates?limit=6", timeout=30)
    print("CANDIDATES", st, "n=", None if not cand else cand.get("count"), err)
    accounts = (cand or {}).get("accounts") or []
    rows = []
    for a in accounts[:5]:
        email = a["email"]
        host = a.get("proxy_host")
        q_st, q_el, q, q_err = call("POST", "/v1/quota/refresh", {}, timeout=35, email=email)
        q_cls = "ok" if q_st == 200 and isinstance(q, dict) and q.get("ok") else classify(q_err, q)
        # short image attempt — if CF, fails fast ~5-15s; don't wait full gen
        # Use a tiny prompt; still may succeed and cost quota — only if quota ok and imageable
        img_st = img_el = img_cls = None
        img_err = None
        if q_cls == "ok" and q.get("imageable"):
            img_st, img_el, img_body, img_err = call(
                "POST",
                "/v1/images/generations",
                {
                    "model": "gpt-image-2",
                    "prompt": "tiny red dot abstract",
                    "n": 1,
                    "size": "1024x1024",
                    "response_format": "b64_json",
                },
                timeout=25,  # fail-fast probe, not full e2e
                email=email,
            )
            if img_st == 200:
                img_cls = "ok"
            else:
                img_cls = classify(img_err, img_body)
        row = {
            "email": email,
            "proxy_host": host,
            "quota": {"status": q_st, "el": round(q_el, 2), "class": q_cls, "rem": None if not isinstance(q, dict) else q.get("remaining")},
            "image_probe": {"status": img_st, "el": None if img_el is None else round(img_el, 2), "class": img_cls, "err": (img_err or "")[:160]},
        }
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
        time.sleep(1.5)
    summary = {
        "quota_ok": sum(1 for r in rows if r["quota"]["class"] == "ok"),
        "image_ok": sum(1 for r in rows if r["image_probe"]["class"] == "ok"),
        "image_cf403": sum(1 for r in rows if r["image_probe"]["class"] == "cf403"),
        "image_timeout": sum(1 for r in rows if r["image_probe"]["class"] == "timeout"),
        "n": len(rows),
    }
    print("SUMMARY", summary, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
