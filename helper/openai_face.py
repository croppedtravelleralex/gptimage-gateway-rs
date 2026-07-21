"""OpenAI-compatible face for panda :8013 when Rust binary is not yet published.

Interim PROTO_BRIDGE_FACE — same semantics as crates/gateway, implemented in Python
so MVP matrix can run without linux/amd64 rust artifacts.

Account binding:
  - default: PIN_ACCOUNT_FILE (unchanged)
  - optional header X-Preferred-Account-Email: resolve from gptimage account pool
    (unique proxy per email via pool identity); unknown email → 400
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from protocol_bridge import AccountIn, ImageIn, QuotaIn, TextIn, execute_image, execute_quota, execute_text

PIN_PATH = Path(os.environ.get("PIN_ACCOUNT_FILE", "secrets/pin_account.json"))
LISTEN = os.environ.get("GATEWAY_LISTEN", "0.0.0.0:8013")

face = FastAPI(title="gptimage-gateway-rs-face", version="0.1.0")


def load_pin() -> AccountIn:
    if not PIN_PATH.is_file():
        raise RuntimeError(f"missing PIN_ACCOUNT_FILE={PIN_PATH}")
    raw = json.loads(PIN_PATH.read_text(encoding="utf-8"))
    return AccountIn(
        email=str(raw.get("email") or ""),
        access_token=str(raw.get("access_token") or ""),
        device_id=raw.get("device_id") or None,
        proxy=raw.get("proxy") or None,
        user_agent=raw.get("user_agent") or None,
    )


_PIN: AccountIn | None = None
_QUOTA_CACHE: dict[str, dict[str, Any]] = {}
_ACCOUNT_CACHE: dict[str, AccountIn] = {}
_IMAGE_LOCKS: dict[str, threading.Lock] = {}
_IMAGE_LOCKS_GUARD = threading.Lock()


def _image_lock_for(email: str) -> threading.Lock:
    key = (email or "").strip().lower() or "_default"
    with _IMAGE_LOCKS_GUARD:
        lock = _IMAGE_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _IMAGE_LOCKS[key] = lock
        return lock


def pin() -> AccountIn:
    global _PIN
    if _PIN is None:
        _PIN = load_pin()
    return _PIN


def _proxy_host(proxy: str) -> str:
    p = (proxy or "").strip()
    if not p:
        return ""
    return p.split("@")[-1].split(":")[0].lower()


def resolve_account(preferred: str | None) -> AccountIn:
    """Empty preferred → pin. Else resolve pool row by email (token+proxy required)."""
    pref = (preferred or "").strip()
    if not pref:
        return pin()
    key = pref.lower()
    pin_acc = pin()
    if key == (pin_acc.email or "").strip().lower():
        return pin_acc
    cached = _ACCOUNT_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        from services.account_service import account_service

        for row in account_service.list_accounts():
            email = str(row.get("email") or "").strip()
            if email.lower() != key:
                continue
            token = str(row.get("access_token") or "").strip()
            proxy = str(row.get("proxy") or "").strip()
            if not token or not proxy:
                raise HTTPExceptionish(
                    400,
                    f"pool account {email} missing token or proxy",
                    "account_incomplete",
                    "self",
                )
            fp = row.get("fp") if isinstance(row.get("fp"), dict) else {}
            acc = AccountIn(
                email=email,
                access_token=token,
                device_id=str(
                    row.get("oai-device-id") or fp.get("oai-device-id") or ""
                )
                or None,
                proxy=proxy,
                user_agent=str(row.get("user-agent") or fp.get("user-agent") or "") or None,
            )
            _ACCOUNT_CACHE[key] = acc
            return acc
    except HTTPExceptionish:
        raise
    except Exception as exc:
        raise HTTPExceptionish(
            500,
            f"pool resolve failed: {type(exc).__name__}: {exc}"[:400],
            "pool_resolve_failed",
            "self",
        ) from exc
    raise HTTPExceptionish(
        400,
        f"unknown preferred account email={pref}",
        "account_not_found",
        "self",
    )


def _cached_quota(account: AccountIn, *, force: bool = False) -> dict[str, Any]:
    key = (account.email or "").strip().lower() or "_pin"
    now = time.time()
    slot = _QUOTA_CACHE.get(key) or {}
    if (
        not force
        and slot.get("body")
        and now - float(slot.get("ts") or 0) < 60
    ):
        return dict(slot["body"])
    body = execute_quota(QuotaIn(account=account))
    _QUOTA_CACHE[key] = {"ts": now, "body": body}
    return body


class ChatReq(BaseModel):
    model: str = "gpt-4o-mini"
    messages: list[dict[str, Any]]
    stream: bool = False


class ImageReq(BaseModel):
    model: str = "gpt-image-2"
    prompt: str
    n: int = 1
    size: str = "1024x1024"
    response_format: str = "b64_json"


@face.get("/health")
def health() -> dict[str, Any]:
    p = pin()
    return {
        "ok": True,
        "service": "gptimage-gateway-rs",
        "wave": "mvp",
        "proto_bridge": True,
        "proto_bridge_face": True,
        "helper_ok": True,
        "listen": LISTEN,
        "pin_email": p.email,
        "multi_account": True,
        "min_image_quota": int(os.environ.get("MVP_MIN_IMAGE_QUOTA", "1")),
    }


@face.get("/v1/models")
def models() -> dict[str, Any]:
    return {
        "object": "list",
        "data": [
            {"id": "gpt-4o-mini", "object": "model", "owned_by": "gptimage-gateway-rs"},
            {"id": "gpt-image-2", "object": "model", "owned_by": "gptimage-gateway-rs"},
        ],
    }


@face.get("/v1/accounts/candidates")
def account_candidates(limit: int = 20):
    """List pool accounts with token+proxy; unique proxy_host preferred for multi-conc."""
    limit = max(1, min(100, int(limit or 20)))
    try:
        from services.account_service import account_service

        rows = account_service.list_accounts()
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "message": f"list_accounts failed: {type(exc).__name__}: {exc}"[:400],
                    "type": "gateway_error",
                    "code": "pool_list_failed",
                    "fault": "self",
                }
            },
        )
    out: list[dict[str, Any]] = []
    seen_proxy: set[str] = set()
    for row in rows:
        email = str(row.get("email") or "").strip()
        token = str(row.get("access_token") or "").strip()
        proxy = str(row.get("proxy") or "").strip()
        status = str(row.get("status") or "")
        if not email or not token or not proxy:
            continue
        if status in {"禁用", "异常", "限流"}:
            continue
        host = _proxy_host(proxy)
        if not host or host in seen_proxy:
            continue
        seen_proxy.add(host)
        out.append(
            {
                "email": email,
                "proxy_host": host,
                "status": status,
                "quota": row.get("quota"),
                "panda_receive_state": row.get("panda_receive_state"),
            }
        )
        if len(out) >= limit:
            break
    return {"ok": True, "count": len(out), "accounts": out}


@face.post("/v1/quota/refresh")
def quota_refresh(x_preferred_account_email: str | None = Header(default=None)):
    account = resolve_account(x_preferred_account_email)
    r = _cached_quota(account, force=True)
    if not r.get("ok"):
        fault = r.get("fault") or "upstream"
        code = 500 if fault == "self" else 502
        return JSONResponse(
            status_code=code,
            content={
                "error": {
                    "message": r.get("error") or "quota refresh failed",
                    "type": "gateway_error",
                    "code": "quota_refresh_failed",
                    "fault": fault,
                }
            },
        )
    return {
        "ok": True,
        "email": r.get("email"),
        "plan": r.get("plan"),
        "status": r.get("status"),
        "remaining": r.get("remaining"),
        "restore_at": r.get("restore_at"),
        "image_quota_unknown": r.get("image_quota_unknown"),
        "min_remaining": r.get("min_remaining"),
        "imageable": r.get("imageable"),
        "image_gen": r.get("image_gen"),
        "elapsed_ms": r.get("elapsed_ms"),
        "proxy_host": _proxy_host(account.proxy or ""),
    }


@face.get("/v1/quota")
def quota_get(x_preferred_account_email: str | None = Header(default=None)):
    return quota_refresh(x_preferred_account_email)


class HTTPExceptionish(Exception):
    def __init__(self, status: int, message: str, code: str, fault: str):
        self.status = status
        self.payload = {
            "error": {
                "message": message,
                "type": "gateway_error",
                "code": code,
                "fault": fault,
            }
        }


@face.exception_handler(HTTPExceptionish)
async def _http_exc_handler(_req, exc: HTTPExceptionish):
    return JSONResponse(status_code=exc.status, content=exc.payload)


@face.post("/v1/chat/completions")
def chat(
    body: ChatReq,
    x_preferred_account_email: str | None = Header(default=None),
):
    if body.stream:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "message": "stream not supported in MVP",
                    "type": "gateway_error",
                    "code": "stream_unsupported",
                    "fault": "self",
                }
            },
        )
    account = resolve_account(x_preferred_account_email)
    prompt = ""
    for m in reversed(body.messages or []):
        if m.get("role") == "user":
            c = m.get("content")
            prompt = c if isinstance(c, str) else str(c)
            break
    if not str(prompt).strip():
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "message": "messages must include a user text",
                    "type": "gateway_error",
                    "code": "invalid_request",
                    "fault": "self",
                }
            },
        )
    r = execute_text(TextIn(account=account, prompt=prompt, model=body.model))
    if not r.get("ok"):
        fault = r.get("fault") or "upstream"
        code = 500 if fault == "self" else 502
        return JSONResponse(
            status_code=code,
            content={
                "error": {
                    "message": r.get("error") or "text failed",
                    "type": "gateway_error",
                    "code": "text_failed",
                    "fault": fault,
                }
            },
        )
    return {
        "id": f"chatcmpl-{uuid.uuid4()}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": body.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": r.get("content") or ""},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


@face.post("/v1/images/generations")
def images(
    body: ImageReq,
    x_preferred_account_email: str | None = Header(default=None),
):
    if body.n != 1:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "message": "MVP only supports n=1",
                    "type": "gateway_error",
                    "code": "n_unsupported",
                    "fault": "self",
                }
            },
        )
    account = resolve_account(x_preferred_account_email)
    with _image_lock_for(account.email or ""):
        # Use cached quota only — do not open a second cold Session just to
        # re-probe before pool_sticky image (prod does not do that on sync face).
        q = _cached_quota(account, force=False)
        if not q.get("ok"):
            # One forced refresh on cache miss/failure, still before image.
            q = _cached_quota(account, force=True)
        if not q.get("ok"):
            fault = q.get("fault") or "upstream"
            code = 500 if fault == "self" else 502
            return JSONResponse(
                status_code=code,
                content={
                    "error": {
                        "message": q.get("error") or "quota refresh failed",
                        "type": "gateway_error",
                        "code": "quota_refresh_failed",
                        "fault": fault,
                    }
                },
            )
        if not q.get("imageable"):
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "message": (
                            f"image_quota_insufficient: remaining={q.get('remaining')} "
                            f"status={q.get('status')} min={q.get('min_remaining')}"
                        ),
                        "type": "gateway_error",
                        "code": "image_quota_insufficient",
                        "fault": "quota",
                        "quota": q,
                    }
                },
            )
        r = execute_image(
            ImageIn(
                account=account,
                prompt=body.prompt,
                model=body.model,
                size=body.size,
            ),
            skip_quota_gate=True,
        )
    if not r.get("ok"):
        fault = r.get("fault") or "upstream"
        if fault == "quota":
            code = 429
            err_code = "image_quota_insufficient"
        elif fault == "self":
            code = 500
            err_code = "image_failed"
        else:
            code = 502
            err_code = "image_failed"
        return JSONResponse(
            status_code=code,
            content={
                "error": {
                    "message": r.get("error") or "image failed",
                    "type": "gateway_error",
                    "code": err_code,
                    "fault": fault,
                    "quota": r.get("quota"),
                }
            },
        )
    return {"created": int(time.time()), "data": [{"b64_json": r.get("b64_json")}]}


def main() -> None:
    import uvicorn

    pin()
    host, _, port_s = LISTEN.partition(":")
    uvicorn.run(face, host=host or "0.0.0.0", port=int(port_s or "8013"), log_level="info")


if __name__ == "__main__":
    main()
