#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import ast
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOTS = ("asf_app", "scheduler", "loaders", "utils")
IGNORE_DIRS = {".git", ".venv", "venv", "__pycache__", ".tmp_asf", "~"}


@dataclass
class FunctionStat:
    size: int
    file: Path
    name: str
    lineno: int


def _iter_py_files(repo_root: Path):
    for root_name in ROOTS:
        root = repo_root / root_name
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if any(part in IGNORE_DIRS for part in path.parts):
                continue
            yield path


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _top_file_sizes(py_files: list[Path], top_n: int) -> list[tuple[int, Path]]:
    out = []
    for path in py_files:
        try:
            out.append((len(_read_text(path).splitlines()), path))
        except Exception:
            continue
    return sorted(out, reverse=True)[:top_n]


def _top_functions(py_files: list[Path], top_n: int) -> list[FunctionStat]:
    stats: list[FunctionStat] = []
    for path in py_files:
        try:
            src = _read_text(path)
            tree = ast.parse(src)
        except Exception:
            continue

        class Visitor(ast.NodeVisitor):
            def __init__(self):
                self.stack: list[str] = []

            def visit_FunctionDef(self, node: ast.FunctionDef):
                end = getattr(node, "end_lineno", node.lineno)
                stats.append(
                    FunctionStat(
                        size=end - node.lineno + 1,
                        file=path,
                        name=".".join(self.stack + [node.name]),
                        lineno=node.lineno,
                    )
                )
                self.stack.append(node.name)
                self.generic_visit(node)
                self.stack.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_ClassDef(self, node: ast.ClassDef):
                self.stack.append(node.name)
                self.generic_visit(node)
                self.stack.pop()

        Visitor().visit(tree)
    return sorted(stats, key=lambda s: s.size, reverse=True)[:top_n]


def _pattern_hits(py_files: list[Path], pattern: str) -> list[tuple[Path, int]]:
    rx = re.compile(pattern, flags=re.MULTILINE)
    out = []
    for path in py_files:
        try:
            n = len(rx.findall(_read_text(path)))
        except Exception:
            continue
        if n:
            out.append((path, n))
    return sorted(out, key=lambda x: x[1], reverse=True)


def _run_cmd(repo_root: Path, args: list[str]) -> str:
    try:
        res = subprocess.run(
            args,
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
        return (res.stdout or "").strip()
    except Exception:
        return ""


def build_report(repo_root: Path, top_n: int = 20) -> str:
    py_files = list(_iter_py_files(repo_root))
    top_files = _top_file_sizes(py_files, top_n=top_n)
    top_funcs = _top_functions(py_files, top_n=top_n)
    except_hits = _pattern_hits(py_files, r"except Exception|except:\s*$")
    print_hits = _pattern_hits(py_files, r"\bprint\(")
    shell_true_hits = _pattern_hits(py_files, r"shell=True")

    tracked_artifacts = _run_cmd(
        repo_root,
        ["git", "ls-files"],
    )
    artifact_lines = []
    if tracked_artifacts:
        for line in tracked_artifacts.splitlines():
            if re.search(r"\.(xlsx|xlsm|pdf|log|zip|parquet|json)$", line):
                artifact_lines.append(line)

    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    lines: list[str] = []
    lines.append("# Hardening Audit Report")
    lines.append("")
    lines.append(f"- Generated: {now}")
    lines.append(f"- Python files scanned: {len(py_files)}")
    lines.append("")

    lines.append("## Largest Files")
    for size, path in top_files:
        lines.append(f"- `{path}`: {size} lines")
    lines.append("")

    lines.append("## Longest Functions")
    for stat in top_funcs:
        lines.append(f"- `{stat.file}:{stat.lineno}` `{stat.name}`: {stat.size} lines")
    lines.append("")

    lines.append("## Broad Exception Hotspots")
    for path, count in except_hits[:top_n]:
        lines.append(f"- `{path}`: {count}")
    lines.append("")

    lines.append("## Print Call Hotspots")
    for path, count in print_hits[:top_n]:
        lines.append(f"- `{path}`: {count}")
    lines.append("")

    lines.append("## shell=True Occurrences")
    if shell_true_hits:
        for path, count in shell_true_hits:
            lines.append(f"- `{path}`: {count}")
    else:
        lines.append("- none")
    lines.append("")

    lines.append("## Tracked Runtime Artifacts (to review)")
    if artifact_lines:
        for line in artifact_lines:
            lines.append(f"- `{line}`")
    else:
        lines.append("- none")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a hardening audit report.")
    parser.add_argument(
        "--output",
        default="HARDENING_AUDIT_REPORT.md",
        help="Output markdown file path (default: HARDENING_AUDIT_REPORT.md)",
    )
    parser.add_argument("--top", type=int, default=20, help="Top N rows per section.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    report = build_report(repo_root, top_n=max(5, int(args.top)))
    out_path = repo_root / args.output
    out_path.write_text(report + "\n", encoding="utf-8")
    print(f"Report written: {out_path}")


if __name__ == "__main__":
    main()
