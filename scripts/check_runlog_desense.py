#!/usr/bin/env python3
"""Fail if runlogs look like they contain Bearer tokens or JWT-ish blobs."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNLOGS = ROOT / "data" / "runlogs"
PAT = re.compile(r"Bearer\s+\S+|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}")


def main() -> int:
    if not RUNLOGS.exists():
        print("no runlogs dir; ok")
        return 0
    bad = []
    for p in RUNLOGS.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() in {".png", ".jpg", ".webp", ".gz"}:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if PAT.search(text):
            bad.append(str(p))
    if bad:
        print("DESENSE_FAIL", *bad, sep="\n")
        return 1
    print("DESENSE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
