# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

from asf_app.ui.ui_communication import outlook


def test_clean_list_variants():
    assert outlook._clean_list(None) == []
    assert outlook._clean_list("a@x.com ; b@x.com, c@x.com") == ["a@x.com", "b@x.com", "c@x.com"]
    assert outlook._clean_list(["a@x.com", " ", None]) == ["a@x.com", "None"]


def test_create_outlook_draft_unsupported_system(monkeypatch):
    monkeypatch.setattr(outlook.platform, "system", lambda: "Linux")

    with pytest.raises(RuntimeError):
        outlook.create_outlook_draft(to_list=["a@x.com"])


def test_create_outlook_draft_dispatches_windows(monkeypatch):
    monkeypatch.setattr(outlook.platform, "system", lambda: "Windows")
    captured = {}

    def _fake_windows(**kwargs):
        captured.update(kwargs)
        return True

    monkeypatch.setattr(outlook, "_create_outlook_windows", _fake_windows)

    ok = outlook.create_outlook_draft(
        to_list="a@x.com ; b@x.com",
        cc_list="c@x.com",
        bcc_list=None,
        subject="Sujet",
        body_html="<p>Body</p>",
    )

    assert ok is True
    assert captured["to_list"] == ["a@x.com", "b@x.com"]
    assert captured["cc_list"] == ["c@x.com"]


def test_create_outlook_mac_returns_false_on_subprocess_error(monkeypatch):
    class _Res:
        returncode = 1
        stderr = "boom"
        stdout = ""

    monkeypatch.setattr(outlook.subprocess, "run", lambda *args, **kwargs: _Res())

    ok = outlook._create_outlook_mac(
        to_list=["a@x.com"],
        cc_list=[],
        bcc_list=[],
        subject="x",
        body_html="<p>x</p>",
        attachments=[],
        use_signature=True,
    )

    assert ok is False


def test_create_outlook_mac_returns_false_on_oserror(monkeypatch):
    def _raise(*args, **kwargs):
        raise OSError("osascript missing")

    monkeypatch.setattr(outlook.subprocess, "run", _raise)

    ok = outlook._create_outlook_mac(
        to_list=["a@x.com"],
        cc_list=[],
        bcc_list=[],
        subject="x",
        body_html="<p>x</p>",
        attachments=[],
        use_signature=True,
    )

    assert ok is False
