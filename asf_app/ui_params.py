# asf_app/ui_params.py
# -*- coding: utf-8 -*-

import pandas as pd
import streamlit as st
from scheduler import config
from scheduler.config_paths import (
    SHEET_PARAM_DEST,
    SHEET_PARAM_BE,
    SHEET_PARAM_BENEV,
)


# ============================================================================
# ONGLET PARAMÈTRES
# ============================================================================

def render_tab_params():

    st.header("⚙️ Paramètres & Tables de configuration")

    # =========================================================================
    # 1) PARAMÈTRES DU MOTEUR (config.py)
    # =========================================================================
    with st.expander("⚙️ Paramètres du moteur (config.py)", expanded=False):
        st.info("Modifie les règles du moteur pour cette session. Non enregistré dans le fichier.")

        with st.form("form_params_moteur"):
            col1, col2 = st.columns(2)
            with col1:
                max_be = st.number_input(
                    "Nombre max de BE par vol",
                    min_value=1,
                    value=int(config.MAX_BE_PER_FLIGHT),
                    step=1,
                )
            with col2:
                max_equiv = st.number_input(
                    "Équivalents max par bénévole",
                    min_value=1,
                    value=int(config.MAX_EQUIV_PER_VOLUNTEER),
                    step=1,
                )

            col3, col4 = st.columns(2)
            with col3:
                max_benev = st.number_input(
                    "Limite max de bénévoles par vol (None = illimité)",
                    min_value=0,
                    value=0 if config.MAX_BENEV_PER_VOL is None else int(config.MAX_BENEV_PER_VOL),
                    step=1,
                    help="0 = illimité",
                )
            with col4:
                duree = st.number_input(
                    "Durée de mission bénévole (heures avant vol)",
                    min_value=1,
                    value=int(config.DUREE_MISSION_HEURES),
                    step=1,
                )

            submitted_params = st.form_submit_button("💾 Appliquer")
            if submitted_params:
                config.MAX_BE_PER_FLIGHT = int(max_be)
                config.MAX_EQUIV_PER_VOLUNTEER = int(max_equiv)
                config.MAX_BENEV_PER_VOL = None if max_benev == 0 else int(max_benev)
                config.DUREE_MISSION_HEURES = int(duree)

                st.success("Paramètres moteur mis à jour (session uniquement).")

    st.markdown("---")

    # =========================================================================
    # 2) ParamDest
    # =========================================================================
    with st.expander("🗂️ ParamDest (TABLEAU DE BORD)", expanded=False):

        path_tdb = st.session_state.paths["tdb"]

        try:
            df_paramdest = pd.read_excel(path_tdb, sheet_name=SHEET_PARAM_DEST, dtype=str).fillna("")
            edited_df = st.data_editor(df_paramdest, use_container_width=True, num_rows="dynamic")

            if st.button("💾 Enregistrer ParamDest"):
                with pd.ExcelWriter(path_tdb, engine="openpyxl", mode="a",
                                    if_sheet_exists="replace") as writer:
                    edited_df.to_excel(writer, sheet_name=SHEET_PARAM_DEST, index=False)
                st.success("ParamDest mis à jour dans le TABLEAU DE BORD.")
        except Exception as e:
            st.error(f"❌ Erreur lecture ParamDest : {e}")

    st.markdown("---")

    # =========================================================================
    # 3) ParamBE
    # =========================================================================
    with st.expander("📦 ParamBE (TABLEAU DE BORD)", expanded=False):

        path_tdb = st.session_state.paths["tdb"]

        try:
            df_parambe = pd.read_excel(path_tdb, sheet_name=SHEET_PARAM_BE, dtype=str).fillna("")
            edited_df = st.data_editor(df_parambe, use_container_width=True, num_rows="dynamic")

            if st.button("💾 Enregistrer ParamBE"):
                with pd.ExcelWriter(path_tdb, engine="openpyxl", mode="a",
                                    if_sheet_exists="replace") as writer:
                    edited_df.to_excel(writer, sheet_name=SHEET_PARAM_BE, index=False)
                st.success("ParamBE mis à jour dans le TABLEAU DE BORD.")
        except Exception as e:
            st.error(f"❌ Erreur lecture ParamBE : {e}")

    st.markdown("---")

    # =========================================================================
    # 4) ParamBenev
    # =========================================================================
    with st.expander("👥 ParamBenev (Planning bénévoles)", expanded=False):

        path_benev = st.session_state.paths["benev"]

        try:
            df_parambenev = pd.read_excel(path_benev, sheet_name=SHEET_PARAM_BENEV, dtype=str).fillna("")
            edited_df = st.data_editor(df_parambenev, use_container_width=True, num_rows="dynamic")

            if st.button("💾 Enregistrer ParamBenev"):
                with pd.ExcelWriter(path_benev, engine="openpyxl", mode="a",
                                    if_sheet_exists="replace") as writer:
                    edited_df.to_excel(writer, sheet_name=SHEET_PARAM_BENEV, index=False)
                st.success("ParamBenev mis à jour dans Planning Bénévoles.")
        except Exception as e:
            st.error(f"❌ Erreur lecture ParamBenev : {e}")
