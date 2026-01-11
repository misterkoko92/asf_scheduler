# -*- coding: utf-8 -*-
from __future__ import annotations

import pandas as pd

from scheduler.planning_schema import normalize_planning_df, validate_planning_df
from scheduler.planning_views import build_export_view


def test_normalize_planning_df_canonical():
    df = pd.DataFrame(
        [
            {
                "Date_Vol": "01/01/2025",
                "Heure_Vol": "10h00",
                "Vol": "AF 1234",
                "Destination": "dla",
                "BE_Numero": "250001",
                "BE_Nb_Colis": "2",
                "BE_Nb_Equiv": "2",
                "Benevole": "Jean",
                "ID": "1",
            }
        ]
    )
    norm = normalize_planning_df(df)
    assert validate_planning_df(norm) == []
    assert norm.loc[0, "Numero_Vol"] == "1234"
    assert norm.loc[0, "Destination"] == "DLA"
    assert norm.loc[0, "Heure_Vol"] == "10:00"
    assert norm.loc[0, "BE_Nb_Colis"] == 2
    assert norm.loc[0, "_STATUS"] == "normal"


def test_normalize_planning_df_be_and_vol_rules():
    df = pd.DataFrame(
        [
            {
                "Date_Vol": "01/01/2025",
                "Heure_Vol": "10h00",
                "Numero_Vol": "AF 0007",
                "Destination": "dss",
                "BE_Numero": "1234",
                "BE_Nb_Colis": "1",
                "BE_Nb_Equiv": "1",
                "Benevole": "Jean",
                "ID": "1",
            }
        ]
    )
    norm = normalize_planning_df(df)
    assert norm.loc[0, "Numero_Vol"] == "7"
    assert norm.loc[0, "BE_Numero"] == "001234"


def test_build_export_view_preserves_routing():
    planning = pd.DataFrame(
        [
            {
                "Date_Vol": "01/01/2025",
                "Heure_Vol": "10:00",
                "Numero_Vol": "1234",
                "Destination": "DLA",
                "Routing": "CDG-DLA",
                "BE_Numero": "250001",
                "BE_Nb_Colis": 2,
                "BE_Nb_Equiv": 2,
                "Benevole": "Jean",
                "ID": "1",
            }
        ]
    )
    df_paramdest = pd.DataFrame([{"Dest_IATA": "DLA", "Dest_Ville": "DOUALA"}])
    df_vols = pd.DataFrame(
        [
            {
                "Date_Vol": "01/01/2025",
                "Numero_Vol": "AF 1234",
                "Routing": "CDG-DLA",
                "IATA": "DLA",
                "Destination": "Douala",
            }
        ]
    )

    view = build_export_view(planning, df_paramdest=df_paramdest, df_vols=df_vols)
    assert view.loc[0, "Dest_Ville"] == "DOUALA"
    assert view.loc[0, "Routing"] == "CDG-DLA"


def test_build_export_view_maps_city_to_iata_without_routing_fallback():
    planning = pd.DataFrame(
        [
            {
                "Date_Vol": "19/12/2025",
                "Heure_Vol": "15:45",
                "Numero_Vol": 718,
                "Destination": "DAKAR",
                "BE_Numero": "250779",
                "BE_Nb_Colis": 10,
                "BE_Nb_Equiv": 10,
                "Benevole": "Gilles",
                "ID": "25",
            }
        ]
    )
    df_paramdest = pd.DataFrame([{"Dest_IATA": "DSS", "Dest_Ville": "DAKAR"}])
    df_vols = pd.DataFrame(
        [
            {
                "Date_Vol": "19/12/2025",
                "Numero_Vol": "AF 718",
                "Routing": "CDG-DSS",
                "IATA": "DSS",
                "Destination": "DAKAR",
            }
        ]
    )

    view = build_export_view(planning, df_paramdest=df_paramdest, df_vols=df_vols)
    assert view.loc[0, "IATA"] == "DSS"
    assert view.loc[0, "Dest_Ville"] == "DAKAR"
    assert view.loc[0, "Routing"] == ""
