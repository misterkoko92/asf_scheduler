# -*- coding: utf-8 -*-
from __future__ import annotations

import pandas as pd

from asf_app.ui.ui_communication.ui_communication_helpers import (
    build_communication_display_dataframe,
    build_destinataire_mapping,
    build_session_source_options,
    build_sim_mode_selector_data,
    fill_column_from_candidate_keywords,
    fill_missing_destinataire,
    is_empty_dataframe,
    reset_onedrive_loaded_state_for_year,
    resolve_default_session_source,
)


def test_build_destinataire_mapping_and_fill_missing_destinataire():
    df_be = pd.DataFrame(
        [
            {"BE_Numero": "25250001", "BE_Destinataire": "HOPITAL A"},
            {"BE_Numero": "25250002", "BE_Destinataire": "HOPITAL B"},
        ]
    )
    df_planning = pd.DataFrame(
        [
            {"BE_Numero": "250001", "BE_Destinataire": "HOPITAL A UPDATED"},
        ]
    )
    mapping = build_destinataire_mapping(df_be=df_be, df_planning=df_planning)

    df_comm = pd.DataFrame(
        [
            {"Numero_BE_Aff": "250001", "Destinataire": ""},
            {"Numero_BE_Aff": "250002", "Destinataire": None},
            {"Numero_BE_Aff": "250003", "Destinataire": "DEJA RENSEIGNE"},
        ]
    )
    out = fill_missing_destinataire(df_comm, mapping)

    assert out.loc[0, "Destinataire"] == "HOPITAL A UPDATED"
    assert out.loc[1, "Destinataire"] == "HOPITAL B"
    assert out.loc[2, "Destinataire"] == "DEJA RENSEIGNE"


def test_fill_missing_destinataire_no_mapping_keeps_dataframe():
    df_comm = pd.DataFrame([{"Numero_BE_Aff": "250001", "Destinataire": ""}])
    out = fill_missing_destinataire(df_comm, {})
    assert out.equals(df_comm)


def test_fill_column_from_candidate_keywords_uses_fallback_columns():
    df = pd.DataFrame(
        [
            {"Destinataire": "", "Destinataire_Mag": "HOPITAL X"},
            {"Destinataire": None, "Destinataire_Mag": "HOPITAL Y"},
        ]
    )
    out = fill_column_from_candidate_keywords(
        df,
        target="Destinataire",
        keywords=["destinataire"],
    )
    assert out["Destinataire"].tolist() == ["HOPITAL X", "HOPITAL Y"]


def test_build_communication_display_dataframe_formats_key_columns():
    df_comm = pd.DataFrame(
        [
            {
                "NUMERO BE": "1234",
                "NUMERO VOL": "AF 0652",
                "HEURE VOL": "18:20:00",
                "BE_Destinataire": "CHU TEST",
                "Expéditeur ASF": "ASF",
            }
        ]
    )
    out = build_communication_display_dataframe(df_comm)
    assert out.loc[0, "Numero_BE_Aff"] == "001234"
    assert out.loc[0, "Numero_Vol_Aff"] == "AF 652"
    assert out.loc[0, "Heure_Vol_Aff"] == "18h20"
    assert out.loc[0, "Destinataire"] == "CHU TEST"
    assert out.loc[0, "Expediteur"] == "ASF"


def test_build_session_source_options_and_default_source():
    df_main = pd.DataFrame([{"a": 1}])
    options = build_session_source_options(
        df_plan_main=df_main,
        sim_res_modes={"colis": {"planning_df": pd.DataFrame()}},
    )
    assert options == ["planning", "simulation"]
    assert resolve_default_session_source(options) == "planning"
    assert resolve_default_session_source(["simulation"]) == "simulation"


def test_build_sim_mode_selector_data_formats_labels():
    mode_values, mode_labels = build_sim_mode_selector_data(
        {
            "colis": {"statistiques": {"nb_colis_expedies": 12, "nb_benevoles_mobilises": 3}},
            "benevoles": {"statistiques": {"nb_colis_expedies": 8, "nb_benevoles_mobilises": 2}},
        }
    )
    assert mode_values == ["colis", "benevoles"]
    assert mode_labels["colis"] == "Priorité Colis (12 colis / 3 bénév)"
    assert mode_labels["benevoles"] == "Priorité Bénévoles (8 colis / 2 bénév)"


def test_reset_onedrive_loaded_state_for_year_clears_stale_state():
    session_state: dict[str, object] = {
        "comm_onedrive_loaded_year": 2025,
        "comm_onedrive_df": pd.DataFrame([{"x": 1}]),
        "comm_onedrive_file_label": "planning.xlsx",
        "comm_onedrive_file_path": "/tmp/planning.xlsx",
    }
    reset_onedrive_loaded_state_for_year(session_state, year=2026)
    assert session_state["comm_onedrive_loaded_year"] is None
    assert "comm_onedrive_df" not in session_state
    assert "comm_onedrive_file_label" not in session_state
    assert "comm_onedrive_file_path" not in session_state


def test_reset_onedrive_loaded_state_for_year_keeps_current_year():
    session_state: dict[str, object] = {
        "comm_onedrive_loaded_year": 2026,
        "comm_onedrive_df": pd.DataFrame([{"x": 1}]),
    }
    reset_onedrive_loaded_state_for_year(session_state, year=2026)
    assert "comm_onedrive_df" in session_state


def test_is_empty_dataframe_supports_none_and_dataframe():
    assert is_empty_dataframe(None) is True
    assert is_empty_dataframe(pd.DataFrame()) is True
    assert is_empty_dataframe(pd.DataFrame([{"x": 1}])) is False
