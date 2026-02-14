# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

import asf_app.ui.ui_manual as ui_manual
import asf_app.ui.ui_params as ui_params


class _Ctx:
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


class _ParamCol(_Ctx):
    def __init__(self, parent):
        self.parent = parent

    def button(self, label, **kwargs):
        return self.parent.button(label, **kwargs)


class _ParamStubSt:
    def __init__(self):
        self.session_state = _SessionState()
        self._button_sequences: dict[str, list[bool]] = {}
        self._text_input_value = ""
        self.infos: list[str] = []
        self.errors: list[str] = []
        self.successes: list[str] = []
        self.rerun_called = False

    def set_button_sequence(self, label: str, values: list[bool]):
        self._button_sequences[str(label)] = list(values)

    def _consume_button(self, label: str) -> bool:
        seq = self._button_sequences.get(str(label))
        if seq:
            return bool(seq.pop(0))
        return False

    def header(self, *_args, **_kwargs):
        return None

    def info(self, msg):
        self.infos.append(str(msg))

    def error(self, msg):
        self.errors.append(str(msg))

    def success(self, msg):
        self.successes.append(str(msg))

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

    def columns(self, n, **_kwargs):
        return [_ParamCol(self) for _ in range(int(n))]

    def text_input(self, _label, value="", **_kwargs):
        if self._text_input_value != "":
            return self._text_input_value
        return value

    def button(self, label, **_kwargs):
        return self._consume_button(str(label))

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

    def text_area(self, _label, value="", **_kwargs):
        return value


def test_ui_params_onedrive_empty_override_and_toggle(monkeypatch):
    stub = _ParamStubSt()
    stub._text_input_value = "   "
    stub.set_button_sequence("🔄 Appliquer le chemin OneDrive (session)", [True])
    monkeypatch.setattr(ui_params, "st", stub)
    monkeypatch.setattr(ui_params, "detect_onedrive_asf", lambda: "/tmp/auto")
    monkeypatch.setattr(ui_params, "ASF_ONEDRIVE", "/tmp/current")

    ui_params._render_onedrive_sources_block()
    assert any("Aucun chemin saisi" in msg for msg in stub.infos)
    assert stub.rerun_called is False

    ui_params._toggle_active_block("paramdest")
    assert stub.session_state.get("active_block") == "paramdest"
    ui_params._toggle_active_block("paramdest")
    assert stub.session_state.get("active_block") is None


def test_ui_params_block_selector_covers_all_buttons(monkeypatch):
    stub = _ParamStubSt()
    for label in [
        "⚙️ Paramoteur",
        "🗂️ ParamDest",
        "📦 ParamBE",
        "👥 ParamBenev",
        "✉️ ParaMail",
    ]:
        stub.set_button_sequence(label, [True])
    monkeypatch.setattr(ui_params, "st", stub)

    out = ui_params._render_block_selector()

    assert out == "paramail"
    assert stub.session_state.get("active_block") == "paramail"


def test_render_tab_params_dispatches_all_blocks(monkeypatch):
    stub = _ParamStubSt()
    monkeypatch.setattr(ui_params, "st", stub)
    monkeypatch.setattr(
        ui_params,
        "get_state",
        lambda: SimpleNamespace(tdb_tmp="TABLEAU_DE_BORD.xlsx", benev_tmp="PLANNING_BENEVOLES.xlsx"),
    )
    monkeypatch.setattr(ui_params, "_render_onedrive_sources_block", lambda: None)

    calls: list[str] = []
    monkeypatch.setattr(
        ui_params,
        "_render_param_table_block",
        lambda **kwargs: calls.append(str(kwargs.get("state_attr", ""))),
    )
    monkeypatch.setattr(ui_params, "_render_paramail_block", lambda: calls.append("paramail"))

    for active in ["paramdest", "parambe", "parambenev", "paramail"]:
        monkeypatch.setattr(ui_params, "_render_block_selector", lambda active=active: active)
        ui_params.render_tab_params()

    assert "df_param_dest" in calls
    assert "df_param_be" in calls
    assert "df_param_benev" in calls
    assert "paramail" in calls


class _ManualColumnConfig:
    @staticmethod
    def NumberColumn(*_args, **_kwargs):
        return {}

    @staticmethod
    def TextColumn(*_args, **_kwargs):
        return {}


