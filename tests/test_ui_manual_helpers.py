# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from asf_app.ui import ui_manual


def test_load_df_resets_index(monkeypatch):
    monkeypatch.setattr(
        ui_manual,
        "load_normalized_sheet",
        lambda **kwargs: pd.DataFrame([{"x": 1}], index=[5]),
    )

    out = ui_manual.load_df(Path("x.xlsx"), "Sheet1", {}, header=0)

    assert list(out.index) == [0]
    assert out.iloc[0]["x"] == 1


def test_write_excel_sheet_success(monkeypatch):
    called = {"ok": False}

    monkeypatch.setattr(
        ui_manual,
        "save_excel_sheet",
        lambda path, sheet_name, df: called.__setitem__("ok", True),
    )

    ok = ui_manual.write_excel_sheet(Path("x.xlsx"), "Sheet1", pd.DataFrame([{"a": 1}]))

    assert ok is True
    assert called["ok"] is True


def test_write_excel_sheet_error(monkeypatch):
    errors: list[str] = []

    def _raise(*args, **kwargs):
        raise OSError("disk error")

    monkeypatch.setattr(ui_manual, "save_excel_sheet", _raise)
    monkeypatch.setattr(ui_manual.st, "error", lambda msg: errors.append(str(msg)))

    ok = ui_manual.write_excel_sheet(Path("x.xlsx"), "Sheet1", pd.DataFrame([{"a": 1}]))

    assert ok is False
    assert errors and "Erreur écriture Excel" in errors[0]


class _Ctx:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        _ = exc_type, exc, tb
        return False


class _ColumnConfig:
    @staticmethod
    def NumberColumn(*_args, **_kwargs):
        return {}

    @staticmethod
    def TextColumn(*_args, **_kwargs):
        return {}


class _StubManualSt:
    def __init__(self):
        self.successes: list[str] = []
        self.errors: list[str] = []
        self._buttons: dict[str, bool] = {}
        self._selected_bene = "ALICE DUPONT"
        self.column_config = _ColumnConfig()

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


def _build_manual_state(tmp_path: Path):
    return SimpleNamespace(
        benev_tmp=str(tmp_path / "PLANNING_BENEVOLES.xlsx"),
        vols_tmp=str(tmp_path / "VOLS.xlsx"),
        tdb_tmp=str(tmp_path / "TABLEAU_DE_BORD.xlsx"),
        df_param_benev=None,
        df_benev=None,
        df_vols=None,
        df_be=None,
    )


def test_render_tab_manual_saves_all_sections(monkeypatch, tmp_path):
    stub = _StubManualSt()
    stub._buttons["💾 Enregistrer disponibilités"] = True
    stub._buttons["💾 Enregistrer vols"] = True
    stub._buttons["💾 Enregistrer BE"] = True
    monkeypatch.setattr(ui_manual, "st", stub)
    state = _build_manual_state(tmp_path)
    monkeypatch.setattr(ui_manual, "get_state", lambda: state)

    def _fake_load_df(path, sheet, mapping, header=0):
        _ = path, mapping, header
        if sheet == ui_manual.SHEET_PARAM_BENEV:
            return pd.DataFrame([{"Benevole": "ALICE DUPONT"}])
        if sheet == ui_manual.SHEET_BENEV_DISPO:
            return pd.DataFrame(
                [
                    {
                        "Benevole": "ALICE DUPONT",
                        "Date": "2026-02-16",
                        "Heure_Arrivee": "11:00",
                        "Heure_Depart": "13:00",
                    }
                ]
            )
        if sheet == ui_manual.SHEET_VOLS:
            return pd.DataFrame([{"Numero_Vol": "AF 822", "Date_Vol": "16/02/26"}])
        if sheet == ui_manual.SHEET_MAG_CENTRAL:
            return pd.DataFrame([{"BE_Numero": "260001", "Destination": "DLA"}])
        return pd.DataFrame()

    monkeypatch.setattr(ui_manual, "load_df", _fake_load_df)
    writes: list[str] = []
    monkeypatch.setattr(
        ui_manual,
        "write_excel_sheet",
        lambda _p, sheet, _df: writes.append(str(sheet)) or True,
    )
    sync_calls = {"count": 0}
    monkeypatch.setattr(ui_manual, "sync_state_paths_to_engine", lambda _s: sync_calls.__setitem__("count", sync_calls["count"] + 1))

    ui_manual.render_tab_manual()

    assert ui_manual.SHEET_BENEV_DISPO in writes
    assert ui_manual.SHEET_VOLS in writes
    assert ui_manual.SHEET_MAG_CENTRAL in writes
    assert sync_calls["count"] == 3
    assert len(stub.successes) >= 3
    # heure arrivée recalculée -3h
    assert str(state.df_benev.iloc[0]["Heure_Arrivee"]).startswith("08:00")


def test_render_tab_manual_stops_when_write_fails(monkeypatch, tmp_path):
    stub = _StubManualSt()
    stub._buttons["💾 Enregistrer disponibilités"] = True
    monkeypatch.setattr(ui_manual, "st", stub)
    state = _build_manual_state(tmp_path)
    monkeypatch.setattr(ui_manual, "get_state", lambda: state)
    monkeypatch.setattr(
        ui_manual,
        "load_df",
        lambda _p, sheet, _m, header=0: (
            pd.DataFrame([{"Benevole": "ALICE DUPONT"}])
            if sheet == ui_manual.SHEET_PARAM_BENEV
            else pd.DataFrame(
                [
                    {
                        "Benevole": "ALICE DUPONT",
                        "Date": "2026-02-16",
                        "Heure_Arrivee": "11:00",
                        "Heure_Depart": "13:00",
                    }
                ]
            )
        ),
    )
    monkeypatch.setattr(ui_manual, "write_excel_sheet", lambda *_args, **_kwargs: False)

    try:
        ui_manual.render_tab_manual()
    except RuntimeError as exc:
        assert "st.stop called" in str(exc)
    else:
        raise AssertionError("render_tab_manual should stop when write fails")


def test_render_tab_manual_reports_missing_tmp_paths(monkeypatch):
    stub = _StubManualSt()
    monkeypatch.setattr(ui_manual, "st", stub)
    state = SimpleNamespace(
        benev_tmp=None,
        vols_tmp=None,
        tdb_tmp=None,
        df_param_benev=None,
        df_benev=None,
        df_vols=None,
        df_be=None,
    )
    monkeypatch.setattr(ui_manual, "get_state", lambda: state)

    ui_manual.render_tab_manual()

    assert stub.errors
    assert "Chemins TMP non initialisés" in stub.errors[0]
