# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pandas as pd

import asf_app.ui.ui_inputs as ui_inputs


class _Ctx:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        _ = exc_type, exc, tb
        return False


class _StubInputsSt:
    def __init__(self):
        self.session_state: dict[str, object] = {}
        self.infos: list[str] = []
        self.warnings: list[str] = []
        self.successes: list[str] = []
        self.errors: list[str] = []
        self.rerun_called = False
        self._button_values: dict[str, list[bool]] = {}
        self._radio_value_by_label: dict[str, object] = {}
        self._date_value = date(2026, 1, 20)

    def set_button_sequence(self, label: str, values: list[bool]):
        self._button_values[label] = list(values)

    def header(self, *_args, **_kwargs):
        return None

    def subheader(self, *_args, **_kwargs):
        return None

    def write(self, *_args, **_kwargs):
        return None

    def info(self, msg):
        self.infos.append(str(msg))

    def warning(self, msg):
        self.warnings.append(str(msg))

    def success(self, msg):
        self.successes.append(str(msg))

    def error(self, msg):
        self.errors.append(str(msg))

    def columns(self, n, **_kwargs):
        count = len(n) if isinstance(n, (list, tuple)) else int(n)
        return [_Ctx() for _ in range(count)]

    def date_input(self, _label, value=None, **_kwargs):
        _ = value
        return self._date_value

    def button(self, label, **_kwargs):
        seq = self._button_values.get(label)
        if seq:
            return seq.pop(0)
        return False

    def file_uploader(self, *_args, **_kwargs):
        return None

    def selectbox(self, _label, options, index=0, **_kwargs):
        return options[index]

    def radio(self, label, options, index=0, **_kwargs):
        if label in self._radio_value_by_label:
            return self._radio_value_by_label[label]
        return options[index]

    def rerun(self):
        self.rerun_called = True


def test_pick_planning_dates_sets_auto_week_range(monkeypatch):
    stub = _StubInputsSt()
    monkeypatch.setattr(ui_inputs, "st", stub)
    state = SimpleNamespace(api_start_date=None, api_end_date=None)

    ui_inputs.pick_planning_dates(state)

    assert state.api_start_date == date(2026, 1, 20)
    assert state.api_end_date == date(2026, 1, 26)


def test_load_input_dataframes_cloud_mode_skips_empty_files(monkeypatch, tmp_path):
    state = SimpleNamespace(
        tdb_tmp=tmp_path / "tdb.xlsx",
        benev_tmp=tmp_path / "benev.xlsx",
        vols_tmp=tmp_path / "vols.xlsx",
    )
    for p in (state.tdb_tmp, state.benev_tmp, state.vols_tmp):
        p.write_bytes(b"")
    monkeypatch.setattr(ui_inputs, "is_graph_onedrive", lambda: False)
    calls: list[str] = []
    monkeypatch.setattr(ui_inputs, "load_tdb_file", lambda _state: calls.append("tdb"))
    monkeypatch.setattr(ui_inputs, "load_benev_file", lambda _state: calls.append("benev"))
    monkeypatch.setattr(ui_inputs, "load_vols_file", lambda _state: calls.append("vols"))

    ui_inputs._load_input_dataframes(state, cloud_mode=True)
    assert calls == []

    for p in (state.tdb_tmp, state.benev_tmp, state.vols_tmp):
        p.write_bytes(b"x")
    ui_inputs._load_input_dataframes(state, cloud_mode=True)
    assert calls == ["tdb", "benev", "vols"]


def test_render_vols_api_controls_warns_without_period(monkeypatch, tmp_path):
    stub = _StubInputsSt()
    monkeypatch.setattr(ui_inputs, "st", stub)
    monkeypatch.setattr(ui_inputs, "get_api_limits", lambda: (100, 1.1))
    monkeypatch.setattr(ui_inputs, "get_default_time_origin_type", lambda: "P")
    monkeypatch.setattr(ui_inputs, "get_tmp_dir", lambda: tmp_path)
    state = SimpleNamespace(api_start_date=None, api_end_date=None, api_time_origin_type="P", df_vols=None)

    ui_inputs._render_vols_api_controls(state)

    assert any("Sélectionne une période" in msg for msg in stub.warnings)


