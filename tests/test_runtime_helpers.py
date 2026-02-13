# -*- coding: utf-8 -*-
from __future__ import annotations

import types

import scheduler.config_paths as cp
from asf_app.config import runtime


def test_get_session_context_returns_none_when_import_fails(monkeypatch):
    fake_module = types.ModuleType("asf_app.config.session_context")
    monkeypatch.setitem(__import__("sys").modules, "asf_app.config.session_context", fake_module)

    assert runtime._get_session_context() is None


def test_runtime_falls_back_to_config_paths(monkeypatch):
    monkeypatch.setattr(runtime, "_get_session_context", lambda: None)
    assert runtime.get_tmp_dir() == cp.TMP_DIR
