# app.py — VERSION PROPRE (avec import communication corrigé)
# -*- coding: utf-8 -*-

import streamlit as st
import pandas as pd
import warnings

from asf_app.ui.theme import apply_theme

# ---------------------------------------
# IMPORTS UI
# ---------------------------------------
from asf_app.ui.ui_inputs import render_tab_inputs
from asf_app.ui.ui_week_data import render_tab_week_data
from asf_app.ui.ui_params import render_tab_params
from asf_app.ui.ui_planning.ui_planning import render_tab_planning
from asf_app.ui.ui_manual import render_tab_manual
from asf_app.ui.ui_logs import render_tab_logs
from asf_app.ui.ui_communication.ui_communication import render_tab_communication  # <-- FIX IMPORT
from asf_app.ui.ui_shipments_update import render_tab_shipments_update
from asf_app.ui.ui_stats.ui_stats import render_tab_stats
from asf_app.ui.ui_simulation import render_tab_simulation
from asf_app.ui.ui_faq import render_tab_faq

from scheduler.config_paths import (
    TABLEAU_DE_BORD,
    PLANNING_BENEVOLES,
    VOLS,
    prepare_paths,
)

# Prépare les copies temporaires OneDrive dès le démarrage de l'UI
prepare_paths(copy_sources=True)

# Masquer les UserWarning openpyxl (Data Validation non supportée)
warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    module="openpyxl"
)

DEFAULT_USE_MODERN_THEME = False  # Passe à True pour activer la refonte visuelle par défaut

# ---------------------------------------
# SESSION STATE INIT
# ---------------------------------------
def init_session_state():
    if "paths" not in st.session_state:
        st.session_state.paths = {
            "tdb": str(TABLEAU_DE_BORD),
            "benev": str(PLANNING_BENEVOLES),
            "vols": str(VOLS),
        }

    st.session_state.setdefault("dfs", {})
    st.session_state.setdefault("planning_df", None)
    st.session_state.setdefault("bilan_df", None)
    st.session_state.setdefault("log_contents", "")
    st.session_state.setdefault("use_modern_theme", DEFAULT_USE_MODERN_THEME)

init_session_state()


# ---------------------------------------
# STREAMLIT CONFIG
# ---------------------------------------
st.set_page_config(page_title="ASF — Planning automatisé", layout="wide")
st.title("📦✈️ ASF — Générateur de Planning Automatisé")

# ----------------------------------------------------
# Choix de thème (haut de page)
# ----------------------------------------------------
top_left, top_right = st.columns([5, 1])
with top_right:
    theme_choice = st.selectbox(
        "Thème",
        options=["Classique", "Moderne"],
        index=1 if st.session_state.get("use_modern_theme") else 0,
    )
    st.session_state.use_modern_theme = theme_choice == "Moderne"

# ----------------------------------------------------
# Styles globaux
# ----------------------------------------------------
apply_theme(st.session_state.get("use_modern_theme", DEFAULT_USE_MODERN_THEME))


# ---------------------------------------
# ONGLET LIST
# ---------------------------------------
tabs = st.tabs([
    "📁 Données semaine",
    "➕ Ajouts manuels",
    "⚙️ Paramètres",
    "📊 Planning",
    "📣 Communication",
    "🚚 Mise à Jour expéditions",
    "🧪 Simulation",
    "📈 Statistiques",
    "📝 Logs",
    "❓ FAQ / Instructions",
])


# ---------------------------------------
# ONGLET 0 — FICHIERS D’ENTRÉE
# ---------------------------------------
with tabs[0]:
    render_tab_inputs()
    st.divider()
    render_tab_week_data()

# ONGLET 2 — AJOUTS MANUELS
with tabs[1]:
    render_tab_manual()

# ONGLET 3 — PARAMÈTRES
with tabs[2]:
    render_tab_params()

# ONGLET 4 — PLANNING
with tabs[3]:
    render_tab_planning()

# ONGLET 5 — COMMUNICATION
with tabs[4]:
    render_tab_communication()

# ONGLET 6 — MISE À JOUR EXPÉDITIONS
with tabs[5]:
    render_tab_shipments_update()

# ONGLET 7 — STATISTIQUES
with tabs[6]:
    render_tab_simulation()

# ONGLET 8 — STATISTIQUES
with tabs[7]:
    render_tab_stats()

# ONGLET 9 — LOGS
with tabs[8]:
    render_tab_logs()

# ONGLET 10 — FAQ / Instructions
with tabs[9]:
    render_tab_faq()
