# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

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
