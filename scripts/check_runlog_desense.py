#!/usr/bin/env python3
"""Desensitization gate: fail if any tracked-ish file leaks credentials or real accounts.

History: this gate used to scan only ``<repo>/data/runlogs``, which ``.gitignore``
empties on a clean checkout -- so it always printed ``DESENSE_OK`` regardless of what
the repo actually contained. It now walks the whole repository (minus build output)
and checks five credential shapes plus real account emails.

Usage:
    python3 scripts/check_runlog_desense.py              # scan the repo
    python3 scripts/check_runlog_desense.py /path/to/logs ...   # scan extra roots

Exit codes:
    0  no findings
    1  findings, or a candidate file could not be read
"""
from __future__ import annotations

import fnmatch
import gzip
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOW_FILE = ROOT / ".desense-allow"

# --------------------------------------------------------------------------- scope

# Directories never worth scanning: build output, vendored deps, VCS metadata.
EXCLUDED_DIR_NAMES = frozenset(
    {
        ".git",
        ".next",
        ".venv",
        "__pycache__",
        "node_modules",
        "out",
        "secrets",  # gitignored by design; holds real credentials on purpose
        "target",
        "venv",
    }
)

# Only these suffixes are scanned. Binary/asset types are skipped by omission.
SCANNED_SUFFIXES = frozenset(
    {
        ".cfg",
        ".conf",
        ".ini",
        ".json",
        ".jsonl",
        ".log",
        ".md",
        ".ndjson",
        ".py",
        ".rs",
        ".sh",
        ".toml",
        ".ts",
        ".tsx",
        ".txt",
        ".yaml",
        ".yml",
    }
)

# Extensionless / dotted names worth scanning anyway (config-ish by convention).
SCANNED_NAME_GLOBS: tuple[str, ...] = (
    "Dockerfile*",
    "Makefile",
    ".env",
    ".env.*",
)

# Transparently decompressed before scanning; rotated logs are normally gzipped.
GZIP_SUFFIX = ".gz"

MAX_FILE_BYTES = 8 * 1024 * 1024

# ------------------------------------------------------------------------ patterns


@dataclass(frozen=True)
class Rule:
    name: str
    pattern: re.Pattern[str]


RULES: tuple[Rule, ...] = (
    # Case-insensitive: the old rule was `Bearer\s+\S+` and missed lowercase headers.
    # The token must carry an entropy marker (a digit or a separator) so prose like
    # "requires Bearer Authorization" in an error string is not a finding. Real
    # bearer tokens are never a bare dictionary word.
    Rule(
        "bearer",
        re.compile(
            r"\bbearer\s+(?=[A-Za-z0-9._~+/=-]*[0-9._~+/=-])([A-Za-z0-9._~+/=-]{8,})",
            re.IGNORECASE,
        ),
    ),
    # A bare HS256 header is `eyJhbGciOiJIUzI1NiJ9` -- 20 chars, under the old
    # `{20,}` quantifier once `eyJ` was consumed, so it slipped through.
    Rule("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}(?:\.[A-Za-z0-9_-]+){0,2}")),
    # OpenAI-style keys: sk-, sk-proj-, sk-ant-. Previously absent entirely.
    Rule("api_key", re.compile(r"\b[sr]k-[A-Za-z0-9_-]{10,}")),
    # Inline proxy credentials, e.g. http://user:pass@host:7897.
    Rule(
        "inline_credentials",
        re.compile(r"\b[a-zA-Z][a-zA-Z0-9+.-]*://[^\s:@/]+:[^\s@/]+@[^\s/?#'\"]+"),
    ),
    # Real account emails: this repo has shipped live proton.me / outlook.com
    # addresses in throwaway scripts.
    Rule(
        "email",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,}\b"),
    ),
)

# ----------------------------------------------------------------------- allowlist

# Built-in exemptions for shapes that are placeholders by construction. Anything
# repo-specific belongs in .desense-allow instead of here.
BUILTIN_ALLOW_SUBSTRINGS: tuple[str, ...] = (
    "redacted",
    "placeholder",
    "<token>",
    "${",
    "your-token",
    "changeme",
)

# Domains that can never be a real account: RFC 2606 reserved plus local test names.
PLACEHOLDER_EMAIL_DOMAINS: frozenset[str] = frozenset(
    {
        "example.com",
        "example.net",
        "example.org",
        "invalid",
        "localhost",
        "test",
        "x.com",
    }
)

# Glyphs used to redact a value. A match touching one of these was already masked.
MASK_CHARS: frozenset[str] = frozenset({"*", "…", "█"})


@dataclass(frozen=True)
class AllowEntry:
    """One `.desense-allow` line: a path glob plus an optional match fragment."""

    path_glob: str
    fragment: str | None

    def exempts(self, rel_path: str, matched: str) -> bool:
        if not fnmatch.fnmatch(rel_path, self.path_glob):
            return False
        if self.fragment is None:
            return True
        return self.fragment.lower() in matched.lower()


def load_allowlist(path: Path) -> tuple[AllowEntry, ...]:
    """Parse `.desense-allow`.

    Line formats (``#`` starts a comment, blank lines ignored)::

        docs/example.md                  # exempt the whole file
        docs/example.md :: Bearer REDACTED   # exempt only matches containing that text
    """
    if not path.exists():
        return ()
    entries: list[AllowEntry] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if "::" in line:
            glob_part, fragment = line.split("::", 1)
            entries.append(AllowEntry(glob_part.strip(), fragment.strip()))
        else:
            entries.append(AllowEntry(line, None))
    return tuple(entries)


