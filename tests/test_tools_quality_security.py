# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import SimpleNamespace


def _load_module_from_path(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_run_quality_resolve_python_prefers_venv(tmp_path, monkeypatch):
    mod = _load_module_from_path("run_quality_mod", Path("tools/run_quality.py"))
    monkeypatch.setattr(mod, "PROJECT_ROOT", tmp_path)

    py = tmp_path / ".venv" / "bin" / "python"
    py.parent.mkdir(parents=True, exist_ok=True)
    py.write_text("#!/usr/bin/env python3\n", encoding="utf-8")

    resolved = mod._resolve_python()
    assert resolved == str(py)


def test_run_quality_main_dispatches_targets(monkeypatch):
    mod = _load_module_from_path("run_quality_mod_dispatch", Path("tools/run_quality.py"))

    calls: list[str] = []
    monkeypatch.setattr(mod, "_resolve_python", lambda: "python3")
    monkeypatch.setattr(mod, "run_ruff", lambda py: calls.append(f"ruff:{py}") or 0)
    monkeypatch.setattr(mod, "run_mypy", lambda py: calls.append(f"mypy:{py}") or 0)

    monkeypatch.setattr(mod.sys, "argv", ["run_quality.py", "ruff"])
    assert mod.main() == 0
    assert calls == ["ruff:python3"]

    calls.clear()
    monkeypatch.setattr(mod.sys, "argv", ["run_quality.py", "all"])
    assert mod.main() == 0
    assert calls == ["ruff:python3", "mypy:python3"]


def test_scan_secrets_should_scan_filters_path_and_suffix():
    mod = _load_module_from_path("scan_secrets_mod_filter", Path("tools/scan_secrets.py"))

    assert mod._should_scan(Path("src/main.py")) is True
    assert mod._should_scan(Path(".env.example")) is False
    assert mod._should_scan(Path("assets/sheet.xlsx")) is False
    assert mod._should_scan(Path(".venv/lib/site.py")) is False


def test_scan_secrets_scan_file_detects_and_ignores_placeholder(tmp_path, monkeypatch):
    mod = _load_module_from_path("scan_secrets_mod_scan", Path("tools/scan_secrets.py"))
    monkeypatch.setattr(mod, "PROJECT_ROOT", tmp_path)

    data = tmp_path / "sample.txt"
    data.write_text(
        "\n".join(
            [
                "API_KEY = replace_with_your_key",  # placeholder: ignored
                "token = ghp_abcdefghijklmnopqrstuvwxyz1234567890",
                "Authorization: Bearer ABCDEFGHIJKLMNOPQRSTUVWXYZ123456",
            ]
        ),
        encoding="utf-8",
    )

    findings = mod._scan_file(Path("sample.txt"))
    kinds = [item[1] for item in findings]
    assert "github-token" in kinds
    assert "bearer-token" in kinds
    assert all("replace_with" not in item[2] for item in findings)


def test_scan_secrets_tracked_files_parses_git_output(tmp_path, monkeypatch):
    mod = _load_module_from_path("scan_secrets_mod_tracked", Path("tools/scan_secrets.py"))
    monkeypatch.setattr(mod, "PROJECT_ROOT", tmp_path)

    fake = SimpleNamespace(returncode=0, stdout=b"a.py\0b.txt\0")
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: fake)

    files = mod._tracked_files()
    assert files == [Path("a.py"), Path("b.txt")]


def test_scan_secrets_main_returns_failure_when_findings(monkeypatch):
    mod = _load_module_from_path("scan_secrets_mod_main", Path("tools/scan_secrets.py"))
    monkeypatch.setattr(mod, "_tracked_files", lambda: [Path("file.txt")])
    monkeypatch.setattr(mod, "_should_scan", lambda p: True)
    monkeypatch.setattr(
        mod,
        "_scan_file",
        lambda p, allowlist_patterns=None: [(1, "secret-assignment", "token=abcdabcdabcdabcd")],
    )

    assert mod.main() == 1


def test_scan_secrets_load_allowlist_patterns(tmp_path, monkeypatch):
    mod = _load_module_from_path("scan_secrets_mod_allowlist", Path("tools/scan_secrets.py"))
    allowlist = tmp_path / ".secret-scan-allowlist"
    allowlist.write_text(
        "\n".join(
            [
                "# comment",
                "",
                r"^tests/fixtures/demo\.txt:\d+:token\s*=\s*dummy_value$",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "ALLOWLIST_FILE", allowlist)

    patterns = mod._load_allowlist_patterns()
    assert len(patterns) == 1
    assert patterns[0].search("tests/fixtures/demo.txt:12:token = dummy_value")


def test_scan_secrets_scan_file_respects_allowlist(tmp_path, monkeypatch):
    mod = _load_module_from_path("scan_secrets_mod_scan_allowlist", Path("tools/scan_secrets.py"))
    monkeypatch.setattr(mod, "PROJECT_ROOT", tmp_path)

    data = tmp_path / "sample.txt"
    data.write_text("token = ghp_abcdefghijklmnopqrstuvwxyz1234567890", encoding="utf-8")

    allowlist_patterns = [mod.re.compile(r"^sample\.txt:1:token = ghp_[A-Za-z0-9_]+$")]
    findings = mod._scan_file(Path("sample.txt"), allowlist_patterns)
    assert findings == []
