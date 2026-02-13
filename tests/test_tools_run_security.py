# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module_from_path(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_run_security_resolve_python_prefers_venv(tmp_path, monkeypatch):
    mod = _load_module_from_path("run_security_mod_resolve", Path("tools/run_security.py"))
    monkeypatch.setattr(mod, "PROJECT_ROOT", tmp_path)

    py = tmp_path / ".venv" / "bin" / "python"
    py.parent.mkdir(parents=True, exist_ok=True)
    py.write_text("#!/usr/bin/env python3\n", encoding="utf-8")

    resolved = mod._resolve_python()
    assert resolved == str(py)


def test_run_security_main_dispatches_targets(monkeypatch):
    mod = _load_module_from_path("run_security_mod_dispatch", Path("tools/run_security.py"))

    calls: list[str] = []
    monkeypatch.setattr(mod, "_resolve_python", lambda: "python3")
    monkeypatch.setattr(mod, "run_secret_scan", lambda py: calls.append(f"secrets:{py}") or 0)
    monkeypatch.setattr(mod, "run_dependency_audit", lambda py: calls.append(f"deps:{py}") or 0)

    monkeypatch.setattr(mod.sys, "argv", ["run_security.py", "secrets"])
    assert mod.main() == 0
    assert calls == ["secrets:python3"]

    calls.clear()
    monkeypatch.setattr(mod.sys, "argv", ["run_security.py", "deps"])
    assert mod.main() == 0
    assert calls == ["deps:python3"]

    calls.clear()
    monkeypatch.setattr(mod.sys, "argv", ["run_security.py", "all"])
    assert mod.main() == 0
    assert calls == ["secrets:python3", "deps:python3"]


def test_run_security_dependency_audit_skips_offline_by_default(monkeypatch):
    mod = _load_module_from_path("run_security_mod_offline_skip", Path("tools/run_security.py"))
    monkeypatch.setattr(mod, "_can_reach_host", lambda *_args, **_kwargs: False)
    monkeypatch.setenv("ASF_FAIL_ON_OFFLINE_AUDIT", "0")
    called = {"run": False}
    monkeypatch.setattr(mod, "_run", lambda _cmd: called.__setitem__("run", True) or 0)

    code = mod.run_dependency_audit("python3")
    assert code == 0
    assert called["run"] is False


def test_run_security_dependency_audit_fails_offline_when_enforced(monkeypatch):
    mod = _load_module_from_path("run_security_mod_offline_fail", Path("tools/run_security.py"))
    monkeypatch.setattr(mod, "_can_reach_host", lambda *_args, **_kwargs: False)
    monkeypatch.setenv("ASF_FAIL_ON_OFFLINE_AUDIT", "1")
    code = mod.run_dependency_audit("python3")
    assert code == 1