def test_render_vols_api_controls_api_success(monkeypatch, tmp_path):
    stub = _StubInputsSt()
    stub.set_button_sequence("Appeler l'API Air France", [True])
    monkeypatch.setattr(ui_inputs, "st", stub)
    monkeypatch.setattr(ui_inputs, "get_api_limits", lambda: (100, 1.1))
    monkeypatch.setattr(ui_inputs, "get_default_time_origin_type", lambda: "P")
    monkeypatch.setattr(ui_inputs, "get_tmp_dir", lambda: tmp_path)
    monkeypatch.setattr(
        ui_inputs,
        "load_vols_api",
        lambda *_args, **_kwargs: pd.DataFrame([{"Date_Vol": "20/01/26", "Numero_Vol": "AF100"}]),
    )
    monkeypatch.setattr(ui_inputs, "store_vols_api_sheet", lambda *_args, **_kwargs: "API_S04")
    loaded_sheets: list[str] = []
    monkeypatch.setattr(
        ui_inputs,
        "_try_load_api_sheet_into_tmp_state",
        lambda _state, sheet_name: loaded_sheets.append(sheet_name),
    )
    state = SimpleNamespace(
        api_start_date=date(2026, 1, 19),
        api_end_date=date(2026, 1, 25),
        api_time_origin_type="M",
        df_vols=None,
    )

    ui_inputs._render_vols_api_controls(state)

    assert isinstance(state.df_vols, pd.DataFrame)
    assert not state.df_vols.empty
    assert loaded_sheets == ["API_S04"]
    assert any("vols chargés via API" in msg for msg in stub.successes)


def test_render_vols_panel_routes_to_api_mode(monkeypatch, tmp_path):
    stub = _StubInputsSt()
    stub._radio_value_by_label["Source vols"] = "API Air France (CDG ➜ ParamDest, AF)"
    monkeypatch.setattr(ui_inputs, "st", stub)
    monkeypatch.setattr(ui_inputs, "pretty_mtime", lambda _p: "N/A")
    state = SimpleNamespace(
        vols_tmp=tmp_path / "VOLS.xlsx",
        df_vols=pd.DataFrame([{"Date_Vol": "16/02/26"}]),
        vols_source="excel",
    )
    state.vols_tmp.write_bytes(b"x")
    called = {"api": 0}
    monkeypatch.setattr(ui_inputs, "_render_vols_api_controls", lambda _state: called.__setitem__("api", 1))
    monkeypatch.setattr(ui_inputs, "_render_vols_excel_controls", lambda _state, _cloud: None)

    ui_inputs._render_vols_panel(state, cloud_mode=False)

    assert state.vols_source == "api"
    assert called["api"] == 1


def test_render_tab_inputs_graph_auth_flow(monkeypatch, tmp_path):
    stub = _StubInputsSt()
    stub.set_button_sequence("🔑 Se connecter à OneDrive", [True])
    stub.set_button_sequence("✅ J'ai terminé l'authentification", [True])
    monkeypatch.setattr(ui_inputs, "st", stub)
    monkeypatch.setattr(ui_inputs, "IS_STREAMLIT_CLOUD", True)
    monkeypatch.setattr(ui_inputs, "is_graph_onedrive", lambda: True)
    monkeypatch.setattr(
        ui_inputs.cp,
        "get_graph_client",
        lambda: SimpleNamespace(acquire_token_silent=lambda: None),
    )
    monkeypatch.setattr(
        ui_inputs.cp,
        "begin_onedrive_device_flow",
        lambda: {"message": "code"},
    )
    monkeypatch.setattr(ui_inputs.cp, "complete_onedrive_device_flow", lambda _flow: True)

    state = SimpleNamespace(
        tdb_tmp=tmp_path / "TABLEAU_DE_BORD.xlsx",
        benev_tmp=tmp_path / "PLANNING_BENEVOLES.xlsx",
        vols_tmp=tmp_path / "VOLS.xlsx",
        df_be=None,
        df_param_be=None,
        df_param_dest=None,
        df_benev=None,
        df_param_benev=None,
        df_vols=None,
        vols_source="excel",
        api_start_date=None,
        api_end_date=None,
    )
    for p in (state.tdb_tmp, state.benev_tmp, state.vols_tmp):
        p.write_bytes(b"x")

    monkeypatch.setattr(ui_inputs, "get_state", lambda: state)
    monkeypatch.setattr(ui_inputs, "get_session_context", lambda: None)
    monkeypatch.setattr(
        ui_inputs,
        "ensure_session_context",
        lambda strict_sources=True: SimpleNamespace(
            source_paths=SimpleNamespace(
                tableau_de_bord=state.tdb_tmp,
                planning_benevoles=state.benev_tmp,
                vols=state.vols_tmp,
            )
        ),
    )
    monkeypatch.setattr(ui_inputs, "sync_state_paths_to_engine", lambda _state: None)
    monkeypatch.setattr(ui_inputs, "_load_input_dataframes", lambda _state, _cloud: None)
    monkeypatch.setattr(ui_inputs, "pick_planning_dates", lambda _state: None)
    monkeypatch.setattr(ui_inputs, "_render_tdb_panel", lambda _state, _cloud: None)
    monkeypatch.setattr(ui_inputs, "_render_benev_panel", lambda _state, _cloud: None)
    monkeypatch.setattr(ui_inputs, "_render_vols_panel", lambda _state, _cloud: None)

    ui_inputs.render_tab_inputs()

    assert stub.rerun_called is True
    assert any("Connexion OneDrive validée." in msg for msg in stub.successes)
