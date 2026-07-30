#!/usr/bin/env python3
"""Write /opt/tnexus/.env on Panda with gateway JWT for upstream."""
import pathlib
import secrets
import subprocess

ROOT = pathlib.Path("/opt/tnexus")
ROOT.mkdir(parents=True, exist_ok=True)

pass_admin = subprocess.check_output(
    [
        "bash",
        "-lc",
        "grep AUTH_BOOTSTRAP_ADMIN_PASSWORD /root/gptimage-gateway-rs/secrets/gateway.env | cut -d= -f2-",
    ],
    text=True,
).strip()

login = subprocess.run(
    [
        "curl",
        "-fsS",
        "-c",
        "-",
        "-X",
        "POST",
        "http://127.0.0.1:8014/api/auth/login",
        "-H",
        "Content-Type: application/json",
        "-d",
        f'{{"username":"admin","password":"{pass_admin}"}}',
        "-o",
        "/dev/null",
    ],
    capture_output=True,
    text=True,
    check=True,
)

gw_token = ""
for line in login.stdout.splitlines():
    if "gws_session" in line:
        gw_token = line.split()[-1]

env_path = ROOT / ".env"
pg = secrets.token_hex(16)
jwt = secrets.token_hex(32)
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if line.startswith("POSTGRES_PASSWORD="):
            pg = line.split("=", 1)[1].strip()
        if line.startswith("JWT_SECRET="):
            jwt = line.split("=", 1)[1].strip()

text = f"""TNEXUS_IMAGE=ghcr.io/croppedtravelleralex/tnexus:latest
POSTGRES_PASSWORD={pg}
DATABASE_URL=postgres://tnexus:{pg}@127.0.0.1:5433/tnexus
REDIS_URL=redis://127.0.0.1:6380
JWT_SECRET={jwt}
JWT_TTL_SECS=86400
AUTH_COOKIE_SECURE=1
LISTEN_ADDR=0.0.0.0:9000
CORS_ORIGINS=https://tnexus.relai.asia
GATEWAY_STATIC_DIR=/app/web/out
GPTIMAGE_BASE=http://127.0.0.1:8014
GROK2API_BASE=http://127.0.0.1:18000
UPSTREAM_API_KEY={gw_token}
DIRECTOR_MODEL=gpt-4o-mini
CHATGPT_IMAGE_MODEL=gpt-image-2
BOOTSTRAP_ADMIN_EMAIL=admin
BOOTSTRAP_ADMIN_PASSWORD=123456
BOOTSTRAP_DEMO_EMAIL=user
BOOTSTRAP_DEMO_PASSWORD=123456
PRESIGN_TTL_SECS=1800
"""

env_path.write_text(text)
env_path.chmod(0o600)
print(f"wrote {env_path} token_len={len(gw_token)}")
