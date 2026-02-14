# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import types
import importlib

from asf_app.ui.ui_communication import outlook


class _FakeAttachments:
    def __init__(self, fail_paths: set[str] | None = None):
        self.added: list[str] = []
        self.fail_paths = fail_paths or set()

    def Add(self, path):
        if path in self.fail_paths:
            raise OSError("attachment error")
        self.added.append(path)


class _FakeMail:
    def __init__(self):
        self.To = ""
        self.CC = ""
        self.BCC = ""
        self.Subject = ""
        self.HTMLBody = "<sig>Outlook signature</sig>"
        self.Attachments = _FakeAttachments()
        self.display_calls: list[bool] = []

    def Display(self, bring_to_front):
        self.display_calls.append(bool(bring_to_front))


def _install_fake_win32com(monkeypatch, mail_obj: _FakeMail, *, dispatch_raises: bool = False) -> None:
    win32_module = types.ModuleType("win32com")
    client_module = types.ModuleType("win32com.client")

    class _FakeOutlook:
        def CreateItem(self, _kind):
            return mail_obj

    def _dispatch(_name):
        if dispatch_raises:
            raise RuntimeError("dispatch failure")
        return _FakeOutlook()

    client_module.Dispatch = _dispatch
    win32_module.client = client_module
    monkeypatch.setitem(sys.modules, "win32com", win32_module)
    monkeypatch.setitem(sys.modules, "win32com.client", client_module)


def test_create_outlook_draft_dispatches_mac(monkeypatch):
    monkeypatch.setattr(outlook.platform, "system", lambda: "Darwin")
    captured = {}

    def _fake_mac(**kwargs):
        captured.update(kwargs)
        return True

    monkeypatch.setattr(outlook, "_create_outlook_mac", _fake_mac)

    ok = outlook.create_outlook_draft(
        to_list="a@x.com",
        cc_list=["b@x.com"],
        bcc_list=None,
        subject="Sujet",
        body_html="<p>Body</p>",
    )

    assert ok is True
    assert captured["to_list"] == ["a@x.com"]


def test_create_outlook_windows_success_with_signature(monkeypatch):
    mail = _FakeMail()
    _install_fake_win32com(monkeypatch, mail)

    ok = outlook._create_outlook_windows(
        to_list=["a@x.com", "b@x.com"],
        cc_list=["c@x.com"],
        bcc_list=["d@x.com"],
        subject="Planning",
        body_html="<p>Bonjour</p>",
        attachments=["/tmp/a.pdf", "/tmp/b.pdf"],
        use_signature=True,
    )

    assert ok is True
    assert mail.To == "a@x.com; b@x.com"
    assert mail.CC == "c@x.com"
    assert mail.BCC == "d@x.com"
    assert mail.Subject == "Planning"
    assert "<p>Bonjour</p>" in mail.HTMLBody
    assert mail.Attachments.added == ["/tmp/a.pdf", "/tmp/b.pdf"]
    assert mail.display_calls == [True]


def test_create_outlook_windows_without_signature_and_attachment_error(monkeypatch):
    mail = _FakeMail()
    mail.Attachments = _FakeAttachments(fail_paths={"/tmp/bad.pdf"})
    _install_fake_win32com(monkeypatch, mail)

    ok = outlook._create_outlook_windows(
        to_list=["a@x.com"],
        cc_list=[],
        bcc_list=[],
        subject="Planning",
        body_html="<p>Sans signature</p>",
        attachments=["/tmp/good.pdf", "/tmp/bad.pdf"],
        use_signature=False,
    )

    assert ok is True
    assert mail.HTMLBody == "<p>Sans signature</p>"
    assert mail.Attachments.added == ["/tmp/good.pdf"]
    assert mail.display_calls == [True]


def test_create_outlook_windows_returns_false_on_dispatch_error(monkeypatch):
    mail = _FakeMail()
    _install_fake_win32com(monkeypatch, mail, dispatch_raises=True)

    ok = outlook._create_outlook_windows(
        to_list=["a@x.com"],
        cc_list=[],
        bcc_list=[],
        subject="x",
        body_html="<p>x</p>",
        attachments=[],
        use_signature=True,
    )

    assert ok is False


def test_create_outlook_windows_handles_signature_read_error(monkeypatch):
    class _MailWithBadSignature(_FakeMail):
        @property
        def HTMLBody(self):
            raise OSError("signature unavailable")

        @HTMLBody.setter
        def HTMLBody(self, value):
            self._html_value = value

    mail = _MailWithBadSignature()
    _install_fake_win32com(monkeypatch, mail)
    ok = outlook._create_outlook_windows(
        to_list=["a@x.com"],
        cc_list=[],
        bcc_list=[],
        subject="Planning",
        body_html="<p>Body</p>",
        attachments=[],
        use_signature=True,
    )
    assert ok is True
    assert "<p>Body</p>" in getattr(mail, "_html_value", "")


def test_outlook_import_extends_windows_errors_with_pywintypes(monkeypatch):
    module_name = "asf_app.ui.ui_communication.outlook"
    original = sys.modules.get(module_name)

    class _ComError(Exception):
        pass

    fake_pywintypes = types.ModuleType("pywintypes")
    fake_pywintypes.com_error = _ComError
    monkeypatch.setitem(sys.modules, "pywintypes", fake_pywintypes)
    sys.modules.pop(module_name, None)
    try:
        reloaded = importlib.import_module(module_name)
        assert _ComError in reloaded.OUTLOOK_WINDOWS_ERRORS
    finally:
        sys.modules.pop(module_name, None)
        if original is not None:
            sys.modules[module_name] = original