class _ManualStubSt:
    def __init__(self):
        self._buttons: dict[str, bool] = {}
        self.successes: list[str] = []
        self.errors: list[str] = []
        self._selected_bene = "ALICE DUPONT"
        self.column_config = _ManualColumnConfig()

    def header(self, *_args, **_kwargs):
        return None

    def caption(self, *_args, **_kwargs):
        return None

    def expander(self, *_args, **_kwargs):
        return _Ctx()

    def selectbox(self, label, options, **_kwargs):
        if "bénévole" in str(label).lower():
            return self._selected_bene if self._selected_bene in options else (options[0] if options else None)
        return options[0] if options else None

    def data_editor(self, df, **_kwargs):
        return df.copy()

    def button(self, label, **_kwargs):
        return bool(self._buttons.get(str(label), False))

    def success(self, msg):
        self.successes.append(str(msg))

    def error(self, msg):
        self.errors.append(str(msg))

    def stop(self):
        raise RuntimeError("st.stop called")


def _manual_state(tmp_path: Path):
    return SimpleNamespace(
        benev_tmp=str(tmp_path / "PLANNING_BENEVOLES.xlsx"),
        vols_tmp=str(tmp_path / "VOLS.xlsx"),
        tdb_tmp=str(tmp_path / "TABLEAU_DE_BORD.xlsx"),
        df_param_benev=None,
        df_benev=None,
        df_vols=None,
        df_be=None,
    )


def _manual_load_df(path, sheet, mapping, header=0):
    _ = path, mapping, header
    if sheet == ui_manual.SHEET_PARAM_BENEV:
        return pd.DataFrame([{"Benevole": "ALICE DUPONT"}])
    if sheet == ui_manual.SHEET_BENEV_DISPO:
        return pd.DataFrame(
            [
                {
                    "Benevole": "ALICE DUPONT",
                    "Date": "2026-02-16",
                    "Heure_Arrivee": "bad",
                    "Heure_Depart": "13:00",
                    "Heure_Arrivee_time": "bad",
                    "Heure_Depart_time": "13:00",
                }
            ]
        )
    if sheet == ui_manual.SHEET_VOLS:
        return pd.DataFrame([{"Numero_Vol": "AF 822", "Date_Vol": "16/02/26"}])
    if sheet == ui_manual.SHEET_MAG_CENTRAL:
        return pd.DataFrame([{"BE_Numero": "260001", "Destination": "DLA"}])
    return pd.DataFrame()


def test_ui_manual_dispo_save_handles_invalid_time_values(monkeypatch, tmp_path):
    stub = _ManualStubSt()
    stub._buttons["💾 Enregistrer disponibilités"] = True
    monkeypatch.setattr(ui_manual, "st", stub)
    state = _manual_state(tmp_path)
    monkeypatch.setattr(ui_manual, "get_state", lambda: state)
    monkeypatch.setattr(ui_manual, "load_df", _manual_load_df)
    monkeypatch.setattr(ui_manual, "write_excel_sheet", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(ui_manual, "sync_state_paths_to_engine", lambda _s: None)

    ui_manual.render_tab_manual()

    assert any("Disponibilités enregistrées" in msg for msg in stub.successes)
    assert state.df_benev is not None


def test_ui_manual_stops_when_vols_write_fails(monkeypatch, tmp_path):
    stub = _ManualStubSt()
    stub._buttons["💾 Enregistrer vols"] = True
    monkeypatch.setattr(ui_manual, "st", stub)
    state = _manual_state(tmp_path)
    monkeypatch.setattr(ui_manual, "get_state", lambda: state)
    monkeypatch.setattr(ui_manual, "load_df", _manual_load_df)
    monkeypatch.setattr(
        ui_manual,
        "write_excel_sheet",
        lambda _path, sheet, _df: sheet != ui_manual.SHEET_VOLS,
    )

    with pytest.raises(RuntimeError, match="st.stop called"):
        ui_manual.render_tab_manual()


def test_ui_manual_stops_when_be_write_fails(monkeypatch, tmp_path):
    stub = _ManualStubSt()
    stub._buttons["💾 Enregistrer BE"] = True
    monkeypatch.setattr(ui_manual, "st", stub)
    state = _manual_state(tmp_path)
    monkeypatch.setattr(ui_manual, "get_state", lambda: state)
    monkeypatch.setattr(ui_manual, "load_df", _manual_load_df)
    monkeypatch.setattr(
        ui_manual,
        "write_excel_sheet",
        lambda _path, sheet, _df: sheet != ui_manual.SHEET_MAG_CENTRAL,
    )

    with pytest.raises(RuntimeError, match="st.stop called"):
        ui_manual.render_tab_manual()
