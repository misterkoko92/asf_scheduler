# -*- coding: utf-8 -*-
from __future__ import annotations

import asf_app.ui.ui_communication.whatsapp_handler as wa


def test_open_whatsapp_cloud_mode_does_not_spawn_process(monkeypatch):
    monkeypatch.setattr(wa, "IS_STREAMLIT_CLOUD", True)
    calls = {"info": [], "code": [], "popen": []}

    monkeypatch.setattr(wa.st, "info", lambda msg: calls["info"].append(msg))
    monkeypatch.setattr(wa.st, "code", lambda msg: calls["code"].append(msg))
    monkeypatch.setattr(wa.subprocess, "Popen", lambda *args, **kwargs: calls["popen"].append((args, kwargs)))

    wa._open_whatsapp("https://wa.me/33600000000?text=test")

    assert calls["info"]
    assert calls["code"]
    assert calls["popen"] == []


def test_open_whatsapp_windows_without_shell_true(monkeypatch):
    monkeypatch.setattr(wa, "IS_STREAMLIT_CLOUD", False)
    monkeypatch.setattr(wa.platform, "system", lambda: "Windows")
    calls = []
    monkeypatch.setattr(wa.subprocess, "Popen", lambda *args, **kwargs: calls.append((args, kwargs)))

    wa._open_whatsapp("https://wa.me/33600000000?text=test")

    assert len(calls) == 1
    args, kwargs = calls[0]
    assert list(args[0])[:3] == ["cmd", "/c", "start"]
    assert kwargs.get("shell") is None
