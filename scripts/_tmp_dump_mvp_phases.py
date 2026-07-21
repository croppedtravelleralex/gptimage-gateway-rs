#!/usr/bin/env python3
import json, subprocess
raw = subprocess.check_output(
    ["docker", "logs", "--since", "8m", "gptimage-gateway-rs-mvp"],
    stderr=subprocess.STDOUT,
    text=True,
    errors="replace",
)
want_ev = (
    "image_pre_conversation_sse_ready",
    "image_sse_post_ready_deadline",
    "image_sse_conversation_id_captured",
    "image_stream_resolve_start",
    "image_resolve_poll_needed",
    "image_poll_start",
    "image_poll_hit",
    "image_poll_timeout",
    "image_urls_resolved",
    "request_phase",
)
for line in raw.splitlines():
    i = line.find("{")
    if i < 0:
        continue
    try:
        o = json.loads(line[i:])
    except Exception:
        continue
    ev = str(o.get("event") or "")
    ph = str(o.get("phase") or "")
    if ev not in want_ev and ph not in (
        "conversation_started",
        "cleanup",
        "sse_ready",
        "upstream_submit",
    ):
        continue
    print(
        {
            k: o.get(k)
            for k in (
                "event",
                "phase",
                "elapsed_ms",
                "conversation_id",
                "tool_invoked",
                "post_ready_timeout_secs",
                "file_ids",
                "timeout_secs",
            )
            if o.get(k) is not None
        }
    )
