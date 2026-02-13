# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

import yaml

from asf_app.config import email_defaults as cfg_email_defaults
from asf_app.ui import email_defaults as ui_email_defaults


def test_coerce_emails_variants():
    assert cfg_email_defaults._coerce_emails(None) == ""
    assert cfg_email_defaults._coerce_emails(" a@b.com ") == "a@b.com"
    assert cfg_email_defaults._coerce_emails(["a@b.com", "", "c@d.com"]) == "a@b.com; c@d.com"
    assert cfg_email_defaults._coerce_emails(("x@y.com", " z@w.com ")) == "x@y.com; z@w.com"


def test_normalize_email_defaults_with_partial_payload():
    normalized = cfg_email_defaults.normalize_email_defaults(
        {
            "airfrance": {"to": ["a@b.com", "c@d.com"], "cc": None},
            "asf_interne": "invalid",
        }
    )
    assert normalized["airfrance"]["to"] == "a@b.com; c@d.com"
    assert normalized["airfrance"]["cc"] == ""
    assert normalized["asf_interne"] == cfg_email_defaults.DEFAULT_EMAIL_DEFAULTS["asf_interne"]


def test_load_email_defaults_missing_file_returns_defaults(tmp_path, monkeypatch):
    file_path = tmp_path / "missing_email_defaults.yml"
    monkeypatch.setattr(cfg_email_defaults, "EMAIL_DEFAULTS_PATH", file_path)
    defaults = cfg_email_defaults.load_email_defaults()
    assert defaults == cfg_email_defaults.DEFAULT_EMAIL_DEFAULTS


def test_load_email_defaults_reads_yaml_and_normalizes(tmp_path, monkeypatch):
    file_path = tmp_path / "email_defaults.yml"
    file_path.write_text(
        yaml.safe_dump(
            {
                "airfrance": {"to": ["x@y.com", "z@w.com"], "cc": "c@d.com", "bcc": None},
                "asf_interne": {"to": "asf@x.com", "cc": "", "bcc": ""},
            },
            allow_unicode=False,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(cfg_email_defaults, "EMAIL_DEFAULTS_PATH", file_path)
    loaded = cfg_email_defaults.load_email_defaults()
    assert loaded["airfrance"]["to"] == "x@y.com; z@w.com"
    assert loaded["airfrance"]["bcc"] == ""
    assert loaded["asf_interne"]["to"] == "asf@x.com"


def test_load_email_defaults_on_yaml_error_falls_back(tmp_path, monkeypatch):
    file_path = tmp_path / "email_defaults.yml"
    file_path.write_text("airfrance: [", encoding="utf-8")
    monkeypatch.setattr(cfg_email_defaults, "EMAIL_DEFAULTS_PATH", file_path)

    def _boom(_f):
        raise yaml.YAMLError("bad yaml")

    monkeypatch.setattr(cfg_email_defaults.yaml, "safe_load", _boom)
    loaded = cfg_email_defaults.load_email_defaults()
    assert loaded == cfg_email_defaults.DEFAULT_EMAIL_DEFAULTS


def test_save_email_defaults_writes_normalized_yaml(tmp_path, monkeypatch):
    file_path = tmp_path / "nested" / "email_defaults.yml"
    monkeypatch.setattr(cfg_email_defaults, "EMAIL_DEFAULTS_PATH", file_path)
    cfg_email_defaults.save_email_defaults(
        {
            "airfrance": {"to": ["a@b.com", "c@d.com"], "cc": "", "bcc": None},
            "asf_interne": {"to": "asf@x.com", "cc": "", "bcc": "hidden@x.com"},
        }
    )

    payload = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    assert payload["airfrance"]["to"] == "a@b.com; c@d.com"
    assert payload["airfrance"]["bcc"] == ""
    assert payload["asf_interne"]["bcc"] == "hidden@x.com"


def test_ui_get_email_defaults_reads_cache_then_loader(monkeypatch):
    fake_st = SimpleNamespace(session_state={})
    monkeypatch.setattr(ui_email_defaults, "st", fake_st)
    monkeypatch.setattr(
        ui_email_defaults,
        "load_email_defaults",
        lambda: {"airfrance": {"to": "x", "cc": "", "bcc": ""}, "asf_interne": {"to": "y", "cc": "", "bcc": ""}},
    )

    first = ui_email_defaults.get_email_defaults()
    second = ui_email_defaults.get_email_defaults()
    assert first == second
    assert fake_st.session_state["email_defaults"]["airfrance"]["to"] == "x"


def test_ui_get_email_defaults_without_streamlit(monkeypatch):
    monkeypatch.setattr(ui_email_defaults, "st", None)
    monkeypatch.setattr(
        ui_email_defaults,
        "load_email_defaults",
        lambda: {"airfrance": {"to": "a", "cc": "", "bcc": ""}, "asf_interne": {"to": "b", "cc": "", "bcc": ""}},
    )
    out = ui_email_defaults.get_email_defaults()
    assert out["airfrance"]["to"] == "a"


def test_ui_set_email_defaults_updates_session_and_persists(monkeypatch):
    fake_st = SimpleNamespace(session_state={})
    monkeypatch.setattr(ui_email_defaults, "st", fake_st)
    saved: dict[str, dict] = {}

    def _save(payload: dict) -> None:
        saved["payload"] = payload

    monkeypatch.setattr(ui_email_defaults, "save_email_defaults", _save)
    out = ui_email_defaults.set_email_defaults(
        {
            "airfrance": {"to": "af@x.com", "cc": "", "bcc": ""},
            "asf_interne": {"to": "asf@x.com", "cc": "", "bcc": ""},
        },
        persist=True,
    )
    assert out["airfrance"]["to"] == "af@x.com"
    assert saved["payload"]["airfrance"]["to"] == "af@x.com"
    assert fake_st.session_state["airfrance_to"] == "af@x.com"
    assert fake_st.session_state["asf_to"] == "asf@x.com"


def test_ui_set_email_defaults_without_streamlit(monkeypatch):
    monkeypatch.setattr(ui_email_defaults, "st", None)
    out = ui_email_defaults.set_email_defaults({"airfrance": {}, "asf_interne": {}}, persist=False)
    assert isinstance(out, dict)
    assert set(out.keys()) == {"airfrance", "asf_interne"}
