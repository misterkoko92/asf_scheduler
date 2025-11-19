# asf_app/state.py
# -*- coding: utf-8 -*-
import streamlit as st
from scheduler.config_paths import (
    TABLEAU_DE_BORD,
    PLANNING_BENEVOLES,
    VOLS,
)


def init_session_state() -> None:
    """Initialise les variables de session Streamlit à la première exécution."""
    if "paths" not in st.session_state:
        st.session_state.paths = {
            "tdb": str(TABLEAU_DE_BORD),
            "benev": str(PLANNING_BENEVOLES),
            "vols": str(VOLS),
        }

    if "planning_df" not in st.session_state:
        st.session_state.planning_df = None

    if "bilan_df" not in st.session_state:
        st.session_state.bilan_df = None
