# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pandas as pd

import loaders.load_vols_api as load_vols_api_mod


def _paramdest_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Dest_IATA": "DLA", "Dest_Ville": "Douala", "Max_Colis_Par_Vol": 12},
        ]
    )


def test_load_vols_api_passes_time_origin_type(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(load_vols_api_mod, "load_paramdest_codes", lambda: _paramdest_df())
    monkeypatch.setattr(load_vols_api_mod, "load_be_dest_codes", lambda: [])

    def _fake_fetch_multiple(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(load_vols_api_mod, "fetch_multiple", _fake_fetch_multiple)

    df = load_vols_api_mod.load_vols_api(
        date(2026, 1, 23),
        date(2026, 1, 23),
        time_origin_type="S",
    )

    assert captured["time_origin_type"] == "S"
    assert isinstance(df, pd.DataFrame)
    assert df.empty


def test_load_vols_api_maps_flights_to_dataframe(monkeypatch):
    monkeypatch.setattr(load_vols_api_mod, "load_paramdest_codes", lambda: _paramdest_df())
    monkeypatch.setattr(load_vols_api_mod, "load_be_dest_codes", lambda: ["DLA"])
    monkeypatch.setattr(
        load_vols_api_mod,
        "fetch_multiple",
        lambda **kwargs: [
            SimpleNamespace(
                route="CDG-DLA",
                date_depart="23/01/26",
                heure_depart="21h01",
                numero_vol="AF 652",
            )
        ],
    )

    df = load_vols_api_mod.load_vols_api(date(2026, 1, 23), date(2026, 1, 23))

    assert len(df) == 1
    assert df.loc[0, "IATA"] == "DLA"
    assert df.loc[0, "Destination"] == "DOUALA"
    assert df.loc[0, "Numero_Vol"] == "AF 652"
    assert df.loc[0, "Heure_Vol"] == "21h01"
    assert int(df.loc[0, "HEURE_MIN"]) == 21 * 60 + 1
