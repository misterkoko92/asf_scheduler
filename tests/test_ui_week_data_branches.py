# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

import asf_app.ui.ui_week_data as ui_week_data


class _Ctx:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        _ = exc_type, exc, tb
        return False


class _StubWeekSt:
    def __init__(self):
        self.errors: list[str] = []
        self.infos: list[str] = []
        self.dataframe_calls = 0

    def header(self, *_args, **_kwargs):
        return None

    def subheader(self, *_args, **_kwargs):
        return None

    def columns(self, n, **_kwargs):
        _ = _kwargs
        return [_Ctx() for _ in range(int(n))]

    def error(self, msg):
        self.errors.append(str(msg))

    def info(self, msg):
        self.infos.append(str(msg))

    def expander(self, *_args, **_kwargs):
        return _Ctx()

    def dataframe(self, *_args, **_kwargs):
        self.dataframe_calls += 1
        return None

    def container(self):
        return _Ctx()

    def markdown(self, *_args, **_kwargs):
        return None

    def selectbox(self, _label, options, index=0, **_kwargs):
        return options[index]

    def data_editor(self, df, **_kwargs):
        _ = _kwargs
        return df


def test_detect_week_returns_none_when_dates_are_invalid():
    state = SimpleNamespace(df_vols=pd.DataFrame({"Date_Vol": ["invalid", None]}))
    assert ui_week_data.detect_week(state) is None


def test_load_be_moteur_handles_parambe_missing_and_empty_loader(monkeypatch, tmp_path):
    state_no_param = SimpleNamespace(df_param_be=pd.DataFrame(), tdb_tmp=tmp_path / "TABLEAU_DE_BORD.xlsx")
    monkeypatch.setattr(ui_week_data, "get_state", lambda: state_no_param)
    df, err = ui_week_data.load_be_moteur()
    assert df is None
    assert err == "ParamBE indisponible"

    state_param = SimpleNamespace(df_param_be=pd.DataFrame([{"A": 1}]), tdb_tmp=tmp_path / "TABLEAU_DE_BORD.xlsx")
    monkeypatch.setattr(ui_week_data, "get_state", lambda: state_param)
    monkeypatch.setattr(ui_week_data, "load_shipments_df", lambda *_a, **_k: pd.DataFrame())
    df2, err2 = ui_week_data.load_be_moteur()
    assert df2 is None
    assert err2 == "Aucun BE moteur"


def test_prepare_be_and_benevoles_dataframe_handle_empty_inputs():
    assert ui_week_data._prepare_be_display_dataframe(None, iata_to_city={}).empty
    state = SimpleNamespace(df_benev=pd.DataFrame(), api_start_date=None, api_end_date=None)
    assert ui_week_data._prepare_benevoles_dataframe(state, week=8).empty


def test_prepare_flights_dataframe_handles_invalid_rows_and_loop_exceptions(monkeypatch):
    state = SimpleNamespace(
        df_vols=pd.DataFrame(
            [
                {"Date_Vol": "invalid", "Heure_Vol": "11h00", "Routing": "CDG-DLA", "Numero_Vol": "AF100", "Source": "excel"},
                {"Date_Vol": "16/02/26", "Heure_Vol": "", "Routing": "CDG-DLA", "Numero_Vol": "AF101", "Source": "excel"},
                {"Date_Vol": "16/02/26", "Heure_Vol": "11h00", "Routing": "CDG", "Numero_Vol": "AF102", "Source": "excel"},
                {
                    "Date_Vol": "16/02/26",
                    "Heure_Vol": "11h00",
                    "Routing": "CDG-DLA-CDG",
                    "Numero_Vol": "AF822",
                    "Source": "api",
                },
            ]
        ),
        df_param_dest=pd.DataFrame(),
        df_be=object(),
        api_start_date=None,
        api_end_date=None,
    )

    monkeypatch.setattr(ui_week_data, "load_be_moteur", lambda: (None, None))

    out = ui_week_data._prepare_flights_dataframe(state, week=8, iata_to_city={"DLA": "DOUALA"})

    assert len(out) == 1
    assert out.iloc[0]["IATA"] == "DLA"
    assert out.iloc[0]["Routing"] == "CDG-DLA"
    assert out.iloc[0]["Destination"] == "DOUALA"


def test_render_tab_week_data_executes_stylers_and_be_error_branch(monkeypatch):
    stub = _StubWeekSt()
    monkeypatch.setattr(ui_week_data, "st", stub)
    monkeypatch.setattr(ui_week_data, "detect_week", lambda _state: 8)
    monkeypatch.setattr(ui_week_data, "build_iata_city_maps", lambda _df: ({}, {}))
    monkeypatch.setattr(ui_week_data, "load_be_moteur", lambda: (None, "boom"))
    monkeypatch.setattr(ui_week_data, "bloc_with_sort", lambda *_a, **_k: None)
    monkeypatch.setattr(
        ui_week_data,
        "_prepare_benevoles_dataframe",
        lambda *_a, **_k: pd.DataFrame([{"Nom": "A", "Date": "16/02/26", "Arrivée": "11h00", "Départ": "13h00"}]),
    )
    monkeypatch.setattr(
        ui_week_data,
        "_prepare_flights_dataframe",
        lambda *_a, **_k: pd.DataFrame([{"Destination": "DLA", "Date": "16/02/26", "Heure": "11h00"}]),
    )
    monkeypatch.setattr(ui_week_data, "_compute_week_dates", lambda **_k: [pd.Timestamp("2026-02-16")])
    monkeypatch.setattr(ui_week_data, "_build_day_labels", lambda _dates: ["lundi 16/02"])
    monkeypatch.setattr(
        ui_week_data,
        "_build_benev_week_table",
        lambda *_a, **_k: (
            pd.DataFrame({("lundi 16/02", "Début"): ["11h00"], ("lundi 16/02", "Fin"): ["13h00"]}, index=["A (1)"]),
            pd.DataFrame({("lundi 16/02", "Début"): [True], ("lundi 16/02", "Fin"): [True]}, index=["A (1)"]),
        ),
    )
    monkeypatch.setattr(ui_week_data, "_build_benev_ranges_by_date", lambda *_a, **_k: {})
    monkeypatch.setattr(
        ui_week_data,
        "_build_flights_week_table",
        lambda *_a, **_k: (
            pd.DataFrame({"lundi 16/02": ["11h00 - AF 822 - DLA"]}, index=["DLA (1)"]),
            pd.DataFrame({"lundi 16/02": ["compatible"]}, index=["DLA (1)"]),
        ),
    )

    state = SimpleNamespace(
        api_start_date=None,
        api_end_date=None,
        df_param_dest=pd.DataFrame(),
        df_be=pd.DataFrame(),
        df_benev=pd.DataFrame(),
        df_vols=pd.DataFrame(),
    )
    monkeypatch.setattr(ui_week_data, "get_state", lambda: state)

    ui_week_data.render_tab_week_data()

    assert any("Erreur BE moteur : boom" in msg for msg in stub.errors)
    assert stub.dataframe_calls >= 2
