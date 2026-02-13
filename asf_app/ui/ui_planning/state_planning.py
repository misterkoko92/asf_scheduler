# asf_app/ui/state_planning.py
# -*- coding: utf-8 -*-

import pandas as pd
import streamlit as st


class PlanningState:
    """
    Conteneur simple et propre pour stocker :
    - le planning généré
    - le bilan (optionnel)
    dans st.session_state.
    """

    def __init__(self):
        # Planning principal
        self._planning = None
        # Bilan
        self._bilan = None
        # Dernier export Excel (Path ou str)
        self._last_export_path = None

    # ---------------------------------------------------------
    # GETTERS
    # ---------------------------------------------------------
    @property
    def planning(self):
        return self._planning

    @property
    def bilan(self):
        return self._bilan

    @property
    def last_export_path(self):
        return self._last_export_path

    # ---------------------------------------------------------
    # SETTERS
    # ---------------------------------------------------------
    def set_planning(self, df_planning, df_bilan=None):
        """Stocke le planning + bilan."""
        if df_planning is not None and not isinstance(df_planning, pd.DataFrame):
            raise ValueError("df_planning doit être un DataFrame pandas")

        self._planning = df_planning
        self._bilan = df_bilan

    def set_last_export_path(self, path):
        """Stocke le dernier fichier exporté (planning Excel)."""
        self._last_export_path = path


# =============================================================
# 🔥 SINGLETON via session_state (avec auto-upgrade si ancien obj)
# =============================================================
def get_planning_state() -> PlanningState:
    """
    Retourne l’unique PlanningState stocké dans Streamlit.
    Si une ancienne version de l’objet est trouvée (sans attribut .planning),
    on la remplace automatiquement par une version propre.
    """
    key = "planning_state"

    if key not in st.session_state:
        st.session_state[key] = PlanningState()
    else:
        obj = st.session_state[key]
        # Upgrade : si un vieil objet n’a pas les attributs attendus
        if not hasattr(obj, "_planning") or not hasattr(obj, "planning"):
            st.session_state[key] = PlanningState()

    return st.session_state[key]
