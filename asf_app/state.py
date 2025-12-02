# asf_app/state.py
# -*- coding: utf-8 -*-
"""
state.py — Gestion centrale de l’état de l’application ASF Scheduler.
Compatible Streamlit (st.session_state) mais indépendant du moteur ASF.
"""

from dataclasses import dataclass, field
from pathlib import Path
import pandas as pd
import streamlit as st
from typing import Optional, Dict, Any, List

import scheduler.config_paths as cp

# ======================================================================
# 🔹 1. Dossier TMP (unique pour tout le projet)
# ======================================================================

def get_tmp_dir() -> Path:
    """
    Retourne le dossier TMP utilisé par l'application.
    Utilise le TMP du moteur (config_paths.TMP_DIR).
    """
    cp.TMP_DIR.mkdir(parents=True, exist_ok=True)
    return cp.TMP_DIR


# ======================================================================
# 🔹 2. State principal (persistant dans st.session_state)
# ======================================================================

@dataclass
class AppState:
    """
    Objet state qui stocke toutes les données utilisées à travers l'UI.
    Rien ici n'exécute de logique métier : ce fichier ne fait que stocker.
    """

    # ---------------------------
    # FICHIERS TMP (répliqués)
    # ---------------------------
    tdb_tmp: Optional[Path] = None
    vols_tmp: Optional[Path] = None
    benev_tmp: Optional[Path] = None
    param_be_tmp: Optional[Path] = None
    param_dest_tmp: Optional[Path] = None
    param_benev_tmp: Optional[Path] = None

    # ---------------------------
    # DONNÉES CHARGÉES
    # ---------------------------
    df_be: Optional[pd.DataFrame] = None
    df_vols: Optional[pd.DataFrame] = None
    df_benev: Optional[pd.DataFrame] = None

    # Paramètres normalisés
    df_param_be: Optional[pd.DataFrame] = None
    df_param_dest: Optional[pd.DataFrame] = None
    df_param_benev: Optional[pd.DataFrame] = None

    # ---------------------------
    # SEMAINE COURANTE
    # ---------------------------
    current_week: Optional[int] = None
    current_year: Optional[int] = None

    # ---------------------------
    # PLANNING GÉNÉRÉ
    # ---------------------------
    planning_df: Optional[pd.DataFrame] = None
    # Pour compatibilité rapide avec l’ancien PlanningState
    planning_active: Optional[pd.DataFrame] = None
    planning_adjusted: Optional[pd.DataFrame] = None
    planning_validated: Optional[pd.DataFrame] = None

    bilan_df: Optional[pd.DataFrame] = None
    last_scenario: Optional[str] = None
    last_engine_logs: List[str] = field(default_factory=list)

    # ---------------------------
    # CONFIG UI / divers
    # ---------------------------
    debug_mode: bool = False
    ready_for_communication: bool = False

    # Historique (plannings déjà validés)
    saved_plannings: Dict[str, Path] = field(default_factory=dict)

    # ---------------------------
    # MÉTHODES UTILES
    # ---------------------------

    def log(self, msg: str):
        """Ajoute un message au log interne."""
        self.last_engine_logs.append(msg)
        print(msg)

    def clear_planning(self):
        """Réinitialise le planning généré."""
        self.planning_df = None
        self.bilan_df = None
        self.ready_for_communication = False
        self.last_scenario = None
        self.last_engine_logs = []

    def set_planning(self, planning_df: pd.DataFrame, bilan_df: pd.DataFrame, scenario: str):
        """Stocke un planning généré."""
        self.planning_df = planning_df
        self.bilan_df = bilan_df
        self.last_scenario = scenario
        self.ready_for_communication = True

    def has_all_inputs(self) -> bool:
        """Retourne True si les 3 fichiers essentiels sont chargés."""
        return (
            self.tdb_tmp is not None
            and self.vols_tmp is not None
            and self.benev_tmp is not None
        )

    def reset_all(self):
        """Reset total de l'UI (mais pas les fichiers)."""
        self.df_be = None
        self.df_vols = None
        self.df_benev = None
        self.df_param_be = None
        self.df_param_benev = None
        self.df_param_dest = None
        self.clear_planning()


# ======================================================================
# 🔹 3. Fonctions helpers pour Streamlit
# ======================================================================

STATE_KEY = "app_state"

def get_state() -> AppState:
    """Retourne l’état global de l’application, en le créant si nécessaire."""
    if STATE_KEY not in st.session_state:
        st.session_state[STATE_KEY] = AppState()
    return st.session_state[STATE_KEY]


def reset_state():
    """Réinitialise complètement l’état."""
    st.session_state[STATE_KEY] = AppState()


# ======================================================================
# FIN DU FICHIER
# ======================================================================
