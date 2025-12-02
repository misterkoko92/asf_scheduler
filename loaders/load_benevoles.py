# loaders/load_benevoles.py
# -*- coding: utf-8 -*-

import pandas as pd
from scheduler.config_paths import PLANNING_BENEVOLES, SHEET_BENEV_DISPO
from loaders.universal_loader import load_and_normalize
from scheduler.column_map import column_map_benev_dispo


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

    # 1) Ne jamais convertir les heures en string ici !
    # On identifie les colonnes d'heures :
    hour_cols = [c for c in df.columns if "Heure" in c or "ARRIV" in c.upper() or "DEPART" in c.upper()]

    # 2) Colonne Date → datetime
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")

    # 3) Les autres colonnes (hors heures) → string
    for col in df.columns:
        if col in hour_cols:
            # Ne PAS convertir → laisser float, int, datetime, string d’origine
            continue
        if col == "Date":
            continue
        df[col] = df[col].astype(str).fillna("")

    return df
