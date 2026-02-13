#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import re
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST_FILE = PROJECT_ROOT / ".secret-scan-allowlist"

# Keep the scanner focused to reduce false positives.
SKIP_SUFFIXES = {
    ".xlsx",
    ".xlsm",
    ".xls",
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".ico",
    ".zip",
    ".7z",
    ".tar",
    ".gz",
    ".pyc",
}
SKIP_PATH_PARTS = {".git", ".venv", "venv", ".mypy_cache", ".pytest_cache", ".ruff_cache"}
SKIP_FILES = {".env.example", ".secret-scan-allowlist"}

PLACEHOLDER_RE = re.compile(
    r"(replace_with|example|dummy|changeme|your[_-]?(key|token|secret)|xxx|abc123)",
    re.IGNORECASE,
)

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "private-key",
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ),
    (
        "aws-access-key-id",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    ),
    (
        "github-token",
        re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{30,}\b"),
    ),
    (
        "slack-token",
        re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    ),
    (
        "bearer-token",
        re.compile(r"Bearer\s+[A-Za-z0-9\-_]{20,}"),
    ),
    (
        "secret-assignment",
        re.compile(
            r"(?i)\b(?:api[_-]?key|token|secret|password)\b"
            r"\s*[:=]\s*[\"']?([A-Za-z0-9_\-\/\+=]{16,})[\"']?"
        ),
    ),
]


def _tracked_files() -> list[Path]:
    proc = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
    )
    if proc.returncode != 0:
        return []
    raw = proc.stdout.decode("utf-8", errors="ignore")
    files = [Path(p) for p in raw.split("\0") if p]
    return files


def _load_allowlist_patterns() -> list[re.Pattern[str]]:
    if not ALLOWLIST_FILE.exists():
        return []
    patterns: list[re.Pattern[str]] = []
    for idx, raw_line in enumerate(ALLOWLIST_FILE.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            patterns.append(re.compile(line))
        except re.error as exc:
            raise RuntimeError(f"Invalid allowlist regex at {ALLOWLIST_FILE}:{idx}: {exc}") from exc
    return patterns


def _should_scan(path: Path) -> bool:
    if path.name in SKIP_FILES:
        return False
    if path.suffix.lower() in SKIP_SUFFIXES:
        return False
    for part in path.parts:
        if part in SKIP_PATH_PARTS:
            return False
    return True


def _is_placeholder_line(line: str) -> bool:
    return bool(PLACEHOLDER_RE.search(line))


def _is_allowlisted(
    rel_path: Path,
    line_no: int,
    line: str,
    allowlist_patterns: list[re.Pattern[str]],
) -> bool:
    if not allowlist_patterns:
        return False
    path_line = f"{rel_path}:{line_no}:{line}"
    for pattern in allowlist_patterns:
        if pattern.search(path_line):
            return True
    return False


def _scan_file(
    rel_path: Path,
    allowlist_patterns: list[re.Pattern[str]] | None = None,
) -> list[tuple[int, str, str]]:
    abs_path = PROJECT_ROOT / rel_path
    findings: list[tuple[int, str, str]] = []
    active_allowlist = allowlist_patterns or []
    try:
        content = abs_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return findings

    for line_no, line in enumerate(content.splitlines(), start=1):
        if _is_placeholder_line(line):
            continue
        for finding_type, pattern in PATTERNS:
            match = pattern.search(line)
            if not match:
                continue
            if finding_type == "secret-assignment":
                token = match.group(1) if match.lastindex else ""
                if len(token) < 16:
                    continue
            if _is_allowlisted(rel_path, line_no, line.strip(), active_allowlist):
                continue
            findings.append((line_no, finding_type, line.strip()))
    return findings


def main() -> int:
    allowlist_patterns = _load_allowlist_patterns()
    files = [p for p in _tracked_files() if _should_scan(p)]
    findings: list[tuple[Path, int, str, str]] = []

    for rel_path in files:
        for line_no, finding_type, line in _scan_file(rel_path, allowlist_patterns):
            findings.append((rel_path, line_no, finding_type, line))

    if not findings:
        print("Secret scan passed: no suspicious hardcoded secret found in tracked text files.")
        return 0

    print("Potential hardcoded secrets detected:")
    for rel_path, line_no, finding_type, line in findings:
        print(f"- {rel_path}:{line_no} [{finding_type}] {line[:180]}")
    print(f"Total findings: {len(findings)}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
