# asf_app/state.py
# -*- coding: utf-8 -*-
"""
state.py — Gestion centrale de l’état de l’application ASF Scheduler.
Compatible Streamlit (st.session_state) mais indépendant du moteur ASF.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

import scheduler.config_paths as cp
from scheduler.data_sources import ExcelSourcePaths
from utils.logging_utils import get_logger

logger = get_logger("state", console=False)

def _get_session_context():
    try:
        from asf_app.config.session_context import get_session_context
        return get_session_context()
    except (ImportError, OSError, RuntimeError, TypeError, ValueError):
        return None

# ======================================================================
# 🔹 1. Dossier TMP (unique pour tout le projet)
# ======================================================================

def get_tmp_dir() -> Path:
    """
    Retourne le dossier TMP utilisé par l'application.
    Utilise le TMP du moteur (config_paths.TMP_DIR).
    """
    ctx = _get_session_context()
    if ctx is not None:
        ctx.tmp_dir.mkdir(parents=True, exist_ok=True)
        return ctx.tmp_dir
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
    api_start_date: Optional[Any] = None
    api_end_date: Optional[Any] = None
    vols_source: str = "excel"  # excel | api
    api_time_origin_type: str = "P"

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
        logger.info(msg)

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


def sync_state_paths_to_engine(state: AppState) -> None:
    """
    Aligne les chemins actifs de l'UI dans la session, et nettoie les caches.
    (Ne modifie plus les variables globales du moteur.)
    """
    tdb = Path(state.tdb_tmp).resolve() if state.tdb_tmp is not None else cp.TABLEAU_DE_BORD
    benev = Path(state.benev_tmp).resolve() if state.benev_tmp is not None else cp.PLANNING_BENEVOLES
    vols = Path(state.vols_tmp).resolve() if state.vols_tmp is not None else cp.VOLS

    st.session_state["paths"] = {
        "tdb": str(tdb),
        "benev": str(benev),
        "vols": str(vols),
    }

    try:
        from scheduler.be_manager import reset_param_be_cache
        reset_param_be_cache()
    except (ImportError, AttributeError, OSError, RuntimeError, TypeError, ValueError):
        pass
    try:
        from loaders.load_params import clear_param_caches
        clear_param_caches()
    except (ImportError, AttributeError, OSError, RuntimeError, TypeError, ValueError):
        pass
    try:
        from loaders.load_shipments import clear_shipments_cache
        clear_shipments_cache()
    except (ImportError, AttributeError, OSError, RuntimeError, TypeError, ValueError):
        pass
    try:
        from loaders.load_benevoles import clear_benevoles_cache
        clear_benevoles_cache()
    except (ImportError, AttributeError, OSError, RuntimeError, TypeError, ValueError):
        pass
    try:
        from loaders.load_vols import clear_vols_cache
        clear_vols_cache()
    except (ImportError, AttributeError, OSError, RuntimeError, TypeError, ValueError):
        pass


def get_excel_source_paths(state: AppState) -> ExcelSourcePaths:
    """
    Retourne les chemins Excel actifs pour la session (sans muter les globals).
    """
    ctx = _get_session_context()
    if ctx is not None:
        return ctx.source_paths
    tdb = Path(state.tdb_tmp).resolve() if state.tdb_tmp is not None else cp.TABLEAU_DE_BORD
    benev = Path(state.benev_tmp).resolve() if state.benev_tmp is not None else cp.PLANNING_BENEVOLES
    vols = Path(state.vols_tmp).resolve() if state.vols_tmp is not None else cp.VOLS
    return ExcelSourcePaths(tableau_de_bord=tdb, planning_benevoles=benev, vols=vols)


# ======================================================================
# FIN DU FICHIER
# ======================================================================
