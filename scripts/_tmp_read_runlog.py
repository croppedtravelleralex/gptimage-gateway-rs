#!/usr/bin/env python3
import json
from pathlib import Path
p = Path("/root/gptimage-gateway-rs/data/runlogs/rust-mvp-multi-poolsticky.json")
d = json.loads(p.read_text(encoding="utf-8"))
for r in d.get("rows") or []:
    print({
        "email": r.get("email"),
        "status": r.get("status"),
        "el": r.get("elapsed_s"),
        "fault": r.get("fault"),
        "err": (r.get("err") or "")[:260],
    })
