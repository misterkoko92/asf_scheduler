# asf_app/ui_logs.py
# -*- coding: utf-8 -*-
import streamlit as st
import pathlib

LOG_FILE = pathlib.Path("asf_scheduler.log")


def render_tab_logs():

    st.header("📜 Logs du moteur ASF")
    st.caption("Aperçu du fichier de logs généré par le moteur.")

    # -------------------------------
    # Boutons d’actions
    # -------------------------------
    col1, col2 = st.columns(2)

    with col1:
        reload_now = st.button("🔄 Recharger les logs")

    with col2:
        clear = st.button("🗑️ Remise à zéro du fichier de logs")

    # -------------------------------
    # Effacement fichier
    # -------------------------------
    if clear:
        LOG_FILE.write_text("", encoding="utf-8")
        st.success("Le fichier de logs a été vidé.")
        return

    # -------------------------------
    # Lecture stable
    # -------------------------------
    if not LOG_FILE.exists():
        st.info("Aucun log n'a encore été généré.")
        return

    try:
        logs = LOG_FILE.read_text(encoding="utf-8")
    except Exception as e:
        st.error(f"Erreur lors de la lecture du fichier de logs : {e}")
        return

    st.text_area(
        "Contenu du fichier de logs",
        logs,
        height=600,
        key="logs_display",
        label_visibility="collapsed",
    )
