"""
Helpers centralisés pour charger les feuilles Param* avec cache Streamlit.
"""

from __future__ import annotations

from pathlib import Path
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
from utils.cache_utils import file_mtime

try:
    import streamlit as st
except Exception:
    st = None


def _load_param_be(tableau_de_bord_path: Path | None = None):
    path = tableau_de_bord_path or TABLEAU_DE_BORD
    df = load_and_normalize(path, SHEET_PARAM_BE, column_map_param_be, header=0)
    for col in ["Priorite_Type", "Equiv"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    if "Type" in df.columns:
        df["Type"] = df["Type"].astype(str).str.strip().str.upper()
    return df


def _load_param_dest(tableau_de_bord_path: Path | None = None):
    path = tableau_de_bord_path or TABLEAU_DE_BORD
    df = load_and_normalize(path, SHEET_PARAM_DEST, column_map_param_dest, header=0)
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


def _load_param_exp(tableau_de_bord_path: Path | None = None):
    path = tableau_de_bord_path or TABLEAU_DE_BORD
    df = load_and_normalize(path, SHEET_PARAM_EXP, column_map_param_expediteur, header=0)
    return df


def _load_param_benev(planning_benevoles_path: Path | None = None):
    # Source fiable : classeur Planning BENEVOLE (feuille ParamBenev)
    path = planning_benevoles_path or PLANNING_BENEVOLES
    df = load_and_normalize(path, SHEET_PARAM_BENEV, column_map_param_benev, header=0)
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
    @st.cache_data(show_spinner=False)
    def _param_be_cached(path: str, mtime: float):
        return _load_param_be(tableau_de_bord_path=Path(path))

    @st.cache_data(show_spinner=False)
    def _param_dest_cached(path: str, mtime: float):
        return _load_param_dest(tableau_de_bord_path=Path(path))

    @st.cache_data(show_spinner=False)
    def _param_exp_cached(path: str, mtime: float):
        return _load_param_exp(tableau_de_bord_path=Path(path))

    @st.cache_data(show_spinner=False)
    def _param_benev_cached(path: str, mtime: float):
        return _load_param_benev(planning_benevoles_path=Path(path))

    def get_param_be(tableau_de_bord_path: Path | None = None):
        path = tableau_de_bord_path or TABLEAU_DE_BORD
        return _param_be_cached(str(path), file_mtime(path))

    def get_param_dest(tableau_de_bord_path: Path | None = None):
        path = tableau_de_bord_path or TABLEAU_DE_BORD
        return _param_dest_cached(str(path), file_mtime(path))

    def get_param_exp(tableau_de_bord_path: Path | None = None):
        path = tableau_de_bord_path or TABLEAU_DE_BORD
        return _param_exp_cached(str(path), file_mtime(path))

    def get_param_benev(planning_benevoles_path: Path | None = None):
        path = planning_benevoles_path or PLANNING_BENEVOLES
        return _param_benev_cached(str(path), file_mtime(path))

else:
    def get_param_be(tableau_de_bord_path: Path | None = None):
        return _load_param_be(tableau_de_bord_path=tableau_de_bord_path)

    def get_param_dest(tableau_de_bord_path: Path | None = None):
        return _load_param_dest(tableau_de_bord_path=tableau_de_bord_path)

    def get_param_exp(tableau_de_bord_path: Path | None = None):
        return _load_param_exp(tableau_de_bord_path=tableau_de_bord_path)

    def get_param_benev(planning_benevoles_path: Path | None = None):
        return _load_param_benev(planning_benevoles_path=planning_benevoles_path)


def load_param_be_from_path(tableau_de_bord_path: Path) -> pd.DataFrame:
    return _load_param_be(tableau_de_bord_path=tableau_de_bord_path)


def load_param_dest_from_path(tableau_de_bord_path: Path) -> pd.DataFrame:
    return _load_param_dest(tableau_de_bord_path=tableau_de_bord_path)


def load_param_exp_from_path(tableau_de_bord_path: Path) -> pd.DataFrame:
    return _load_param_exp(tableau_de_bord_path=tableau_de_bord_path)


def load_param_benev_from_path(planning_benevoles_path: Path) -> pd.DataFrame:
    return _load_param_benev(planning_benevoles_path=planning_benevoles_path)


def clear_param_caches() -> None:
    if st is None:
        return
    for name in ("_param_be_cached", "_param_dest_cached", "_param_exp_cached", "_param_benev_cached"):
        cached = globals().get(name)
        if cached is not None and hasattr(cached, "clear"):
            try:
                cached.clear()
            except Exception:
                pass
