#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
QUALITY_SCOPE = ["asf_app", "scheduler", "loaders", "utils", "tests"]


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


def run_ruff(python_exec: str) -> int:
    return _run(
        [
            python_exec,
            "-m",
            "ruff",
            "check",
            "--config",
            ".ruff.toml",
            *QUALITY_SCOPE,
        ]
    )


def run_mypy(python_exec: str) -> int:
    return _run(
        [
            python_exec,
            "-m",
            "mypy",
            "--config-file",
            "mypy.ini",
            "asf_app",
            "scheduler",
            "loaders",
            "utils",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run repository quality checks.")
    parser.add_argument(
        "target",
        choices=["ruff", "mypy", "all"],
        nargs="?",
        default="all",
    )
    args = parser.parse_args()

    python_exec = _resolve_python()
    exit_code = 0

    if args.target in {"ruff", "all"}:
        exit_code = max(exit_code, run_ruff(python_exec))
    if args.target in {"mypy", "all"}:
        exit_code = max(exit_code, run_mypy(python_exec))

    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
