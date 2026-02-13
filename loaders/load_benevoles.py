# loaders/load_benevoles.py
# -*- coding: utf-8 -*-

import logging
from pathlib import Path

import pandas as pd

from loaders.universal_loader import load_and_normalize
from scheduler.column_map import column_map_benev_dispo
from scheduler.config_paths import PLANNING_BENEVOLES, SHEET_BENEV_DISPO
from utils.cache_utils import file_mtime
from utils.datetime_utils import normalize_hour_str, parse_date_series, parse_time_series

logger = logging.getLogger("ASF-SCHEDULER")


def load_benevoles(*, planning_path: Path | None = None) -> pd.DataFrame:
    """
    Charge et normalise la feuille 'Disponibilités'.
    - Conserve les heures sous leur forme originale (float Excel ou string)
    - Convertit uniquement la colonne Date en datetime
    - Convertit uniquement les colonnes textuelles en string
    """

    benev_path = planning_path or PLANNING_BENEVOLES
    df = load_and_normalize(
        path=benev_path,
        sheet_name=SHEET_BENEV_DISPO,
        mapping=column_map_benev_dispo,
        header=0
    )

    logger.debug("DEBUG LOAD_BENEVOLES start")
    logger.debug("Lignes brutes: %s", len(df))
    logger.debug("Colonnes normalisees: %s", list(df.columns))
    try:
        logger.debug("Apercu benevoles:\n%s", df.head(5).to_string(index=False))
    except (AttributeError, TypeError, ValueError):
        logger.debug("Apercu benevoles indisponible")
    logger.debug("DEBUG LOAD_BENEVOLES end")

    # 1) Identifie les colonnes d'heures :
    hour_cols = [c for c in df.columns if "Heure" in c or "ARRIV" in c.upper() or "DEPART" in c.upper()]

    # 2) Colonne Date → datetime puis format JJ/MM/AA
    if "Date" in df.columns:
        df["Date_dt"] = parse_date_series(df["Date"])
        df["Date"] = df["Date_dt"].dt.strftime("%d/%m/%y")

    # 3) Normalisation : ID/quotas en int, reste en string
    if "ID" in df.columns:
        df["ID"] = pd.to_numeric(df["ID"], errors="coerce").astype("Int64")
    for col in ["Max_Jours_Semaine", "Max_Exp_Semaine", "Max_Exp_Jour"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    if "Attente_Max_Heures" in df.columns:
        df["Attente_Max_Heures"] = pd.to_numeric(df["Attente_Max_Heures"], errors="coerce")

    # 4) Formattage heures HHhMM et filtrage des dispos incomplètes
    for col in hour_cols:
        parsed = parse_time_series(df[col])
        df[f"{col}_time"] = parsed.dt.time
        df[col] = normalize_hour_str(df[col])

    if {"Heure_Arrivee", "Heure_Depart"}.issubset(df.columns):
        df = df[(df["Heure_Arrivee"] != "") & (df["Heure_Depart"] != "")]

    # 5) Les autres colonnes (hors heures/dates/numériques) → string
    for col in df.columns:
        if (
            col in hour_cols
            or col in ["Date", "ID", "Max_Jours_Semaine", "Max_Exp_Semaine", "Max_Exp_Jour", "Attente_Max_Heures"]
            or col.endswith("_time")
            or col.endswith("_dt")
        ):
            continue
        df[col] = df[col].astype(str).fillna("")

    return df


# Cache Streamlit optionnel pour éviter des relectures multiples
try:
    import streamlit as st

    @st.cache_data(show_spinner=False)
    def _get_benevoles_cached(planning_path: str, planning_mtime: float) -> pd.DataFrame:
        return load_benevoles(planning_path=Path(planning_path))

    def get_benevoles_cached(planning_path: Path | None = None) -> pd.DataFrame:
        path = planning_path or PLANNING_BENEVOLES
        return _get_benevoles_cached(str(path), file_mtime(path))

except (ImportError, ModuleNotFoundError):
    def get_benevoles_cached(planning_path: Path | None = None) -> pd.DataFrame:
        return load_benevoles(planning_path=planning_path)


def clear_benevoles_cache() -> None:
    cached = globals().get("_get_benevoles_cached") or globals().get("get_benevoles_cached")
    if cached is not None and hasattr(cached, "clear"):
        try:
            cached.clear()
        except (AttributeError, RuntimeError, TypeError):
            pass
