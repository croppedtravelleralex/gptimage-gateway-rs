#!/usr/bin/env python3
"""Capture Phase B golden fixtures from production Python builders.

Writes JSON under fixtures/protocol/. Re-run after chatgpt_web_request.py changes.

Usage (WSL / Linux):
  GPTIMAGE_ROOT=../gptimage python3 scripts/capture_protocol_fixtures.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "fixtures" / "protocol"
GPTIMAGE_ROOT = Path(os.environ.get("GPTIMAGE_ROOT", ROOT.parent / "gptimage"))

FIXTURE_UUIDS = [
    "00000000-0000-4000-8000-000000000001",
    "00000000-0000-4000-8000-000000000002",
    "00000000-0000-4000-8000-000000000003",
    "00000000-0000-4000-8000-000000000004",
    "00000000-0000-4000-8000-000000000005",
    "00000000-0000-4000-8000-000000000006",
]
_uuid_iter = iter(FIXTURE_UUIDS)


def _fixture_uuid() -> str:
    try:
        return next(_uuid_iter)
    except StopIteration:
        return str(uuid.uuid4())


def main() -> int:
    if not GPTIMAGE_ROOT.is_dir():
        print(f"GPTIMAGE_ROOT not found: {GPTIMAGE_ROOT}", file=sys.stderr)
        return 2
    sys.path.insert(0, str(GPTIMAGE_ROOT))
    from services.protocol import chatgpt_web_request as cwr  # noqa: WPS433

    OUT.mkdir(parents=True, exist_ok=True)
    fixed_time = 1_730_000_000.0
    seed = "fixture-contextual-seed"

    real_ctx = cwr.build_client_contextual_info

    def patched_ctx(**kw):
        kw = dict(kw)
        kw["jitter"] = False
        return real_ctx(**kw)

    with (
        mock.patch.object(cwr, "new_uuid", side_effect=_fixture_uuid),
        mock.patch("time.time", return_value=fixed_time),
        mock.patch.object(cwr, "build_client_contextual_info", patched_ctx),
    ):
        chat_messages = [
            {
                "id": _fixture_uuid(),
                "author": {"role": "user"},
                "content": {"content_type": "text", "parts": ["hello fixture"]},
                "metadata": {},
            }
        ]
        chat_body = cwr.build_chat_body(
            chat_messages,
            "gpt-4o-mini",
            timezone="Asia/Shanghai",
            timezone_offset=-480,
            contextual_seed=seed,
            contextual_jitter=False,
        )

        prepare = cwr.build_image_prepare_body(
            "sunset over ocean",
            "gpt-image-2",
            timezone="Asia/Shanghai",
            timezone_offset=-480,
            spa_tool_path=True,
        )

        start = cwr.build_image_start_body(
            "a red cube on white background",
            "gpt-image-2",
            timezone="Asia/Shanghai",
            timezone_offset=-480,
            contextual_seed=seed,
            spa_tool_path=True,
        )

        refs = [
            {
                "file_id": "file-fixture-001",
                "mime_type": "image/png",
                "file_name": "input.png",
                "file_size": 204800,
                "width": 1024,
                "height": 1024,
            }
        ]
        start_refs = cwr.build_image_start_body(
            "edit: make the sky sunset orange",
            "gpt-image-2",
            references=refs,
            timezone="Asia/Shanghai",
            timezone_offset=-480,
            contextual_seed=seed,
            spa_tool_path=True,
        )

    class Req:
        token = "fixture-requirements-token"
        proof_token = "fixture-proof"
        turnstile_token = ""
        so_token = ""

    sentinel = cwr.build_sentinel_headers(Req())
    estuary = {
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Authorization": "Bearer REDACTED",
        "must_include": ["Authorization"],
    }
    upload = {
        "api_session": {"must_include": ["Authorization", "OAI-Device-Id"]},
        "resource_put": {
            "must_include": ["Content-Type", "x-ms-blob-type"],
            "must_not_include": ["Authorization", "OAI-Device-Id", "OAI-Language"],
        },
    }

    writes = {
        "chat_body.json": chat_body,
        "image_prepare_body.json": prepare,
        "image_start_body.json": start,
        "image_start_body_with_refs.json": start_refs,
        "sentinel_headers.json": sentinel,
        "estuary_headers.json": estuary,
        "upload_api_vs_resource.json": upload,
    }
    for name, payload in writes.items():
        path = OUT / name
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {path.relative_to(ROOT)}")

    meta = {
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "gptimage_root": str(GPTIMAGE_ROOT),
        "fixed_time": fixed_time,
        "contextual_seed": seed,
        "contextual_jitter": False,
        "spa_tool_path": True,
    }
    (OUT / "capture_meta.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )
    print("capture_meta.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
