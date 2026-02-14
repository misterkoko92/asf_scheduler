# -*- coding: utf-8 -*-
from __future__ import annotations

import pandas as pd

import asf_app.ui.ui_communication.clean_planning_df as clean_df
from asf_app.ui.ui_communication.clean_planning_df import build_df_comm


def test_build_df_comm_formats_be_and_vol():
    df_planning = pd.DataFrame(
        [
            {
                "Date_Vol": "01/01/2025",
                "Heure_Vol": "10:00",
                "Numero_Vol": "AF 0007",
                "Destination": "DLA",
                "BE_Numero": "1234",
                "BE_Nb_Colis": 1,
                "Benevole": "DUPONT",
                "ID": "1",
            }
        ]
    )
    df_paramdest = pd.DataFrame([{"Dest_IATA": "DLA", "Dest_Ville": "DOUALA"}])
    df_parambenev = pd.DataFrame(
        [
            {
                "ID": "1",
                "Benevole": "DUPONT",
                "Prenom": "Jean",
                "Prenom_Court": "J.",
                "Nom": "Dupont",
                "Telephone": "0600000000",
            }
        ]
    )

    df_comm = build_df_comm(df_planning, df_paramdest, df_parambenev)

    assert df_comm.loc[0, "Numero_BE_Aff"] == "001234"
    assert df_comm.loc[0, "Numero_Vol_Aff"] == "AF 7"


def test_u_and_normalize_column_fallbacks():
    assert clean_df._u(pd.NA) == ""
    assert clean_df._u("  douala ") == "DOUALA"

    df = pd.DataFrame([{"X": 1}])
    clean_df._normalize_column(df, "NUMERO VOL")
    assert "NUMERO VOL" in df.columns
    assert df.loc[0, "NUMERO VOL"] == ""


def test_build_df_comm_returns_empty_on_empty_input():
    out = build_df_comm(pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
    assert out.empty


def test_build_df_comm_handles_missing_columns_and_name_fallback():
    df_planning = pd.DataFrame(
        [
            {
                "Date_Vol": "01/01/2025",
                "Heure_Vol": "10:00",
                "Numero_Vol": "AF 0007",
                "Destination": "DOUALA",
                "BE_Numero": "1234",
                "BE_Nb_Colis": 2,
                "Benevole": "DUPONT JEAN",
                "ID_BENEVOLE": "45.0",
                "BENEVOLE_ID": "",
                "BE_Destinataire": "HOPITAL",
            }
        ]
    )
    # Colonnes ParamDest volontairement absentes pour couvrir les fallbacks.
    df_paramdest = pd.DataFrame([{}])
    df_parambenev = pd.DataFrame(
        [
            {
                "ID": "45",
                "Benevole": "DUPONT JEAN",
                "Prenom": "Jean",
                "Prenom_Court": "J.",
                "Nom": "Dupont",
                "Telephone": "0600000000",
            }
        ]
    )

    out = build_df_comm(df_planning, df_paramdest, df_parambenev)
    assert not out.empty
    assert out.loc[0, "Destinataire"] == "HOPITAL"
    assert out.loc[0, "BENEVOLE_ID"] == "45"
    assert out.loc[0, "Benevole_Prenom"] == "Jean"
