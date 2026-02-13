#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
QUALITY_SCOPE = ["asf_app", "scheduler", "loaders", "utils", "tests"]
DEFAULT_COVERAGE_MIN = "75"


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


def run_coverage(python_exec: str) -> int:
    min_cov = str(
        os.getenv("ASF_COVERAGE_MIN")
        or os.getenv("COVERAGE_MIN")
        or DEFAULT_COVERAGE_MIN
    )
    return _run(
        [
            python_exec,
            "-m",
            "pytest",
            "-q",
            "--maxfail=1",
            "--disable-warnings",
            "--cov=asf_app",
            "--cov=scheduler",
            "--cov=loaders",
            "--cov=utils",
            "--cov-report=term",
            "--cov-report=xml",
            f"--cov-fail-under={min_cov}",
        ]
    )


def run_dashboard(python_exec: str) -> int:
    return _run(
        [
            python_exec,
            "tools/quality_dashboard.py",
            "--refresh",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run repository quality checks.")
    parser.add_argument(
        "target",
        choices=["ruff", "mypy", "coverage", "dashboard", "all"],
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
    if args.target in {"coverage", "all"}:
        exit_code = max(exit_code, run_coverage(python_exec))
    if args.target == "dashboard":
        exit_code = max(exit_code, run_dashboard(python_exec))

    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
