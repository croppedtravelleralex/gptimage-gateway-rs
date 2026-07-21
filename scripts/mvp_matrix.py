#!/usr/bin/env python3
"""MVP matrix against gateway :8013. Desensitized runlog only.

Always refreshes live quota before images; skips image cases when not imageable.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

BASE = os.environ.get("GATEWAY_BASE", "http://127.0.0.1:8013").rstrip("/")
AUTH = (os.environ.get("GATEWAY_AUTH") or "").strip()
N_TEXT = int(os.environ.get("N_TEXT", "5"))
N_IMAGE = int(os.environ.get("N_IMAGE", "5"))
# Healthy serial e2e is ~40-60s; client wall = target + small slack (not 100s+).
IMAGE_TIMEOUT = float(os.environ.get("IMAGE_TIMEOUT", "75"))
IMAGE_GAP_SECS = float(os.environ.get("IMAGE_GAP_SECS", "5"))
MIN_IMAGE_QUOTA = int(os.environ.get("MVP_MIN_IMAGE_QUOTA", "1"))
PIN_EMAIL = (os.environ.get("PIN_EMAIL") or "").strip()
OUT = Path(os.environ.get("OUT", f"data/runlogs/rust-mvp-{time.strftime('%Y%m%d-%H%M%S')}.json"))


def api(method: str, path: str, body: dict | None = None, timeout: float = 120.0):
    data = None if body is None else json.dumps(body).encode()
    h = {"Content-Type": "application/json"}
    if AUTH:
        h["Authorization"] = f"Bearer {AUTH}"
    if PIN_EMAIL:
        h["X-Preferred-Account-Email"] = PIN_EMAIL
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=h)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return resp.status, time.time() - t0, json.loads(raw), None
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8", "replace")
            j = json.loads(err_body)
        except Exception:
            j, err_body = None, str(e)[:500]
        return e.code, time.time() - t0, j, err_body[:500] if isinstance(err_body, str) else str(e)[:500]
    except Exception as e:
        return None, time.time() - t0, None, str(e)[:500]


def fault_of(j, err) -> str:
    if isinstance(j, dict):
        e = j.get("error") or {}
        if isinstance(e, dict) and e.get("fault"):
            return str(e["fault"])
    if err and "helper" in str(err).lower():
        return "self"
    return "upstream" if err or (isinstance(j, dict) and j.get("error")) else "ok"


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    health_s, _, health_j, health_err = api("GET", "/health", timeout=10)
    results = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "base": BASE,
        "pin_email": PIN_EMAIL or (health_j or {}).get("pin_email"),
        "health": {"status": health_s, "body": health_j, "err": health_err},
        "quota": None,
        "text": [],
        "image": [],
        "summary": {},
    }
    self_n = 0

    for i in range(N_TEXT):
        uid = uuid.uuid4().hex[:8]
        st, el, j, err = api(
            "POST",
            "/v1/chat/completions",
            {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": f"Reply with exactly: MVP-OK-{uid}"}],
                "stream": False,
            },
            timeout=90,
        )
        content = ""
        if isinstance(j, dict):
            try:
                content = j["choices"][0]["message"]["content"]
            except Exception:
                content = ""
        fault = fault_of(j, err) if st != 200 else "ok"
        if fault == "self":
            self_n += 1
        results["text"].append({
            "i": i,
            "status": st,
            "elapsed_s": round(el, 3),
            "ok": st == 200 and bool(str(content).strip()),
            "fault": fault,
            "content_len": len(content or ""),
            "content_head": (content or "")[:80],
            "err": err,
        })
        print(f"TEXT[{i}] status={st} ok={results['text'][-1]['ok']} el={el:.1f}s fault={fault}", flush=True)

    q_st, q_el, q_j, q_err = api("POST", "/v1/quota/refresh", {}, timeout=60)
    results["quota"] = {
        "status": q_st,
        "elapsed_s": round(q_el, 3),
        "body": q_j,
        "err": q_err,
    }
    imageable = bool(isinstance(q_j, dict) and q_j.get("imageable"))
    remaining = q_j.get("remaining") if isinstance(q_j, dict) else None
    print(
        f"QUOTA status={q_st} remaining={remaining} imageable={imageable} el={q_el:.1f}s min={MIN_IMAGE_QUOTA}",
        flush=True,
    )

    if N_IMAGE > 0 and not imageable:
        results["image"].append({
            "i": 0,
            "status": None,
            "elapsed_s": 0,
            "ok": False,
            "fault": "quota",
            "b64_len": 0,
            "err": f"skipped_images: not imageable remaining={remaining} body={q_j}",
            "skipped": True,
        })
        print("IMAGE skipped: quota gate (not imageable)", flush=True)
    else:
        for i in range(N_IMAGE):
            if i and IMAGE_GAP_SECS > 0:
                time.sleep(IMAGE_GAP_SECS)
            uid = uuid.uuid4().hex[:6]
            st, el, j, err = api(
                "POST",
                "/v1/images/generations",
                {
                    "model": "gpt-image-2",
                    "prompt": f"simple flat icon, solid color background, label MVP{uid}, no text clutter",
                    "n": 1,
                    "size": "1024x1024",
                    "response_format": "b64_json",
                },
                timeout=IMAGE_TIMEOUT,
            )
            b64_len = 0
            if isinstance(j, dict):
                try:
                    b64_len = len(j["data"][0].get("b64_json") or "")
                except Exception:
                    b64_len = 0
            fault = fault_of(j, err) if st != 200 else "ok"
            if fault == "self":
                self_n += 1
            results["image"].append({
                "i": i,
                "status": st,
                "elapsed_s": round(el, 3),
                "ok": st == 200 and b64_len > 1000,
                "fault": fault,
                "b64_len": b64_len,
                "err": err,
            })
            print(
                f"IMAGE[{i}] status={st} ok={results['image'][-1]['ok']} el={el:.1f}s b64={b64_len} fault={fault}",
                flush=True,
            )
            if fault == "quota":
                print("IMAGE stop: quota exhausted mid-run", flush=True)
                break

    t_ok = sum(1 for r in results["text"] if r["ok"])
    i_ok = sum(1 for r in results["image"] if r["ok"])
    t_self = sum(1 for r in results["text"] if r.get("fault") == "self")
    i_self = sum(1 for r in results["image"] if r.get("fault") == "self")
    i_up = sum(1 for r in results["image"] if r.get("fault") == "upstream")
    i_quota = sum(1 for r in results["image"] if r.get("fault") == "quota")
    skipped = any(r.get("skipped") for r in results["image"])
    # If images skipped due to quota, text-only can still pass when N_IMAGE was requested? No:
    # require imageable when N_IMAGE>0.
    min_image_ok = max(1, min(N_IMAGE, 3)) if N_IMAGE and not skipped else 0
    results["summary"] = {
        "text_ok": f"{t_ok}/{N_TEXT}",
        "image_ok": f"{i_ok}/{N_IMAGE}",
        "image_upstream": i_up,
        "image_quota_blocks": i_quota,
        "image_skipped_quota": skipped,
        "quota_remaining": remaining,
        "imageable": imageable,
        "self": self_n,
        "text_self": t_self,
        "image_self": i_self,
        "pass_gate": self_n == 0
        and t_self == 0
        and i_self == 0
        and t_ok >= max(1, N_TEXT - 1)
        and (N_IMAGE == 0 or (imageable and i_ok >= min_image_ok)),
    }
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results["summary"], ensure_ascii=False), flush=True)
    print(f"wrote {OUT}", flush=True)
    return 0 if results["summary"]["pass_gate"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
