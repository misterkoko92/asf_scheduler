#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import os
import shlex
import socket
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _resolve_python() -> str:
    candidates = [
        PROJECT_ROOT / ".venv" / "bin" / "python",
        PROJECT_ROOT / ".venv" / "Scripts" / "python.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return sys.executable


def _run(command: list[str]) -> int:
    completed = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    return int(completed.returncode)


def _can_reach_host(host: str, port: int, timeout_sec: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_sec):
            return True
    except OSError:
        return False


def run_secret_scan(python_exec: str) -> int:
    return _run([python_exec, "tools/scan_secrets.py"])


def run_dependency_audit(python_exec: str) -> int:
    if not _can_reach_host("pypi.org", 443):
        if str(os.getenv("ASF_FAIL_ON_OFFLINE_AUDIT", "0")).strip() == "1":
            print(
                "Dependency audit failed: offline environment detected "
                "(pypi.org unreachable)."
            )
            return 1
        print(
            "Dependency audit skipped: offline environment detected "
            "(pypi.org unreachable). Set ASF_FAIL_ON_OFFLINE_AUDIT=1 to fail."
        )
        return 0
    extra_args = shlex.split(os.getenv("ASF_PIP_AUDIT_ARGS", ""))
    cmd = [
        python_exec,
        "-m",
        "pip_audit",
        "--local",
        "--progress-spinner",
        "off",
        *extra_args,
    ]
    return _run(cmd)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run repository security checks.")
    parser.add_argument(
        "target",
        choices=["secrets", "deps", "all"],
        nargs="?",
        default="all",
    )
    args = parser.parse_args()

    python_exec = _resolve_python()
    exit_code = 0

    if args.target in {"secrets", "all"}:
        exit_code = max(exit_code, run_secret_scan(python_exec))
    if args.target in {"deps", "all"}:
        exit_code = max(exit_code, run_dependency_audit(python_exec))

    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
