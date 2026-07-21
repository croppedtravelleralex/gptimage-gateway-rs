#!/usr/bin/env python3
import json, subprocess, sys, time, urllib.request

q = json.loads(subprocess.check_output([
    "curl", "-sS", "-X", "POST", "http://127.0.0.1:8013/v1/quota/refresh",
    "-H", "Content-Type: application/json", "-d", "{}",
], text=True))
print("quota", {k: q.get(k) for k in ("email", "remaining", "status", "imageable")})
if not q.get("imageable") or int(q.get("remaining") or 0) < 1:
    print("SKIP_NO_QUOTA")
    sys.exit(2)

body = json.dumps({
    "model": "gpt-image-2",
    "prompt": "a small green plant in a clay pot, simple photo",
    "n": 1,
    "size": "1024x1024",
    "response_format": "b64_json",
}).encode()
req = urllib.request.Request(
    "http://127.0.0.1:8013/v1/images/generations",
    data=body,
    method="POST",
    headers={
        "Content-Type": "application/json",
        "X-Preferred-Account-Email": q.get("email") or "",
    },
)
t0 = time.time()
try:
    with urllib.request.urlopen(req, timeout=75) as resp:
        j = json.loads(resp.read())
        b64 = (((j.get("data") or [{}])[0] or {}).get("b64_json") or "")
        print(json.dumps({
            "status": resp.status,
            "elapsed_s": round(time.time() - t0, 3),
            "b64_len": len(b64),
            "ok": resp.status == 200 and len(b64) > 1000,
        }))
        code = 0 if resp.status == 200 and len(b64) > 1000 else 1
except Exception as e:
    print(json.dumps({"status": None, "elapsed_s": round(time.time() - t0, 3), "ok": False, "err": str(e)[:400]}))
    code = 1

subprocess.run(["python3", "/tmp/dump_phases.py"], check=False)
sys.exit(code)
