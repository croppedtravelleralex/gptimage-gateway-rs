#!/usr/bin/env python3
import json, time, urllib.request, uuid

BASE = "http://127.0.0.1:8013"
EMAILS = ["ivetterock54353@outlook.com", "qaflowxwy83tivv5@proton.me"]


def call(method, path, body=None, timeout=80, email=None):
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
        err = str(e)[:240]
        try:
            if hasattr(e, "read"):
                err = e.read().decode("utf-8", "replace")[:240]
        except Exception:
            pass
        return getattr(e, "code", None), time.time() - t0, None, err


def main() -> int:
    rows = []
    for i, email in enumerate(EMAILS):
        _, el, q, _ = call("POST", "/v1/quota/refresh", {}, timeout=60, email=email)
        print(
            "QUOTA",
            email,
            {k: (q or {}).get(k) for k in ("remaining", "imageable", "status", "proxy_host")},
            "el",
            round(el, 2),
            flush=True,
        )
        if not q or not q.get("imageable"):
            return 2
        uid = uuid.uuid4().hex[:6]
        st, el, j, err = call(
            "POST",
            "/v1/images/generations",
            {
                "model": "gpt-image-2",
                "prompt": f"serial multi {uid}",
                "n": 1,
                "size": "1024x1024",
                "response_format": "b64_json",
            },
            timeout=80,
            email=email,
        )
        b64 = ""
        if isinstance(j, dict):
            try:
                b64 = ((j.get("data") or [{}])[0] or {}).get("b64_json") or ""
            except Exception:
                b64 = ""
        ok = st == 200 and len(b64) > 1000
        print(
            f"SERIAL[{i}] {email} status={st} ok={ok} el={el:.1f}s b64={len(b64)} err={(err or '')[:100]}",
            flush=True,
        )
        rows.append(ok)
        time.sleep(3)
    print("SUMMARY", f"{sum(rows)}/{len(rows)}", flush=True)
    return 0 if all(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
