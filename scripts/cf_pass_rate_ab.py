#!/usr/bin/env python3
"""Phase B' criterion 2: CF pass-rate A/B harness (curl_cffi vs wreq).

Does not run automatically in CI — requires live egress, account pool, and a CF test window.
See docs/29-cf-pass-rate-ab-20260727.md.

Usage:
  SPIKE_PROXY=http://127.0.0.1:7897 python3 scripts/cf_pass_rate_ab.py --rounds 3
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_curl_cffi(profiles: list[str], proxy: str) -> list[dict]:
    os.environ["SPIKE_PROXY"] = proxy
    env = os.environ.copy()
    proc = subprocess.run(
        [sys.executable, str(ROOT / "spike" / "curl_cffi_baseline.py")],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if proc.returncode != 0:
        print(proc.stderr or proc.stdout, file=sys.stderr)
    text = proc.stdout
    if "---SUMMARY-JSON---" not in text:
        return []
    payload = text.split("---SUMMARY-JSON---", 1)[1].strip()
    return json.loads(payload)


def run_wreq(profiles: list[str], proxy: str) -> list[dict]:
    spike = ROOT / "spike" / "tls-fingerprint"
    if not (spike / "Cargo.toml").exists():
        print("missing spike/tls-fingerprint", file=sys.stderr)
        return []
    env = os.environ.copy()
    if proxy:
        env["SPIKE_PROXY"] = proxy
    proc = subprocess.run(
        ["cargo", "run", "--release", "--", *profiles],
        cwd=spike,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if proc.returncode != 0:
        print(proc.stderr or proc.stdout, file=sys.stderr)
    text = proc.stdout
    if "---SUMMARY-JSON---" not in text:
        return []
    payload = text.split("---SUMMARY-JSON---", 1)[1].strip()
    return json.loads(payload)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=1)
    ap.add_argument(
        "--profiles",
        default="chrome124,chrome131",
        help="comma-separated impersonate profiles (chrome120 excluded)",
    )
    args = ap.parse_args()
    proxy = os.environ.get("SPIKE_PROXY", "http://127.0.0.1:7897")
    profiles = [p.strip() for p in args.profiles.split(",") if p.strip()]

    report = {
        "proxy": proxy,
        "profiles": profiles,
        "rounds": args.rounds,
        "curl_cffi": [],
        "wreq": [],
        "note": "TLS probe only — extend with upstream ChatGPT probe when CF window open",
    }
    for _ in range(args.rounds):
        report["curl_cffi"].append(run_curl_cffi(profiles, proxy))
        report["wreq"].append(run_wreq(profiles, proxy))

    out = ROOT / "data" / "runlogs" / "cf-pass-rate-ab-latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
