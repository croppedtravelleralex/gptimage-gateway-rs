#!/usr/bin/env bash
# Install helper + gptimage Python deps on WSL (host python, no venv).
set -euo pipefail

echo "Installing fastapi stack..."
pip3 install --break-system-packages -q \
  fastapi "uvicorn[standard]" pydantic httpx \
  pillow curl-cffi pybase64 python-multipart tiktoken \
  sqlalchemy psycopg2-binary gitpython

python3 -c "import fastapi, curl_cffi, PIL; print('helper deps OK')"
