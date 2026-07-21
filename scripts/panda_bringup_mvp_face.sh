#!/usr/bin/env bash
# Bring up PROTO_BRIDGE_FACE on panda :8013 (test only; does not touch :8012).
# Prereq: /root/gptimage-gateway-rs/{helper,scripts,secrets} already populated.
set -euo pipefail
ROOT=/root/gptimage-gateway-rs
IMG=$(docker inspect chatgpt2api-local --format '{{.Config.Image}}')
PIN="$ROOT/secrets/pin_account.json"

mkdir -p "$ROOT/secrets" "$ROOT/data/runlogs" "$ROOT/helper" "$ROOT/scripts"

if [[ ! -f "$PIN" ]]; then
  echo "exporting pin account..."
  docker exec -e OUT_PATH=/tmp/pin_account.json chatgpt2api-local \
    python3 - <<'PY' > /tmp/export_pin_out.json
import json, os, sqlite3, sys
db="/app/data/accounts.db"
prefer=(os.environ.get("PIN_EMAIL") or "").strip().lower()
out=os.environ.get("OUT_PATH","/tmp/pin_account.json")
rows=list(sqlite3.connect(db).execute("select id, access_token, data from accounts"))
cands=[]
for _id, token, data in rows:
    try: d=json.loads(data) if isinstance(data,str) else (data or {})
    except Exception: d={}
    if not isinstance(d, dict): d={}
    email=str(d.get("email") or "").strip()
    proxy=str(d.get("proxy") or "").strip()
    st=str(d.get("panda_receive_state") or "").lower()
    status=str(d.get("status") or "")
    if not email or not token or not proxy: continue
    if status in {"禁用","异常"}: continue
    if st and st not in {"verified_ready","verified","local_verified"}: continue
    score=10 if st=="verified_ready" else 0
    if prefer and email.lower()==prefer: score+=100
    cands.append((score,{
      "email":email,"access_token":token,
      "device_id":str(d.get("oai-device-id") or (d.get("fp") or {}).get("oai-device-id") or ""),
      "proxy":proxy,
      "user_agent":str(d.get("user-agent") or (d.get("fp") or {}).get("user-agent") or ""),
    }))
if not cands:
    print("NO_CANDIDATE"); sys.exit(2)
cands.sort(key=lambda x:-x[0])
acc=cands[0][1]
open(out,"w",encoding="utf-8").write(json.dumps(acc,ensure_ascii=False))
print(json.dumps({"ok":True,"email":acc["email"],"proxy_host":acc["proxy"].split("@")[-1].split(":")[0]},ensure_ascii=False))
PY
  docker cp chatgpt2api-local:/tmp/pin_account.json "$PIN"
  chmod 600 "$PIN"
  cat /tmp/export_pin_out.json || true
fi

docker rm -f gptimage-gateway-rs-mvp 2>/dev/null || true
docker run -d --name gptimage-gateway-rs-mvp --network host \
  -v /root/gptimage/api:/app/api:ro \
  -v /root/gptimage/services:/app/services:ro \
  -v /root/gptimage/utils:/app/utils:ro \
  -v /root/gptimage/scripts:/app/scripts:ro \
  -v /root/gptimage/config.json:/app/config.json:ro \
  -v /root/gptimage/data:/app/data:ro \
  -v "$ROOT:/opt/gws" \
  -e GPTIMAGE_ROOT=/app \
  -e PIN_ACCOUNT_FILE=/opt/gws/secrets/pin_account.json \
  -e GATEWAY_LISTEN=0.0.0.0:8013 \
  -e PYTHONPATH=/opt/gws/helper \
  -w /opt/gws/helper \
  "$IMG" \
  python3 openai_face.py

sleep 2
curl -fsS http://127.0.0.1:8013/health | tee "$ROOT/data/runlogs/health-$(date +%Y%m%d-%H%M%S).json"
echo
echo "MVP face up on :8013 (production :8012 untouched)"
