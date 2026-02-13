# -*- coding: utf-8 -*-
from __future__ import annotations

from asf_app.ui.ui_communication import email_airfrance_handler as airfrance
from asf_app.ui.ui_communication import email_asf_handler as asf


def test_build_subject_helpers():
    assert airfrance.build_subject_airfrance(3, 2026) == "Aviation Sans Frontires / Planning S3"
    assert asf.build_subject_asf(3, 2026) == "Planning SEMAINE 3 - 2026"


def test_generate_airfrance_email_uses_defaults(monkeypatch):
    captured = {}

    def fake_create_outlook_draft(**kwargs):
        captured.update(kwargs)
        return True

    monkeypatch.setattr(airfrance, "create_outlook_draft", fake_create_outlook_draft)

    result = airfrance.generate_airfrance_email(
        to_list=["ops@example.org"],
        cc_list=["cc@example.org"],
        bcc_list=["bcc@example.org"],
        week=4,
        year=2026,
        attachments=[],
    )

    assert result is True
    assert captured["subject"] == "Aviation Sans Frontires / Planning S4"
    assert "semaine 4" in captured["body_html"]
    assert captured["to_list"] == ["ops@example.org"]
    assert captured["cc_list"] == ["cc@example.org"]
    assert captured["bcc_list"] == ["bcc@example.org"]
    assert captured["attachments"] is None
    assert captured["use_signature"] is True


def test_generate_asf_email_uses_custom_values(monkeypatch):
    captured = {}

    def fake_create_outlook_draft(**kwargs):
        captured.update(kwargs)
        return "ok"

    monkeypatch.setattr(asf, "create_outlook_draft", fake_create_outlook_draft)

    result = asf.generate_asf_email(
        to_list=["asf@example.org"],
        bcc_list=["blind@example.org"],
        cc_list=["copy@example.org"],
        week=5,
        year=2026,
        custom_subject="Sujet custom",
        custom_body="<b>Body</b>",
        attachments=["/tmp/demo.pdf"],
    )

    assert result == "ok"
    assert captured["subject"] == "Sujet custom"
    assert captured["body_html"] == "<b>Body</b>"
    assert captured["to_list"] == ["asf@example.org"]
    assert captured["cc_list"] == ["copy@example.org"]
    assert captured["bcc_list"] == ["blind@example.org"]
    assert captured["attachments"] == ["/tmp/demo.pdf"]
    assert captured["use_signature"] is True
