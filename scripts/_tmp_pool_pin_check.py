#!/usr/bin/env python3
import json
import traceback
from pathlib import Path

candidates = [
    Path("/opt/gws/secrets/pin_account.json"),
    Path("/root/gptimage-gateway-rs/secrets/pin_account.json"),
]
pin = None
for p in candidates:
    if p.is_file():
        pin = json.loads(p.read_text(encoding="utf-8"))
        print("pin_file", str(p))
        break
if not pin:
    raise SystemExit("no pin")
email = (pin.get("email") or "").strip().lower()
print("pin_email", email)
print("pin_proxy", (pin.get("proxy") or "").split("@")[-1])
try:
    from services.account_service import account_service

    rows = account_service.list_accounts()
    print("pool_n", len(rows))
    hits = [r for r in rows if str(r.get("email") or "").strip().lower() == email]
    print("hits", len(hits))
    if hits:
        h = hits[0]
        print("pool_proxy", str(h.get("proxy") or "").split("@")[-1])
        print("pool_status", h.get("status"))
        print("token_len_pool", len(str(h.get("access_token") or "")))
        print("token_len_pin", len(str(pin.get("access_token") or "")))
        print("token_prefix_same", str(h.get("access_token") or "")[:24] == str(pin.get("access_token") or "")[:24])
        fp = h.get("fp") if isinstance(h.get("fp"), dict) else {}
        print("device", h.get("oai-device-id") or fp.get("oai-device-id"))
        print("ua_head", str(h.get("user-agent") or fp.get("user-agent") or "")[:60])
except Exception:
    traceback.print_exc()
