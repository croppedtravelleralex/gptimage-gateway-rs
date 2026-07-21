#!/usr/bin/env python3
"""Conc=1 and conc=3 image timing matrix against Rust :8013.

Target: each image 40–60s; conc=3 wall ≈ single-image window (parallel).
Quota-first; unique-proxy preferred emails.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8013"
AUTH = "Bearer mvp-test"


def call(
    method: str,
    path: str,
    body: dict | None = None,
    headers: dict | None = None,
    timeout: float = 180.0,
) -> tuple[int, float, Any, str]:
    url = BASE.rstrip("/") + path
    data = None if body is None else json.dumps(body).encode()
    h = {"Authorization": AUTH, "Content-Type": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            elapsed = time.perf_counter() - t0
            try:
                return resp.status, elapsed, json.loads(raw.decode()), ""
            except Exception:
                return resp.status, elapsed, raw[:200], "non_json"
    except urllib.error.HTTPError as e:
        elapsed = time.perf_counter() - t0
        raw = e.read()
        try:
            j = json.loads(raw.decode())
        except Exception:
            j = {"raw": raw[:400].decode(errors="replace")}
        return e.code, elapsed, j, "http_error"
    except Exception as e:
        return 0, time.perf_counter() - t0, None, f"{type(e).__name__}: {e}"


def pick_accounts(n: int) -> list[str]:
    st, _, j, err = call("GET", "/v1/accounts/candidates?limit=40", timeout=30)
    if st != 200 or not isinstance(j, dict):
        raise RuntimeError(f"candidates failed status={st} err={err} body={j}")
    emails: list[str] = []
    for a in j.get("accounts") or []:
        email = str(a.get("email") or "").strip()
        if not email:
            continue
        qst, qel, qj, _ = call(
            "POST",
            "/v1/quota/refresh",
            body={},
            headers={"X-Preferred-Account-Email": email},
            timeout=60,
        )
        imageable = isinstance(qj, dict) and qj.get("imageable") is True
        rem = (qj or {}).get("remaining") if isinstance(qj, dict) else None
        print(f"  quota {email}: status={qst} imageable={imageable} remaining={rem} {qel:.1f}s")
        if imageable:
            emails.append(email)
        if len(emails) >= n:
            break
    if len(emails) < n:
        raise RuntimeError(f"need {n} imageable unique-proxy accounts, got {len(emails)}: {emails}")
    return emails


def one_image(email: str, tag: str) -> dict:
    prompt = f"tiny red circle icon, flat, no text, tag={tag}"
    st, el, j, err = call(
        "POST",
        "/v1/images/generations",
        body={"model": "gpt-image-2", "prompt": prompt, "n": 1, "size": "1024x1024"},
        headers={"X-Preferred-Account-Email": email},
        timeout=180,
    )
    b64_len = 0
    fault = None
    if isinstance(j, dict):
        data = j.get("data") or []
        if data and isinstance(data[0], dict):
            b64_len = len(str(data[0].get("b64_json") or ""))
            err_obj = j.get("error") or {}
        if isinstance(err_obj, dict):
            fault = err_obj.get("fault") or err_obj.get("code")
            if err_obj.get("message"):
                err = str(err_obj.get("message"))[:240]
    ok = st == 200 and b64_len > 1000
    return {
        "tag": tag,
        "email": email,
        "ok": ok,
        "status": st,
        "elapsed_s": round(el, 2),
        "b64_len": b64_len,
        "fault": fault,
        "err": err[:200] if err else "",
        "in_target": ok and 40.0 <= el <= 60.0,
    }


def run_serial(emails: list[str]) -> list[dict]:
    out = []
    for i, email in enumerate(emails, 1):
        r = one_image(email, f"c1-{i}")
        print(json.dumps(r, ensure_ascii=False))
        out.append(r)
    return out


def run_parallel(emails: list[str]) -> tuple[list[dict], float]:
    t0 = time.perf_counter()
    with cf.ThreadPoolExecutor(max_workers=len(emails)) as ex:
        futs = [ex.submit(one_image, email, f"c3-{i}") for i, email in enumerate(emails, 1)]
        out = [f.result() for f in futs]
    wall = time.perf_counter() - t0
    for r in out:
        print(json.dumps(r, ensure_ascii=False))
    print(json.dumps({"wall_s": round(wall, 2), "n": len(out)}, ensure_ascii=False))
    return out, wall


def main() -> int:
    print("=== health ===")
    st, el, j, err = call("GET", "/health", timeout=10)
    print(json.dumps({"status": st, "elapsed": round(el, 2), "body": j, "err": err}, ensure_ascii=False))
    if st != 200 or not isinstance(j, dict) or j.get("runtime") != "rust":
        print("FAIL: expected runtime=rust on :8013")
        return 2

    print("=== pick 3 imageable accounts ===")
    emails = pick_accounts(3)
    print("emails:", emails)

    print("=== conc=1 (3 serial) ===")
    c1 = run_serial(emails)
    print("=== conc=3 (parallel) ===")
    c3, wall = run_parallel(emails)

    def summary(rows: list[dict], wall_s: float | None = None) -> dict:
        oks = [r for r in rows if r["ok"]]
        return {
            "ok_n": len(oks),
            "n": len(rows),
            "self_faults": sum(1 for r in rows if r.get("fault") == "self"),
            "elapsed_s": [r["elapsed_s"] for r in rows],
            "in_target_40_60": sum(1 for r in rows if r.get("in_target")),
            "wall_s": wall_s,
        }

    report = {
        "base": BASE,
        "conc1": summary(c1),
        "conc3": summary(c3, wall),
        "pass_conc1": all(r["ok"] and r["in_target"] for r in c1),
        "pass_conc3": (
            all(r["ok"] and r["in_target"] for r in c3)
            and wall <= 70.0  # parallel wall should stay near single-image window
        ),
    }
    print("=== REPORT ===")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["pass_conc1"] and report["pass_conc3"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
