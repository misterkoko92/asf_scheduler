# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

import asf_app.ui.ui_week_data as ui_week_data


def test_detect_week_from_vols_dataframe():
    state = SimpleNamespace(df_vols=pd.DataFrame({"Date_Vol": ["23/01/26", "24/01/26"]}))
    assert ui_week_data.detect_week(state) == 4


def test_detect_week_handles_empty_or_missing_columns():
    assert ui_week_data.detect_week(SimpleNamespace(df_vols=None)) is None
    assert ui_week_data.detect_week(SimpleNamespace(df_vols=pd.DataFrame())) is None
    assert ui_week_data.detect_week(SimpleNamespace(df_vols=pd.DataFrame({"X": [1]}))) is None


def test_robust_to_datetime_fallback_when_first_parse_fails(monkeypatch):
    calls = {"count": 0}

    def _fake_parse(series, *args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise TypeError("boom")
        return pd.to_datetime(series, errors="coerce", dayfirst=True)

    monkeypatch.setattr(ui_week_data, "parse_date_series", _fake_parse)

    out = ui_week_data.robust_to_datetime(pd.Series(["23/01/26"]))
    assert calls["count"] == 2
    assert out.notna().all()


def test_load_be_moteur_returns_error_on_loader_failure(monkeypatch, tmp_path):
    state = SimpleNamespace(
        df_param_be=pd.DataFrame([{"A": 1}]),
        tdb_tmp=tmp_path / "TABLEAU_DE_BORD.xlsx",
    )
    monkeypatch.setattr(ui_week_data, "get_state", lambda: state)
    monkeypatch.setattr(
        ui_week_data,
        "load_shipments_df",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("read-fail")),
    )

    df, err = ui_week_data.load_be_moteur()
    assert df is None
    assert "Erreur load_shipments_df" in str(err)


def test_load_be_moteur_success_formats_and_sorts(monkeypatch, tmp_path):
    state = SimpleNamespace(
        df_param_be=pd.DataFrame([{"A": 1}]),
        tdb_tmp=tmp_path / "TABLEAU_DE_BORD.xlsx",
    )
    monkeypatch.setattr(ui_week_data, "get_state", lambda: state)

    raw = pd.DataFrame(
        [
            {
                "BE_Numero": "260002",
                "BE_Type": "MM",
                "Destination": "RUN",
                "BE_Expediteur": "ASF",
                "BE_Nb_Colis": 1,
                "Equiv_Colis": 1,
                "Priorite": 2,
                "BE_Douane": "non",
                "BE_Special": "",
            },
            {
                "BE_Numero": "260001",
                "BE_Type": "FRET",
                "Destination": "DLA",
                "BE_Expediteur": "HIA",
                "BE_Nb_Colis": 3,
                "Equiv_Colis": 4,
                "Priorite": 1,
                "BE_Douane": "oui",
                "BE_Special": "X",
            },
        ]
    )
    monkeypatch.setattr(ui_week_data, "load_shipments_df", lambda *args, **kwargs: raw)

    df, err = ui_week_data.load_be_moteur()
    assert err is None
    assert df is not None
    assert list(df["BE_Numero"]) == ["260001", "260002"]
    assert list(df["Douane"]) == ["OUI", "NON"]
    assert set(["Type", "Destination", "IATA", "Nb_Colis", "Equiv_colis", "Priorité"]).issubset(df.columns)
