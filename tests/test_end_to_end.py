# -*- coding: utf-8 -*-
from __future__ import annotations

import scheduler.config_paths as cp
from asf_app.ui.ui_communication.clean_planning_df import build_df_comm
from loaders.load_params import load_param_benev_from_path, load_param_dest_from_path
from scheduler.planning_schema import normalize_planning_df, validate_planning_df
from scheduler.solver_ortools import solve_planning_ortools


def test_full_chain_ortools_to_communication(sample_onedrive):
    planning_df, bilan_df, stats = solve_planning_ortools(
        timeout_seconds=10,
        data_source_name="excel",
    )

    assert stats.get("status") in {"OPTIMAL", "FEASIBLE"}
    assert stats.get("nb_be_envoyes") == 1

    planning_df = normalize_planning_df(planning_df)
    assert validate_planning_df(planning_df) == []
    assert not planning_df.empty
    dest_values = set(planning_df["Destination"].astype(str).str.upper().unique())
    assert dest_values.intersection({"DLA", "DOUALA"})

    df_paramdest = load_param_dest_from_path(cp.TABLEAU_DE_BORD)
    df_parambenev = load_param_benev_from_path(cp.PLANNING_BENEVOLES)
    df_comm = build_df_comm(planning_df, df_paramdest, df_parambenev)

    assert not df_comm.empty
    required_cols = [
        "Destination",
        "Date_Affichage",
        "Date_Affichage_WA",
        "Numero_Vol_Aff",
        "Heure_Vol_Aff",
        "Numero_BE_Aff",
        "Nb_Colis",
        "Type_Colis",
        "Expediteur",
        "Destinataire",
        "Benevole",
        "Benevole_Tel",
        "Code_IATA",
        "Dest_Ville",
        "BENEVOLE_ID",
    ]
    for col in required_cols:
        assert col in df_comm.columns
    assert df_comm["Numero_BE_Aff"].astype(str).str.strip().ne("").any()
    assert df_comm["Benevole_Tel"].astype(str).str.strip().ne("").any()
