# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import asf_app.ui.ui_inputs as ui_inputs


class _StubSt:
    def __init__(self):
        self.session_state: dict[str, object] = {}
        self.errors: list[str] = []
        self.infos: list[str] = []
        self.successes: list[str] = []
        self._button_values: dict[str, list[bool]] = {}
        self.rerun_called = False

    def set_button_sequence(self, label: str, values: list[bool]) -> None:
        self._button_values[label] = list(values)

    def info(self, msg):
        self.infos.append(str(msg))

    def error(self, msg):
        self.errors.append(str(msg))

    def success(self, msg):
        self.successes.append(str(msg))

    def button(self, label, **_kwargs):
        seq = self._button_values.get(label)
        if seq:
            return seq.pop(0)
        return False

    def rerun(self):
        self.rerun_called = True


def test_render_graph_auth_section_when_client_missing(monkeypatch):
    stub = _StubSt()
    monkeypatch.setattr(ui_inputs, "st", stub)
    monkeypatch.setattr(ui_inputs, "is_graph_onedrive", lambda: True)
    monkeypatch.setattr(ui_inputs.cp, "get_graph_client", lambda: None)

    ui_inputs._render_graph_onedrive_auth_section()

    assert any("Graph non configuré" in msg for msg in stub.errors)


def test_render_graph_auth_section_when_token_ready(monkeypatch):
    stub = _StubSt()
    monkeypatch.setattr(ui_inputs, "st", stub)
    monkeypatch.setattr(ui_inputs, "is_graph_onedrive", lambda: True)
    monkeypatch.setattr(
        ui_inputs.cp,
        "get_graph_client",
        lambda: SimpleNamespace(acquire_token_silent=lambda: "token"),
    )

    ui_inputs._render_graph_onedrive_auth_section()

    assert any("Connexion OneDrive active" in msg for msg in stub.successes)


def test_resolve_inputs_session_context_sets_source_error(monkeypatch):
    stub = _StubSt()
    monkeypatch.setattr(ui_inputs, "st", stub)
    monkeypatch.setattr(ui_inputs, "get_session_context", lambda: None)
    monkeypatch.setattr(
        ui_inputs,
        "ensure_session_context",
        lambda strict_sources=True: (_ for _ in ()).throw(FileNotFoundError("missing sources")),
    )

    ctx = ui_inputs._resolve_inputs_session_context()

    assert ctx is None
    assert stub.session_state["source_error"] == "missing sources"


def test_resolve_inputs_session_context_reuses_existing_context(monkeypatch):
    existing = SimpleNamespace(source_paths=SimpleNamespace())
    monkeypatch.setattr(ui_inputs, "get_session_context", lambda: existing)

    ctx = ui_inputs._resolve_inputs_session_context()

    assert ctx is existing


def test_render_inputs_panels_dispatches_three_panels(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(ui_inputs, "_render_tdb_panel", lambda _state, _cloud: calls.append("tdb"))
    monkeypatch.setattr(ui_inputs, "_render_benev_panel", lambda _state, _cloud: calls.append("benev"))
    monkeypatch.setattr(ui_inputs, "_render_vols_panel", lambda _state, _cloud: calls.append("vols"))

    class _Ctx:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            _ = exc_type, exc, tb
            return False

    monkeypatch.setattr(ui_inputs.st, "columns", lambda n: [_Ctx() for _ in range(int(n))])

    ui_inputs._render_inputs_panels(SimpleNamespace(), cloud_mode=False)

    assert calls == ["tdb", "benev", "vols"]


def test_ensure_inputs_tmp_paths_falls_back_to_defaults(monkeypatch, tmp_path):
    monkeypatch.setattr(ui_inputs, "get_tmp_dir", lambda: Path(tmp_path))
    synced: list[bool] = []
    monkeypatch.setattr(ui_inputs, "sync_state_paths_to_engine", lambda _state: synced.append(True))
    state = SimpleNamespace(tdb_tmp=None, benev_tmp=None, vols_tmp=None)

    ui_inputs._ensure_inputs_tmp_paths(state, ctx=None)

    assert state.tdb_tmp.name == "TABLEAU_DE_BORD.xlsx"
    assert state.benev_tmp.name == "PLANNING_BENEVOLES.xlsx"
    assert state.vols_tmp.name == "VOLS.xlsx"
    assert synced == [True]


def test_render_graph_auth_section_noop_when_graph_mode_disabled(monkeypatch):
    stub = _StubSt()
    monkeypatch.setattr(ui_inputs, "st", stub)
    monkeypatch.setattr(ui_inputs, "is_graph_onedrive", lambda: False)
    ui_inputs._render_graph_onedrive_auth_section()
    assert stub.errors == []
    assert stub.successes == []


def test_resolve_inputs_session_context_uses_ensure_when_missing(monkeypatch):
    expected = SimpleNamespace(source_paths=SimpleNamespace())
    monkeypatch.setattr(ui_inputs, "get_session_context", lambda: None)
    monkeypatch.setattr(ui_inputs, "ensure_session_context", lambda strict_sources=True: expected)
    assert ui_inputs._resolve_inputs_session_context() is expected
