#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
import base64, io, tarfile
from pathlib import Path
d = base64.b64decode(open("/tmp/mvp.b64").read())
tarfile.open(fileobj=io.BytesIO(d), mode="r:gz").extractall("/root/gptimage-gateway-rs")
t = Path("/root/gptimage-gateway-rs/helper/protocol_bridge.py").read_text(encoding="utf-8")
assert "_apply_mvp_sse_post_ready" in t
print("synced ok")
PY
docker restart gptimage-gateway-rs-mvp
sleep 6
curl -fsS http://127.0.0.1:8013/health; echo
echo "=== QUOTA FIRST ==="
curl -sS -X POST http://127.0.0.1:8013/v1/quota/refresh -H "Content-Type: application/json" -d "{}"
echo
# only proceed if imageable
python3 - <<'PY'
import json, os, subprocess, sys, time, urllib.request
q = json.loads(subprocess.check_output([
    "curl","-sS","-X","POST","http://127.0.0.1:8013/v1/quota/refresh",
    "-H","Content-Type: application/json","-d","{}",
], text=True))
print("quota_parsed", {k:q.get(k) for k in ("email","remaining","status","imageable","min_remaining")})
if not q.get("imageable"):
    print("SKIP_IMAGE_NO_QUOTA")
    sys.exit(2)
# single image probe with 75s client wall
body = json.dumps({
    "model": "gpt-image-2",
    "prompt": "a red apple on a white table, simple photo",
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
        raw = resp.read()
        st = resp.status
        j = json.loads(raw)
        b64 = (((j.get("data") or [{}])[0] or {}).get("b64_json") or "")
        print(json.dumps({
            "status": st,
            "elapsed_s": round(time.time()-t0, 3),
            "b64_len": len(b64),
            "ok": st==200 and len(b64)>1000,
        }))
except Exception as e:
    print(json.dumps({"status": None, "elapsed_s": round(time.time()-t0,3), "ok": False, "err": str(e)[:400]}))
    sys.exit(1)
# phase evidence
print("=== PHASE TAIL ===")
subprocess.run(
    "docker logs --since 3m gptimage-gateway-rs-mvp 2>&1 | python3 -c \""
    "import sys,json\n"
    "for line in sys.stdin:\n"
    " s=line.strip(); i=s.find('{');\n"
    " if i<0: continue\n"
    " try: o=json.loads(s[i:])\n"
    " except Exception: continue\n"
    " ev=str(o.get('event') or '')\n"
    " if ev in ('image_pre_conversation_sse_ready','image_sse_post_ready_deadline','image_sse_conversation_id_captured','image_stream_resolve_start','image_poll_hit','image_urls_resolved','request_phase') or o.get('phase') in ('conversation_started','cleanup','sse_ready'):\n"
    "  print({k:o.get(k) for k in ('event','phase','elapsed_ms','conversation_id','tool_invoked','post_ready_timeout_secs','file_ids') if o.get(k) is not None})\n"
    "\"",
    shell=True,
)
PY