def is_builtin_allowed(rule: Rule, matched: str, line: str, start: int) -> bool:
    lowered = matched.lower()
    if any(token in lowered for token in BUILTIN_ALLOW_SUBSTRINGS):
        return True
    # Already-desensitized text, e.g. `qaflow*****cd05@proton.me` or `eyJhbG…`.
    # The regexes cannot span mask characters, so they match only the tail; treat a
    # hit that abuts a mask glyph as evidence the value was already redacted.
    if any(ch in matched for ch in MASK_CHARS):
        return True
    if start > 0 and line[start - 1] in MASK_CHARS:
        return True
    if rule.name == "email":
        domain = lowered.rsplit("@", 1)[-1]
        if domain in PLACEHOLDER_EMAIL_DOMAINS:
            return True
        if domain.endswith(".example") or domain.endswith(".local"):
            return True
    return False


# ------------------------------------------------------------------------ scanning


@dataclass(frozen=True)
class Finding:
    rel_path: str
    line_no: int
    rule: str
    masked: str


def mask(value: str) -> str:
    """Show enough to locate the hit without reprinting the credential."""
    stripped = value.strip()
    if len(stripped) <= 8:
        return stripped[0] + "*" * (len(stripped) - 1) if stripped else ""
    return f"{stripped[:3]}***{stripped[-3:]} (len={len(stripped)})"


def is_candidate(path: Path) -> bool:
    name = path.name
    suffixes = path.suffixes
    if suffixes and suffixes[-1] == GZIP_SUFFIX:
        return len(suffixes) > 1 and suffixes[-2] in SCANNED_SUFFIXES
    if path.suffix in SCANNED_SUFFIXES:
        return True
    return any(fnmatch.fnmatch(name, pattern) for pattern in SCANNED_NAME_GLOBS)


def iter_candidates(root: Path):
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            children = list(current.iterdir())
        except OSError as exc:
            yield None, current, exc
            continue
        for child in children:
            if child.is_symlink():
                continue
            if child.is_dir():
                if child.name not in EXCLUDED_DIR_NAMES:
                    stack.append(child)
            elif child.is_file() and is_candidate(child):
                yield child, None, None


def read_text(path: Path) -> tuple[str, bool]:
    """Return (text, was_truncated). Reads one byte past the cap to detect overflow."""
    if path.suffix == GZIP_SUFFIX:
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as handle:
            data = handle.read(MAX_FILE_BYTES + 1)
    else:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            data = handle.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        return data[:MAX_FILE_BYTES], True
    return data, False


def scan_file(
    path: Path, rel_path: str, allowlist: tuple[AllowEntry, ...]
) -> tuple[list[Finding], bool]:
    text, truncated = read_text(path)
    findings: list[Finding] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for rule in RULES:
            for match in rule.pattern.finditer(line):
                matched = match.group(0)
                if is_builtin_allowed(rule, matched, line, match.start()):
                    continue
                if any(entry.exempts(rel_path, matched) for entry in allowlist):
                    continue
                findings.append(Finding(rel_path, line_no, rule.name, mask(matched)))
    return findings, truncated


def relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def main(argv: list[str]) -> int:
    roots = [Path(arg).resolve() for arg in argv[1:]] or [ROOT]
    allowlist = load_allowlist(ALLOW_FILE)

    findings: list[Finding] = []
    unreadable: list[str] = []
    truncated: list[str] = []

    for root in roots:
        if not root.exists():
            print(f"DESENSE_FAIL: scan root does not exist: {root}", file=sys.stderr)
            return 1
        for path, failed_dir, exc in iter_candidates(root):
            if failed_dir is not None:
                unreadable.append(f"{relative(failed_dir, root)}: {exc}")
                continue
            assert path is not None
            rel_path = relative(path, root)
            try:
                file_findings, was_truncated = scan_file(path, rel_path, allowlist)
            except OSError as exc:
                # The old gate swallowed OSError and treated the file as clean.
                unreadable.append(f"{rel_path}: {exc}")
                continue
            findings.extend(file_findings)
            if was_truncated:
                truncated.append(rel_path)

    if unreadable:
        print("DESENSE_UNREADABLE (treated as failure, cannot prove they are clean):")
        for item in sorted(unreadable):
            print(f"  {item}")

    if truncated:
        # Scanning only a prefix cannot prove the tail is clean, so this fails too.
        print(f"DESENSE_TRUNCATED (over {MAX_FILE_BYTES} bytes, tail unscanned):")
        for item in sorted(truncated):
            print(f"  {item}")

    if findings:
        print(f"DESENSE_FAIL: {len(findings)} finding(s)")
        for f in sorted(findings, key=lambda x: (x.rel_path, x.line_no, x.rule)):
            print(f"  {f.rel_path}:{f.line_no}: [{f.rule}] {f.masked}")
        print("")
        print("Redact the values, or add a justified exemption to .desense-allow.")
        return 1

    if unreadable or truncated:
        return 1

    print(f"DESENSE_OK (scanned roots: {', '.join(str(r) for r in roots)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
