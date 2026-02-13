#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "QUALITY_DASHBOARD.md"
DEFAULT_HISTORY = PROJECT_ROOT / "QUALITY_DASHBOARD_HISTORY.csv"


@dataclass
class QualitySnapshot:
    generated_at: str
    iso_week: str
    branch: str
    commit: str
    tests_collected: int | None
    coverage_percent: float | None
    coverage_target: int
    gate_ruff: str = "not_run"
    gate_mypy: str = "not_run"
    gate_coverage: str = "not_run"
    gate_secrets: str = "not_run"
    gate_deps: str = "not_run"


def _resolve_python() -> str:
    candidates = [
        PROJECT_ROOT / ".venv" / "bin" / "python",
        PROJECT_ROOT / ".venv" / "Scripts" / "python.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return sys.executable


def _run(command: list[str]) -> tuple[int, str]:
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    output = "\n".join(part for part in (completed.stdout, completed.stderr) if part).strip()
    return int(completed.returncode), output


def _read_default_coverage_target() -> int:
    run_quality = PROJECT_ROOT / "tools" / "run_quality.py"
    try:
        text = run_quality.read_text(encoding="utf-8")
    except OSError:
        return 75
    match = re.search(r'DEFAULT_COVERAGE_MIN\s*=\s*"(\d+)"', text)
    if not match:
        return 75
    try:
        return int(match.group(1))
    except ValueError:
        return 75


def _parse_tests_collected(output: str) -> int | None:
    match = re.search(r"(\d+)\s+tests collected", output)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _collect_tests_collected(python_exec: str) -> int | None:
    code, output = _run([python_exec, "-m", "pytest", "--collect-only", "-q"])
    if code != 0:
        return None
    return _parse_tests_collected(output)


def _read_coverage_percent(coverage_xml: Path) -> float | None:
    if not coverage_xml.exists():
        return None
    try:
        tree = ElementTree.parse(coverage_xml)
    except ElementTree.ParseError:
        return None
    root = tree.getroot()
    raw = root.attrib.get("line-rate")
    if raw is None:
        return None
    try:
        return round(float(raw) * 100.0, 2)
    except ValueError:
        return None


def _low_coverage_modules(coverage_xml: Path, *, limit: int = 10) -> list[tuple[str, float, int]]:
    if not coverage_xml.exists():
        return []
    try:
        tree = ElementTree.parse(coverage_xml)
    except ElementTree.ParseError:
        return []

    rows: list[tuple[str, float, int]] = []
    for class_node in tree.findall(".//class"):
        filename = class_node.attrib.get("filename", "").strip()
        if not filename:
            continue
        line_rate_raw = class_node.attrib.get("line-rate")
        lines_valid_raw = class_node.attrib.get("lines-valid", "0")
        try:
            percent = round(float(line_rate_raw or "0") * 100.0, 2)
        except ValueError:
            continue
        try:
            lines_valid = int(float(lines_valid_raw))
        except ValueError:
            lines_valid = 0
        if lines_valid <= 0:
            lines_valid = len(class_node.findall("./lines/line"))
        rows.append((filename, percent, lines_valid))

    rows.sort(key=lambda item: (item[1], -item[2], item[0]))
    return rows[:limit]


def _git_value(args: list[str], default: str) -> str:
    code, output = _run(["git", *args])
    if code != 0 or not output:
        return default
    return output.splitlines()[0].strip() or default


def _append_history_row(history_file: Path, snap: QualitySnapshot) -> None:
    history_file.parent.mkdir(parents=True, exist_ok=True)
    write_header = not history_file.exists()
    with history_file.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        if write_header:
            writer.writerow(
                [
                    "generated_at",
                    "iso_week",
                    "branch",
                    "commit",
                    "tests_collected",
                    "coverage_percent",
                    "coverage_target",
                    "gate_ruff",
                    "gate_mypy",
                    "gate_coverage",
                    "gate_secrets",
                    "gate_deps",
                ]
            )
        writer.writerow(
            [
                snap.generated_at,
                snap.iso_week,
                snap.branch,
                snap.commit,
                snap.tests_collected if snap.tests_collected is not None else "",
                snap.coverage_percent if snap.coverage_percent is not None else "",
                snap.coverage_target,
                snap.gate_ruff,
                snap.gate_mypy,
                snap.gate_coverage,
                snap.gate_secrets,
                snap.gate_deps,
            ]
        )


def _read_history_tail(history_file: Path, *, limit: int = 12) -> list[dict[str, str]]:
    if not history_file.exists():
        return []
    try:
        with history_file.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except OSError:
        return []
    if len(rows) <= limit:
        return rows
    return rows[-limit:]


def _gate_status(code: int) -> str:
    return "pass" if code == 0 else "fail"


def _refresh_gates(python_exec: str, *, with_deps: bool) -> dict[str, str]:
    statuses = {
        "gate_ruff": "not_run",
        "gate_mypy": "not_run",
        "gate_coverage": "not_run",
        "gate_secrets": "not_run",
        "gate_deps": "not_run",
    }
    gate_commands = [
        ("gate_ruff", [python_exec, "tools/run_quality.py", "ruff"]),
        ("gate_mypy", [python_exec, "tools/run_quality.py", "mypy"]),
        ("gate_coverage", [python_exec, "tools/run_quality.py", "coverage"]),
        ("gate_secrets", [python_exec, "tools/run_security.py", "secrets"]),
    ]
    if with_deps:
        gate_commands.append(("gate_deps", [python_exec, "tools/run_security.py", "deps"]))

    for key, command in gate_commands:
        code, _ = _run(command)
        statuses[key] = _gate_status(code)
    return statuses


def _build_markdown(
    snap: QualitySnapshot,
    *,
    low_coverage: Iterable[tuple[str, float, int]],
    history_rows: list[dict[str, str]],
) -> str:
    lines: list[str] = []
    lines.append("# Quality Dashboard")
    lines.append("")
    lines.append(f"- Generated: {snap.generated_at}")
    lines.append(f"- ISO week: {snap.iso_week}")
    lines.append(f"- Branch: `{snap.branch}`")
    lines.append(f"- Commit: `{snap.commit}`")
    lines.append("")
    lines.append("## Current Snapshot")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| Tests collected | {snap.tests_collected if snap.tests_collected is not None else 'n/a'} |")
    lines.append(f"| Coverage total | {snap.coverage_percent if snap.coverage_percent is not None else 'n/a'} |")
    lines.append(f"| Coverage target | {snap.coverage_target}% |")
    lines.append("")
    lines.append("## Quality Gates")
    lines.append("")
    lines.append("| Gate | Status |")
    lines.append("|---|---|")
    lines.append(f"| Ruff | {snap.gate_ruff} |")
    lines.append(f"| Mypy | {snap.gate_mypy} |")
    lines.append(f"| Coverage | {snap.gate_coverage} |")
    lines.append(f"| Secrets | {snap.gate_secrets} |")
    lines.append(f"| Dependency audit | {snap.gate_deps} |")
    lines.append("")
    lines.append("## Lowest Coverage Modules")
    lines.append("")
    lines.append("| Module | Coverage % | Lines |")
    lines.append("|---|---:|---:|")
    low_rows = list(low_coverage)
    if low_rows:
        for name, coverage, lines_valid in low_rows:
            lines.append(f"| `{name}` | {coverage:.2f} | {lines_valid} |")
    else:
        lines.append("| _n/a_ | _n/a_ | _n/a_ |")
    lines.append("")
    lines.append("## Weekly History")
    lines.append("")
    lines.append("| Generated | Week | Branch | Commit | Tests | Coverage | Target | Ruff | Mypy | Coverage Gate | Secrets | Deps |")
    lines.append("|---|---|---|---|---:|---:|---:|---|---|---|---|---|")
    if history_rows:
        for row in history_rows:
            lines.append(
                "| "
                + " | ".join(
                    [
                        row.get("generated_at", ""),
                        row.get("iso_week", ""),
                        row.get("branch", ""),
                        row.get("commit", ""),
                        row.get("tests_collected", ""),
                        row.get("coverage_percent", ""),
                        row.get("coverage_target", ""),
                        row.get("gate_ruff", ""),
                        row.get("gate_mypy", ""),
                        row.get("gate_coverage", ""),
                        row.get("gate_secrets", ""),
                        row.get("gate_deps", ""),
                    ]
                )
                + " |"
            )
    else:
        lines.append("| _n/a_ | _n/a_ | _n/a_ | _n/a_ | _n/a_ | _n/a_ | _n/a_ | _n/a_ | _n/a_ | _n/a_ | _n/a_ | _n/a_ |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate weekly quality dashboard.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--history", default=str(DEFAULT_HISTORY))
    parser.add_argument("--refresh", action="store_true", help="Run quality/security gates before snapshot.")
    parser.add_argument("--with-deps", action="store_true", help="Include dependency audit during refresh.")
    parser.add_argument("--fail-on-gate", action="store_true", help="Return non-zero when a refreshed gate fails.")
    args = parser.parse_args()

    python_exec = _resolve_python()
    now = datetime.now(timezone.utc).astimezone()
    coverage_target = _read_default_coverage_target()

    snap = QualitySnapshot(
        generated_at=now.strftime("%Y-%m-%d %H:%M:%S %Z"),
        iso_week=f"{now.isocalendar().year}-W{int(now.isocalendar().week):02d}",
        branch=_git_value(["rev-parse", "--abbrev-ref", "HEAD"], "unknown"),
        commit=_git_value(["rev-parse", "--short", "HEAD"], "unknown"),
        tests_collected=_collect_tests_collected(python_exec),
        coverage_percent=_read_coverage_percent(PROJECT_ROOT / "coverage.xml"),
        coverage_target=coverage_target,
    )

    if args.refresh:
        statuses = _refresh_gates(python_exec, with_deps=bool(args.with_deps))
        for key, value in statuses.items():
            setattr(snap, key, value)
        # Re-read generated artifacts after refresh.
        snap.tests_collected = _collect_tests_collected(python_exec)
        snap.coverage_percent = _read_coverage_percent(PROJECT_ROOT / "coverage.xml")

    history_path = Path(args.history)
    _append_history_row(history_path, snap)
    history_rows = _read_history_tail(history_path)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        _build_markdown(
            snap,
            low_coverage=_low_coverage_modules(PROJECT_ROOT / "coverage.xml"),
            history_rows=history_rows,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Dashboard written: {output_path}")

    if args.fail_on_gate and args.refresh:
        gate_values = [
            snap.gate_ruff,
            snap.gate_mypy,
            snap.gate_coverage,
            snap.gate_secrets,
        ]
        if args.with_deps:
            gate_values.append(snap.gate_deps)
        if any(value == "fail" for value in gate_values):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
