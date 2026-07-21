#!/usr/bin/env python3
"""Multi-account concurrent image matrix for :8013.

Picks unique-proxy imageable accounts via /v1/accounts/candidates + live quota,
then runs CONCURRENCY parallel images each bound to a different email header.
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import sys
import time
import urllib.request
import uuid
from pathlib import Path

BASE = os.environ.get("GATEWAY_BASE", "http://127.0.0.1:8013").rstrip("/")
N = int(os.environ.get("N_IMAGE", "4"))
CONC = int(os.environ.get("CONCURRENCY", "2"))
TO = float(os.environ.get("IMAGE_TIMEOUT", "80"))
STAGGER = float(os.environ.get("STAGGER_SECS", "0.5"))
MIN_REMAINING = int(os.environ.get("MVP_MIN_IMAGE_QUOTA", "1"))
OUT = Path(os.environ.get("OUT", f"data/runlogs/rust-mvp-multi-{time.strftime('%Y%m%d-%H%M%S')}.json"))


def call(method: str, path: str, body=None, timeout: float = 60.0, email: str | None = None):
    data = None if body is None else json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    if email:
        headers["X-Preferred-Account-Email"] = email
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, time.time() - t0, json.loads(resp.read()), None
    except Exception as e:
        st = getattr(e, "code", None)
        err = str(e)[:500]
        try:
            if hasattr(e, "read"):
                err = e.read().decode("utf-8", "replace")[:500]
        except Exception:
            pass
        return st, time.time() - t0, None, err


def pick_accounts(need: int) -> list[dict]:
    st, el, j, err = call("GET", "/v1/accounts/candidates?limit=40", timeout=30)
    if st != 200 or not isinstance(j, dict):
        raise RuntimeError(f"candidates failed status={st} err={err}")
    cands = list(j.get("accounts") or [])
    print(f"CANDIDATES http={st} el={el:.1f}s n={len(cands)}", flush=True)
    picked: list[dict] = []
    for c in cands:
        email = str(c.get("email") or "").strip()
        if not email:
            continue
        q_st, q_el, q, q_err = call("POST", "/v1/quota/refresh", {}, timeout=60, email=email)
        row = {
            "email": email,
            "proxy_host": c.get("proxy_host"),
            "quota_http": q_st,
            "quota_el": round(q_el, 2),
            "remaining": q.get("remaining") if isinstance(q, dict) else None,
            "imageable": bool(isinstance(q, dict) and q.get("imageable")),
            "status": q.get("status") if isinstance(q, dict) else None,
            "err": (q_err or "")[:160],
        }
        print(
            f"  QUOTA {email} host={row['proxy_host']} rem={row['remaining']} "
            f"imageable={row['imageable']} status={row['status']} el={q_el:.1f}s",
            flush=True,
        )
        if row["imageable"] and int(row["remaining"] or 0) >= MIN_REMAINING:
            picked.append(row)
        if len(picked) >= need:
            break
    return picked


def one_image(i: int, email: str, proxy_host: str) -> dict:
    if STAGGER > 0 and i > 0:
        time.sleep(STAGGER * (i % max(1, CONC)))
    uid = uuid.uuid4().hex[:6]
    st, el, j, err = call(
        "POST",
        "/v1/images/generations",
        {
            "model": "gpt-image-2",
            "prompt": f"a yellow lemon on marble, photo {uid}",
            "n": 1,
            "size": "1024x1024",
            "response_format": "b64_json",
        },
        timeout=TO,
        email=email,
    )
    b64 = ""
    if isinstance(j, dict):
        try:
            b64 = ((j.get("data") or [{}])[0] or {}).get("b64_json") or ""
        except Exception:
            b64 = ""
    ok = st == 200 and len(b64) > 1000
    fault = "ok"
    if not ok:
        fault = "upstream"
        if isinstance(j, dict):
            e = j.get("error") or {}
            if isinstance(e, dict) and e.get("fault"):
                fault = str(e["fault"])
        elif err and "pin_mismatch" in err:
            fault = "self"
    row = {
        "i": i,
        "email": email,
        "proxy_host": proxy_host,
        "status": st,
        "ok": ok,
        "elapsed_s": round(el, 1),
        "b64_len": len(b64),
        "fault": fault,
        "err": (err or "")[:200],
    }
    print(
        f"IMG[{i}] email={email} host={proxy_host} status={st} ok={ok} "
        f"el={el:.1f}s b64={len(b64)} fault={fault}",
        flush=True,
    )
    return row


def main() -> int:
    health_st, _, health, health_err = call("GET", "/health", timeout=10)
    print("HEALTH", {"status": health_st, "body": health, "err": health_err}, flush=True)
    if not isinstance(health, dict) or not health.get("multi_account"):
        print("FACE_NOT_MULTI_ACCOUNT — deploy openai_face.py first", flush=True)
        return 3

    accounts = pick_accounts(N)
    if len(accounts) < N:
        print(f"SKIP_NOT_ENOUGH_ACCOUNTS need={N} got={len(accounts)}", flush=True)
        return 2

    print(f"START N={N} CONCURRENCY={CONC} accounts={[a['email'] for a in accounts]}", flush=True)
    t0 = time.time()
    rows: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONC) as pool:
        futs = [
            pool.submit(one_image, i, accounts[i]["email"], str(accounts[i].get("proxy_host") or ""))
            for i in range(N)
        ]
        for fut in concurrent.futures.as_completed(futs):
            rows.append(fut.result())
    rows.sort(key=lambda r: r["i"])
    wall = time.time() - t0
    oks = [r for r in rows if r["ok"]]
    self_n = sum(1 for r in rows if r.get("fault") == "self")
    hosts = {r.get("proxy_host") for r in rows}
    summary = {
        "ok": f"{len(oks)}/{N}",
        "concurrency": CONC,
        "wall_s": round(wall, 1),
        "elapsed": [r["elapsed_s"] for r in rows],
        "unique_proxy_hosts": len(hosts),
        "in_40_60": sum(1 for r in oks if 40 <= r["elapsed_s"] <= 60),
        "in_30_70": sum(1 for r in oks if 30 <= r["elapsed_s"] <= 70),
        "all_ok": len(oks) == N,
        "self": self_n,
        "pass_gate": len(oks) == N and self_n == 0,
        "accounts": [a["email"] for a in accounts],
    }
    print("SUMMARY", summary, flush=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {"health": health, "accounts": accounts, "rows": rows, "summary": summary},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print("wrote", OUT, flush=True)
    return 0 if summary["pass_gate"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
