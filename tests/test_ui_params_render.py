# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd

import asf_app.ui.ui_params as ui_params


class _Ctx:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        _ = exc_type, exc, tb
        return False


class _Col:
    def __init__(self, parent):
        self.parent = parent

    def button(self, label, **kwargs):
        return self.parent.button(label, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        _ = exc_type, exc, tb
        return False


class _SessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


class _StubSt:
    def __init__(self):
        self.session_state = _SessionState()
        self.successes: list[str] = []
        self.rerun_called = False

    def header(self, *_args, **_kwargs):
        return None

    def info(self, *_args, **_kwargs):
        return None

    def divider(self):
        return None

    def markdown(self, *_args, **_kwargs):
        return None

    def caption(self, *_args, **_kwargs):
        return None

    def subheader(self, *_args, **_kwargs):
        return None

    def expander(self, *_args, **_kwargs):
        return _Ctx()

    def text_input(self, _label, value="", **_kwargs):
        return value

    def columns(self, n, **_kwargs):
        return [_Col(self) for _ in range(int(n))]

    def button(self, _label, **_kwargs):
        return False

    def rerun(self):
        self.rerun_called = True

    def form(self, *_args, **_kwargs):
        return _Ctx()

    def selectbox(self, _label, options, index=0, **_kwargs):
        return options[index]

    def number_input(self, _label, min_value=0, value=0, **_kwargs):
        _ = min_value
        return value

    def form_submit_button(self, *_args, **_kwargs):
        return False

    def data_editor(self, df, **_kwargs):
        return df

    def success(self, msg):
        self.successes.append(str(msg))

    def error(self, *_args, **_kwargs):
        return None

    def text_area(self, _label, value="", **_kwargs):
        return value


class _StubStActions(_StubSt):
    def __init__(self):
        super().__init__()
        self.infos: list[str] = []
        self.errors: list[str] = []
        self._button_sequences: dict[str, list[bool]] = {}
        self._text_input_value: str | None = None
        self._edited_df = None

    def set_button_sequence(self, label: str, values: list[bool]):
        self._button_sequences[label] = list(values)

    def button(self, label, **_kwargs):
        seq = self._button_sequences.get(label)
        if seq:
            return seq.pop(0)
        return False

    def text_input(self, _label, value="", **_kwargs):
        if self._text_input_value is not None:
            return self._text_input_value
        return value

    def info(self, msg):
        self.infos.append(str(msg))

    def error(self, msg):
        self.errors.append(str(msg))

    def data_editor(self, df, **_kwargs):
        if self._edited_df is not None:
            return self._edited_df
        return df


def test_render_tab_params_smoke_without_active_block(monkeypatch):
    stub = _StubSt()
    monkeypatch.setattr(ui_params, "st", stub)
    monkeypatch.setattr(ui_params, "get_state", lambda: SimpleNamespace())

    ui_params.render_tab_params()

    assert "active_block" in stub.session_state
    assert stub.session_state["active_block"] is None


def test_render_tab_params_paramoteur_submit_updates_session(monkeypatch):
    stub = _StubSt()
    stub.session_state["active_block"] = "paramoteur"

    def _button(label, **kwargs):
        _ = kwargs
        return False

    stub.button = _button  # type: ignore[method-assign]
    stub.form_submit_button = lambda *_args, **_kwargs: True  # type: ignore[method-assign]

    state = SimpleNamespace()
    monkeypatch.setattr(ui_params, "st", stub)
    monkeypatch.setattr(ui_params, "get_state", lambda: state)

    ui_params.render_tab_params()

    assert hasattr(state, "config_moteur")
    assert stub.session_state.get("solver_version") in {"v2", "v3"}
    assert any("Paramoteur mis à jour" in msg for msg in stub.successes)


def test_render_onedrive_sources_block_applies_override(monkeypatch):
    stub = _StubStActions()
    stub._text_input_value = "/tmp/onedrive-custom"
    stub.set_button_sequence("🔄 Appliquer le chemin OneDrive (session)", [True])
    monkeypatch.setattr(ui_params, "st", stub)
    monkeypatch.setattr(ui_params, "detect_onedrive_asf", lambda: "/tmp/auto")
    monkeypatch.setattr(ui_params, "ASF_ONEDRIVE", "/tmp/current")

    ui_params._render_onedrive_sources_block()

    assert stub.rerun_called is True
    assert any("surchargé" in msg for msg in stub.successes)


def test_render_param_table_block_validate_and_error(monkeypatch):
    stub = _StubStActions()
    stub.set_button_sequence("💾 Valider ParamDest", [True])
    monkeypatch.setattr(ui_params, "st", stub)
    state = SimpleNamespace(df_param_dest=None, tdb_tmp="tdb.xlsx")
    df_source = pd.DataFrame([{"a": 1}])
    stub._edited_df = pd.DataFrame([{"a": 2}])
    monkeypatch.setattr(ui_params, "load_param_df", lambda *_args, **_kwargs: df_source)

    ui_params._render_param_table_block(
        state=state,
        state_attr="df_param_dest",
        source_path=Path("tdb.xlsx"),
        sheet_name="ParamDest",
        mapping={},
        title="ParamDest",
        validate_label="💾 Valider ParamDest",
        success_label="OK",
        error_label="ParamDest",
    )
    assert int(state.df_param_dest.iloc[0]["a"]) == 2
    assert any("OK" in msg for msg in stub.successes)

    monkeypatch.setattr(
        ui_params,
        "load_param_df",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ui_params.InputLoadError("boom")),
    )
    ui_params._render_param_table_block(
        state=state,
        state_attr="df_param_dest",
        source_path=Path("tdb.xlsx"),
        sheet_name="ParamDest",
        mapping={},
        title="ParamDest",
        validate_label="💾 Valider ParamDest",
        success_label="OK",
        error_label="ParamDest",
    )
    assert any("Erreur ParamDest" in msg for msg in stub.errors)


def test_render_paramail_block_session_and_persist(monkeypatch):
    stub = _StubStActions()
    stub.set_button_sequence("✅ Valider cette session uniquement", [True])
    stub.set_button_sequence("💾 Valider en dur", [True])
    monkeypatch.setattr(ui_params, "st", stub)
    monkeypatch.setattr(
        ui_params,
        "get_email_defaults",
        lambda: {
            "airfrance": {"to": "a@x.com", "cc": "", "bcc": ""},
            "asf_interne": {"to": "b@x.com", "cc": "", "bcc": ""},
        },
    )
    calls: list[bool] = []
    monkeypatch.setattr(ui_params, "set_email_defaults", lambda _payload, persist=False: calls.append(bool(persist)))

    ui_params._render_paramail_block()

    assert calls == [False, True]
    assert any("session" in msg.lower() for msg in stub.successes)
