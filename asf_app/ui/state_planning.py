# asf_app/ui/state_planning.py
# -*- coding: utf-8 -*-
"""
state_planning.py — État dédié à la section « Planning » de l’UI ASF Scheduler.
Ce state est indépendant de l'état global (asf_app/state.py) et ne gère
que les données propres à :
  - exécution des scénarios (réel + A/B/C)
  - planning actif / ajusté
  - comparaisons
  - validation planning final
  - mise à disposition pour Communication
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import pandas as pd
import streamlit as st


# ======================================================================
# 🔹 Dataclass : PlanningState
# ======================================================================

@dataclass
class PlanningState:
    """
    Stocke tous les éléments nécessaires à l’onglet Planning.
    
    Important :
    - Rien ici n’effectue de logique métier.
    - Ce module ne dépend pas du moteur ASF.
    - Entièrement compatible Streamlit.
    """

    # ---------------------------------------------------
    # Résultats moteurs (4 scénarios)
    # ---------------------------------------------------
    planning_scenarios: Dict[str, pd.DataFrame] = field(default_factory=dict)
    bilan_scenarios: Dict[str, pd.DataFrame] = field(default_factory=dict)
    stats_scenarios: Dict[str, dict] = field(default_factory=dict)

    # ---------------------------------------------------
    # Planning actif (après sélection)
    # ---------------------------------------------------
    active_tag: str = "real"             # "real", "A", "B", "C"
    planning_active: Optional[pd.DataFrame] = None
    bilan_active: Optional[pd.DataFrame] = None
    stats_active: Optional[dict] = None

    # ---------------------------------------------------
    # Version ajustée (manuelle) du planning actif
    # ---------------------------------------------------
    planning_adjusted: Optional[pd.DataFrame] = None

    # ---------------------------------------------------
    # Planning validé (utilisé par Communication)
    # ---------------------------------------------------
    planning_validated: Optional[pd.DataFrame] = None
    bilan_validated: Optional[pd.DataFrame] = None
    validated_filename: Optional[str] = None

    # ---------------------------------------------------
    # Flags divers
    # ---------------------------------------------------
    ready_for_communication: bool = False
    last_engine_logs: list = field(default_factory=list)

    # ==================================================
    # MÉTHODES
    # ==================================================

    # ---------- LOG ----------
    def log(self, msg: str):
        self.last_engine_logs.append(msg)
        print(msg)

    # ---------- RESET ----------
    def reset_all(self):
        """Reset total — utile si on change d’année / semaine / sources."""
        self.planning_scenarios = {}
        self.bilan_scenarios = {}
        self.stats_scenarios = {}
        self.active_tag = "real"
        self.planning_active = None
        self.bilan_active = None
        self.stats_active = None
        self.planning_adjusted = None
        self.planning_validated = None
        self.bilan_validated = None
        self.validated_filename = None
        self.ready_for_communication = False
        self.last_engine_logs = []

    # ---------- ACTIVER UN SCÉNARIO ----------
    def activate_scenario(self, tag: str):
        """Définit le scénario actif (real / A / B / C)."""
        if tag in self.planning_scenarios:
            self.active_tag = tag
            self.planning_active = self.planning_scenarios.get(tag)
            self.bilan_active = self.bilan_scenarios.get(tag)
            self.stats_active = self.stats_scenarios.get(tag)
            # Lorsque l’on change de scénario, on oublie l’ajusté
            self.planning_adjusted = None
            self.ready_for_communication = False

    # ---------- STOCKER RÉSULTATS DES 4 MOTEURS ----------
    def set_all_scenarios(self, planning_dict, bilan_dict, stats_dict):
        self.planning_scenarios = planning_dict
        self.bilan_scenarios = bilan_dict
        self.stats_scenarios = stats_dict

    # ---------- STOCKER PLANNING ACTIF ----------
    def set_active_planning(self, tag: str):
        self.activate_scenario(tag)

    # ---------- AJOUT / MODIFICATION MANUELLE ----------
    def set_adjusted_planning(self, df: pd.DataFrame):
        """Stocker un planning ajusté."""
        self.planning_adjusted = df.copy() if df is not None else None

    # ---------- VALIDER LE PLANNING ----------
    def validate_planning(self, df: Optional[pd.DataFrame], bilan: Optional[pd.DataFrame], filename: str):
        """
        Validation finale — ce planning sera utilisé dans l'onglet Communication.
        """
        self.planning_validated = df.copy() if df is not None else None
        self.bilan_validated = bilan.copy() if bilan is not None else None
        self.validated_filename = filename
        self.ready_for_communication = True


# ======================================================================
# 🔹 Helpers Streamlit
# ======================================================================

PLANNING_STATE_KEY = "planning_state"


def get_planning_state() -> PlanningState:
    """Retourne l’état Planning (créé si absent)."""
    if PLANNING_STATE_KEY not in st.session_state:
        st.session_state[PLANNING_STATE_KEY] = PlanningState()
    return st.session_state[PLANNING_STATE_KEY]


def reset_planning_state():
    """Reset total du state Planning."""
    st.session_state[PLANNING_STATE_KEY] = PlanningState()
