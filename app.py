# app.py
# -*- coding: utf-8 -*-

import streamlit as st

# Onglets UI
from asf_app.ui_inputs import render_tab_inputs
from asf_app.ui_params import render_tab_params
from asf_app.ui_planning import render_tab_planning
from asf_app.ui_logs import render_tab_logs
from asf_app.ui_manual import render_tab_manual
from asf_app.ui_communication import render_tab_communication   # ⬅️ NOUVEL ONGLET

# Chemins des fichiers par défaut
from scheduler.config_paths import (
    TABLEAU_DE_BORD,
    PLANNING_BENEVOLES,
    VOLS,
)

# ----------------------------------------------------------------------
# 🟩 INITIALISATION SESSION_STATE (OBLIGATOIRE)
# ----------------------------------------------------------------------
def init_session_state():
    """Initialise toutes les clés globales nécessaires aux onglets."""
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

    if "log_contents" not in st.session_state:
        st.session_state.log_contents = ""


# ----------------------------------------------------------------------
# APPEL OBLIGATOIRE AVANT TOUTE UI
# ----------------------------------------------------------------------
init_session_state()


# ----------------------------------------------------------------------
# STREAMLIT CONFIG
# ----------------------------------------------------------------------
st.set_page_config(page_title="ASF — Planning automatisé", layout="wide")
st.title("📦✈️ ASF — Générateur de Planning Automatisé")
st.caption("Interface complète de gestion du planning ASF Messagerie Médicale")


# ----------------------------------------------------------------------
# ONGLET EN ORDRE DEMANDÉ
# ----------------------------------------------------------------------
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📁 Fichiers d’entrée",
    "⚙️ Paramètres",
    "📊 Planning",
    "📝 Logs",
    "➕ Ajouts manuels",
    "📣 Communication",            # ⬅️ NOUVEL ONGLET
])


with tab1:
    render_tab_inputs()

with tab2:
    render_tab_params()

with tab3:
    render_tab_planning()

with tab4:
    render_tab_logs()

with tab5:
    render_tab_manual()

with tab6:
    render_tab_communication()     # ⬅️ NOUVEL APPEL


# ----------------------------------------------------------------------
# 🔍 DEBUG : AFFICHAGE AUTOMATIQUE DES DATAFRAMES
# ----------------------------------------------------------------------
#import pandas as pd
#
#with st.sidebar.expander("🔍 Debug DataFrames / session_state"):
#    st.write("### session_state keys")
#    for key, value in st.session_state.items():
#       st.write(f"**{key}** → {type(value)}")
#      if isinstance(value, pd.DataFrame):
#         st.write(value.head(5))
#
#    # Inspection spéciale de l'objet scheduler si présent
#   if "scheduler" in st.session_state:
#        scheduler = st.session_state.scheduler
#        st.write("---")
#        st.write("### Contenu de scheduler (attributs DataFrame)")
#        for attr in dir(scheduler):
#            if attr.startswith("_"):
#                continue
#            try:
#                value = getattr(scheduler, attr)
#            except:
#                continue
#
#            if isinstance(value, pd.DataFrame):
#                st.write(f"**scheduler.{attr}** → DataFrame")
#                st.write(value.head(5))
#            else:
#                st.write(f"scheduler.{attr} → {type(value)}")
