# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import date, time
from pathlib import Path

import pandas as pd

import loaders.load_vols as lv


class _BadHeadDataFrame(pd.DataFrame):
    @property
    def _constructor(self):
        return _BadHeadDataFrame

    def head(self, *_args, **_kwargs):
        raise TypeError("preview failed")


def test_load_vols_handles_debug_preview_error_and_api_row_edge_cases(monkeypatch, tmp_path):
    monkeypatch.setattr(
        lv,
        "load_and_normalize",
        lambda **_kwargs: _BadHeadDataFrame(
            [
                {
                    "Numero_Vol": "AF900",
                    "Date_Vol": "16/02/26",
                    "Heure_Vol": "09:00",
                    "Destination_Nom": "DOUALA",
                    "Route_API": "CDG-DLA",
                }
            ]
        ),
    )

    api_rows = pd.DataFrame(
        [
            # Numero_Vol manquant -> skip
            {"Date": "16/02/26", "Heure": "11:00", "Numéro": "", "Routing": "CDG-DLA", "Max_Colis": "40"},
            # Date invalide -> skip
            {"Date": "not-a-date", "Heure": "11:00", "Numéro": "AF100", "Routing": "CDG-DLA", "Max_Colis": "40"},
            # Trailing CDG + capacité invalide
            {"Date": "16/02/26", "Heure": "11:00", "Numéro": "AF101", "Routing": "CDG-DLA-CDG", "Max_Colis": "bad"},
            # Routing trop court -> skip
            {"Date": "16/02/26", "Heure": "11:00", "Numéro": "AF102", "Routing": "CDG", "Max_Colis": "30"},
        ]
    )
    monkeypatch.setattr(
        lv.pd,
        "read_excel",
        lambda *_a, **_k: {
            "API-EMPTY": pd.DataFrame(),
            "API-S04-2026": api_rows,
            "OTHER": pd.DataFrame([{"x": 1}]),
        },
    )
    monkeypatch.setattr(lv, "warn_ui", lambda *_a, **_k: None)

    param_dest = pd.DataFrame(
        [
            {"Dest_Ville": "DOUALA", "Dest_IATA": "DLA", "Max_Colis_Par_Vol": 20},
        ]
    )

    out = lv.load_vols(vols_path=tmp_path / "Vols.xlsx", param_dest_df=param_dest)

    assert any(v["source"] == "api" and v["dest_iata"] == "DLA" for v in out)


def test_load_vols_df_handles_origin_fallback_paths_and_cache_core(monkeypatch):
    monkeypatch.setattr(
        lv,
        "load_vols",
        lambda **_kwargs: [
            {
                "routing": [" ", " "],
                "routing_full": [],
                "dest_iata": "DLA",
                "flight_number": "0652",
                "date": date(2026, 2, 16),
                "departure_time": time(11, 0),
                "route_pos": 1,
                "max_colis_base": 20,
                "source": "excel",
            },
            {
                "routing": [],
                "routing_full": [" ", " "],
                "dest_iata": "RUN",
                "flight_number": "0653",
                "date": date(2026, 2, 17),
                "departure_time": time(12, 0),
                "route_pos": 1,
                "max_colis_base": 24,
                "source": "api",
            },
        ],
    )

    param_dest = pd.DataFrame(
        [
            {"Dest_IATA": "DLA", "Dest_Ville": "DOUALA"},
            {"Dest_IATA": "RUN", "Dest_Ville": "SAINT DENIS"},
        ]
    )

    df = lv.load_vols_df(param_dest_df=param_dest)
    assert set(df["Routing"]) == {"CDG-DLA", "CDG-RUN"}

    monkeypatch.setattr(lv, "load_vols_df", lambda **_k: pd.DataFrame([{"A": 1}]))
    cached_df = lv._get_vols_df_cached(str(Path("vols.xlsx")), 0.0, str(Path("tdb.xlsx")), 0.0)
    assert len(cached_df) == 1
