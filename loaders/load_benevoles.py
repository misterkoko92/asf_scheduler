# loaders/load_benevoles.py
# -*- coding: utf-8 -*-

import pandas as pd
from datetime import datetime, time
from scheduler.config_paths import PLANNING_BENEVOLES, SHEET_BENEV_DISPO
from loaders.universal_loader import load_and_normalize
from scheduler.column_map import column_map_benev_dispo
from utils.datetime_utils import parse_date_series, normalize_hour_str, parse_time_series

def _parse_excel_time(v) -> time | None:
    if v is None or str(v).strip() == "":
        return None
    if isinstance(v, time):
        return v
    if isinstance(v, datetime):
        return v.time()
    s = str(v).strip()
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).time()
        except Exception:
            pass
    try:
        vf = float(v)
        sec = int(vf * 86400)
        return time(sec // 3600, (sec % 3600) // 60, sec % 60)
    except Exception:
        return None

def load_benevoles() -> pd.DataFrame:
    """
    Charge et normalise la feuille 'Disponibilités'.
    - Conserve les heures sous leur forme originale (float Excel ou string)
    - Convertit uniquement la colonne Date en datetime
    - Convertit uniquement les colonnes textuelles en string
    """

    df = load_and_normalize(
        path=PLANNING_BENEVOLES,
        sheet_name=SHEET_BENEV_DISPO,
        mapping=column_map_benev_dispo,
        header=0
    )

    print("\n=== DEBUG LOAD_BENEVOLES (PATCH) ===")
    print(f"Lignes brutes : {len(df)}")
    print(f"Colonnes normalisées : {list(df.columns)}")
    try:
        print(df.head(5))
    except Exception:
        pass
    print("====================================\n")

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
        if col in hour_cols or col in ["Date", "ID", "Max_Jours_Semaine", "Max_Exp_Semaine", "Max_Exp_Jour", "Attente_Max_Heures"]:
            continue
        df[col] = df[col].astype(str).fillna("")

    return df


# Cache Streamlit optionnel pour éviter des relectures multiples
try:
    import streamlit as st

    @st.cache_data(show_spinner=False)
    def get_benevoles_cached() -> pd.DataFrame:
        return load_benevoles()

except Exception:
    def get_benevoles_cached() -> pd.DataFrame:
        return load_benevoles()
