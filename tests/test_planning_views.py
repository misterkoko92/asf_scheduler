# -*- coding: utf-8 -*-
from __future__ import annotations

import pandas as pd

from scheduler.planning_views import _build_dest_maps, build_comm_base, build_export_view


def _planning_row(destination: str = "DLA") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Date_Vol": "01/01/2025",
                "Heure_Vol": "10:00",
                "Numero_Vol": "AF 1234",
                "Destination": destination,
                "BE_Numero": "250001",
                "BE_Nb_Colis": 2,
                "BE_Nb_Equiv": 2,
                "Benevole": "Jean",
                "ID": "1",
            }
        ]
    )


def test_build_dest_maps_empty_inputs():
    iata_to_city, city_to_iata = _build_dest_maps(None)
    assert iata_to_city == {}
    assert city_to_iata == {}


def test_build_export_view_empty_returns_empty():
    out = build_export_view(pd.DataFrame())
    assert out.empty


def test_build_export_view_fallbacks_from_vols_when_paramdest_missing():
    planning = _planning_row("Douala")
    df_vols = pd.DataFrame(
        [
            {
                "Date_Vol": "01/01/2025",
                "Numero_Vol": "AF 1234",
                "IATA": "DLA",
                "Destination": "Douala",
            }
        ]
    )

    out = build_export_view(planning, df_paramdest=pd.DataFrame(), df_vols=df_vols)
    assert out.loc[0, "IATA"] == "DLA"
    assert out.loc[0, "Dest_Ville"] == "DOUALA"
    assert out.loc[0, "Routing"] == ""


def test_build_comm_base_empty_and_populated():
    assert build_comm_base(pd.DataFrame()).empty

    out = build_comm_base(_planning_row("RUN"))
    assert out.loc[0, "DESTINATION"] == "RUN"
    assert out.loc[0, "NUMERO VOL"] == "1234"
    assert out.loc[0, "NUMERO BE"] == "250001"
