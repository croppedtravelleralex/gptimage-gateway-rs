"""Phase B' spike baseline: capture curl_cffi's TLS fingerprint.

Mirrors spike/tls-fingerprint/src/main.rs but on the Python side, using the
same impersonate profiles that production actually uses
(gptimage-panda/services/account_fingerprint.py FP_PROFILES).

Temporary spike artifact -- not part of scripts/ and not wired into anything.
"""

from __future__ import annotations

import json
import os
import sys

from curl_cffi import requests

FP_ENDPOINT = "https://tls.browserleaks.com/json"

# Exactly the impersonate values in gptimage-panda FP_PROFILES.
TARGETS = ["chrome120", "chrome124", "chrome131"]


def main() -> int:
    proxy = os.environ.get("SPIKE_PROXY") or ""
    proxies = {"http": proxy, "https": proxy} if proxy else None

    results = []
    for profile in TARGETS:
        try:
            with requests.Session(impersonate=profile, timeout=30) as s:
                r = s.get(FP_ENDPOINT, proxies=proxies)
                print(f"=== curl_cffi {profile} (HTTP {r.status_code}) ===")
                print(r.text)
                print()
                v = r.json()
                results.append(
                    {
                        "client": "curl_cffi",
                        "profile": profile,
                        "ja3_hash": v.get("ja3_hash"),
                        "ja3_text": v.get("ja3_text"),
                        "ja3n_hash": v.get("ja3n_hash"),
                        "ja4": v.get("ja4"),
                        "ja4_r": v.get("ja4_r"),
                        "ja4_ro": v.get("ja4_ro"),
                        "akamai_hash": v.get("akamai_hash"),
                        "akamai_text": v.get("akamai_text"),
                        "user_agent": v.get("user_agent"),
                    }
                )
        except Exception as exc:  # noqa: BLE001 - spike: report and continue
            print(f"=== curl_cffi {profile} FAILED ===")
            print(f"{type(exc).__name__}: {exc}")
            print()

    print("---SUMMARY-JSON---")
    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
