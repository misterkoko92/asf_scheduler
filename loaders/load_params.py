"""
Helpers centralisés pour charger les feuilles Param* avec cache Streamlit.
"""

from __future__ import annotations

import pandas as pd

from loaders.universal_loader import load_and_normalize
from scheduler.config_paths import (
    TABLEAU_DE_BORD,
    PLANNING_BENEVOLES,
    SHEET_PARAM_BE,
    SHEET_PARAM_DEST,
    SHEET_PARAM_EXP,
    SHEET_PARAM_BENEV,
)
from scheduler.column_map import column_map_param_be, column_map_param_dest, column_map_param_expediteur, column_map_param_benev

try:
    import streamlit as st
except Exception:
    st = None


def _load_param_be():
    df = load_and_normalize(TABLEAU_DE_BORD, SHEET_PARAM_BE, column_map_param_be, header=0)
    for col in ["Priorite_Type", "Equiv"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    if "Type" in df.columns:
        df["Type"] = df["Type"].astype(str).str.strip().str.upper()
    return df


def _load_param_dest():
    df = load_and_normalize(TABLEAU_DE_BORD, SHEET_PARAM_DEST, column_map_param_dest, header=0)
    freq_cols = [
        "Freq_Semaine",
        "Freq_Lundi",
        "Freq_Mardi",
        "Freq_Mercredi",
        "Freq_Jeudi",
        "Freq_Vendredi",
        "Freq_Samedi",
        "Freq_Dimanche",
    ]
    if "Max_Colis_Par_Vol" in df.columns:
        df["Max_Colis_Par_Vol"] = pd.to_numeric(df["Max_Colis_Par_Vol"], errors="coerce").astype("Int64")
    # Fréquences : "ok" -> 1, vide ou autre -> 0 (jour interdit)
    for col in freq_cols:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.strip()
                .str.lower()
                .map(lambda x: 1 if x == "ok" else 0 if x != "" else 0)
                .astype("Int64")
            )
    # Codes IATA en upper
    if "Dest_IATA" in df.columns:
        df["Dest_IATA"] = df["Dest_IATA"].astype(str).str.strip().str.upper()
    return df


def _load_param_exp():
    df = load_and_normalize(TABLEAU_DE_BORD, SHEET_PARAM_EXP, column_map_param_expediteur, header=0)
    return df


def _load_param_benev():
    # Source fiable : classeur Planning BENEVOLE (feuille ParamBenev)
    df = load_and_normalize(PLANNING_BENEVOLES, SHEET_PARAM_BENEV, column_map_param_benev, header=0)
    # Numériques
    if "ID" in df.columns:
        df["ID"] = pd.to_numeric(df["ID"], errors="coerce").astype("Int64")
    for col in ["Max_Jours_Semaine", "Max_Exp_Semaine", "Max_Exp_Jour"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    if "Attente_Max_Heures" in df.columns:
        df["Attente_Max_Heures"] = pd.to_numeric(df["Attente_Max_Heures"], errors="coerce")
    return df


if st is not None and hasattr(st, "cache_data"):
    _param_be = st.cache_data(show_spinner=False)(_load_param_be)
    _param_dest = st.cache_data(show_spinner=False)(_load_param_dest)
    _param_exp = st.cache_data(show_spinner=False)(_load_param_exp)
    _param_benev = st.cache_data(show_spinner=False)(_load_param_benev)

    def get_param_be():
        return _param_be()

    def get_param_dest():
        return _param_dest()

    def get_param_exp():
        return _param_exp()

    def get_param_benev():
        return _param_benev()

else:
    def get_param_be():
        return _load_param_be()

    def get_param_dest():
        return _load_param_dest()

    def get_param_exp():
        return _load_param_exp()

    def get_param_benev():
        return _load_param_benev()
