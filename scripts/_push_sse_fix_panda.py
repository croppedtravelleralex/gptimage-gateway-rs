#!/usr/bin/env python3
"""Push SSE early-exit fix to panda (stdin protocol), restart MVP, print quota."""
from __future__ import annotations

import base64
import subprocess
import sys
from pathlib import Path

RECEIVER = r'''import base64, pathlib, sys
raw = [ln.rstrip("\n") for ln in sys.stdin]
i = 0
while i < len(raw):
    if not raw[i].strip():
        i += 1
        continue
    name, remote, marker, n = raw[i], raw[i + 1], raw[i + 2], int(raw[i + 3])
    parts = raw[i + 4 : i + 4 + n]
    i = i + 4 + n
    data = base64.b64decode("".join(parts))
    pathlib.Path(remote).write_bytes(data)
    text = data.decode("utf-8", "replace")
    if marker not in text:
        raise SystemExit(f"missing marker {marker!r} in {remote}")
    print(f"wrote {name} -> {remote} count={text.count(marker)}")
'''

FILES = [
    (
        "api",
        Path(r"D:\SelfMadeTool\AutoRegister\gptimage\services\openai_backend_api.py"),
        "/root/gptimage/services/openai_backend_api.py",
        "image_sse_complete_predicate",
    ),
    (
        "bridge",
        Path(r"D:\SelfMadeTool\AutoRegister\gptimage-gateway-rs\helper\protocol_bridge.py"),
        "/root/gptimage-gateway-rs/helper/protocol_bridge.py",
        'MVP_IMAGE_SSE_POST_READY_SECS", "50"',
    ),
]


def ssh(*args: str, input_bytes: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["ssh", "-o", "ConnectTimeout=35", "-o", "BatchMode=yes", "panda", *args],
        input=input_bytes,
        capture_output=True,
    )


def main() -> int:
    put = ssh("cat > /tmp/recv_sse.py", input_bytes=RECEIVER.encode("utf-8"))
    if put.returncode != 0:
        sys.stderr.write(put.stderr.decode("utf-8", "replace"))
        return put.returncode

    lines: list[str] = []
    for name, local, remote, marker in FILES:
        data = local.read_bytes()
        if marker.encode() not in data:
            raise SystemExit(f"local missing {marker} in {local}")
        b64 = base64.b64encode(data).decode("ascii")
        parts = [b64[j : j + 76] for j in range(0, len(b64), 76)]
        lines.extend([name, remote, marker, str(len(parts)), *parts])
    payload = ("\n".join(lines) + "\n").encode("ascii")
    recv = ssh("python3 /tmp/recv_sse.py", input_bytes=payload)
    sys.stdout.write(recv.stdout.decode("utf-8", "replace"))
    sys.stderr.write(recv.stderr.decode("utf-8", "replace"))
    if recv.returncode != 0:
        return recv.returncode

    verify = ssh(
        "grep -c image_sse_complete_predicate /root/gptimage/services/openai_backend_api.py; "
        "grep -n 'MVP_IMAGE_SSE_POST_READY_SECS' /root/gptimage-gateway-rs/helper/protocol_bridge.py | head -1; "
        "docker restart gptimage-gateway-rs-mvp chatgpt2api-local; sleep 8; "
        "curl -fsS http://127.0.0.1:8012/health >/dev/null && echo PROD_OK; "
        "curl -fsS http://127.0.0.1:8013/health; echo; "
        "echo QUOTA_FIRST; "
        "curl -sS -X POST http://127.0.0.1:8013/v1/quota/refresh -H 'Content-Type: application/json' -d '{}'; echo"
    )
    sys.stdout.write(verify.stdout.decode("utf-8", "replace"))
    sys.stderr.write(verify.stderr.decode("utf-8", "replace"))
    return verify.returncode


if __name__ == "__main__":
    raise SystemExit(main())
