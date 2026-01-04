# asf_app/services/planning_service.py
# -*- coding: utf-8 -*-
import datetime
from typing import Tuple, Dict

import pandas as pd

from scheduler.core_scheduler import Scheduler
from scheduler.planning_schema import normalize_planning_df
from asf_app.config.paths import AppPaths


# =====================================================================
# LANCER LE PLANNING (mode automatique complet)
# =====================================================================

def run_planning(paths: AppPaths) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Synchronise les chemins avec le moteur, lance le Scheduler
    et renvoie (planning_df, bilan_df).

    Le Scheduler utilise désormais :
      - load_and_normalize()
      - column_map
      - copies temporaires des sources
      - chemins propres via config_paths
    """

    # On pousse les chemins UI → moteur
    paths.sync_to_engine()

    scheduler = Scheduler()
    planning_df, bilan_df = scheduler.run()
    planning_df = normalize_planning_df(planning_df)

    # Toujours assurer un DataFrame propre
    if planning_df is None:
        planning_df = pd.DataFrame()
    if bilan_df is None:
        bilan_df = pd.DataFrame()

    return planning_df, bilan_df


# =====================================================================
# AJOUT MANUEL D’UN BE (version simple, utilisée par UI_legacy)
# =====================================================================

def add_manual_be(planning_df: pd.DataFrame, form_data: Dict) -> pd.DataFrame:
    """
    Ajoute manuellement un BE dans le planning (mode MANUEL)
    — Cette fonction est utilisée par une partie du code Streamlit.

    ⚠️ La logique avancée (auto/semiauto/benevole forcé)
    est gérée par be_placement_service.place_be().
    Ici, on ne fait qu’insérer une ligne brute.
    """

    # Heure : peut venir sous forme datetime.time ou string
    heure = form_data.get("heure_vol")
    if isinstance(heure, datetime.time):
        heure_str = heure.strftime("%H:%M")
    else:
        heure_str = str(heure or "").strip()

    new_row = {
        "Date_Vol": form_data.get("date_vol"),
        "Heure_Vol": heure_str,
        "Numero_Vol": form_data.get("vol_num", ""),
        "Destination": form_data.get("dest", ""),
        "BE_Numero": form_data.get("be_num", ""),
        "BE_Nb_Colis": form_data.get("nb_colis", 0),
        "BE_Nb_Equiv": form_data.get("nb_colis", 0),
        "Benevole": form_data.get("benevole", ""),
        "_MANUEL": True,
    }

    df2 = pd.concat([planning_df, pd.DataFrame([new_row])], ignore_index=True)
    return normalize_planning_df(df2)
