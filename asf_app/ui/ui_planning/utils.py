# -*- coding: utf-8 -*-

import streamlit as st


def show_mag_central_status() -> None:
    method = st.session_state.get("mag_central_write_method")
    if method == "excel":
        st.info("MAG CENTRAL mis à jour via Excel (validations préservées).")
    elif method == "openpyxl":
        st.warning("MAG CENTRAL mis à jour via openpyxl : validations de données possibles supprimées.")
    elif method == "no_updates":
        st.info("MAG CENTRAL : aucune cellule à mettre à jour.")
    elif method == "missing":
        st.warning("MAG CENTRAL non mis à jour : fichier introuvable.")
    elif method == "read_error":
        st.warning("MAG CENTRAL non mis à jour : erreur d’ouverture.")
