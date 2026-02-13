# asf_app/ui/ui_params.py
# -*- coding: utf-8 -*-

import os
from pathlib import Path

import pandas as pd
import streamlit as st

from asf_app.services.files_service import save_excel_sheet
from asf_app.services.input_service import InputLoadError, load_normalized_sheet
from asf_app.state import get_state
from asf_app.ui.email_defaults import get_email_defaults, set_email_defaults
from scheduler.column_map import (
    column_map_param_be,
    column_map_param_benev,
    column_map_param_dest,
)
from scheduler.config_paths import (
    ASF_ONEDRIVE,
    SHEET_PARAM_BE,
    SHEET_PARAM_BENEV,
    SHEET_PARAM_DEST,
    detect_onedrive_asf,
)
from utils.logging_utils import get_logger

logger = get_logger("ui_params", console=False)

PARAM_UI_ERRORS = (
    InputLoadError,
    FileNotFoundError,
    OSError,
    PermissionError,
    KeyError,
    ValueError,
    TypeError,
    RuntimeError,
    pd.errors.ParserError,
)


# ================================================================
# HELPERS
# ================================================================

def load_param_df(state, attr_name, path, sheet, mapping, header=0):
    """
    Charge un DF Param* dans STATE si vide.
    """
    df = getattr(state, attr_name)
    if df is None:
        df = load_normalized_sheet(path, sheet, mapping, header=header)
        df = df.reset_index(drop=True)
        setattr(state, attr_name, df)
    return df


def reload_param_df(state, attr_name, path, sheet, mapping, header=0):
    """
    Recharge explicitement un DF Param* depuis Excel vers STATE.
    """
    df = load_normalized_sheet(path, sheet, mapping, header=header)
    df = df.reset_index(drop=True)
    setattr(state, attr_name, df)
    return df


def write_excel_sheet(path: Path, sheet_name: str, df: pd.DataFrame):
    """
    Réécriture propre d’une feuille dans un Excel.
    """
    try:
        save_excel_sheet(path, sheet_name, df)
        return True

    except PARAM_UI_ERRORS as e:
        logger.warning("Ecriture Excel impossible pour %s (%s): %s", sheet_name, path, e)
        st.error(f"❌ Erreur écriture Excel ({sheet_name}) : {e}")
        return False


# ================================================================
# UI PRINCIPALE
# ================================================================

def render_tab_params():

    state = get_state()

    st.header("⚙️ Paramètres & Tables de configuration")

    st.info(
        "⚠️ Les Param* sont valables **uniquement pour la session**.\n"
        "ParaMail peut être enregistré pour la session ou en dur."
    )

    st.divider()

    # Bloc OneDrive (détection + override)
    with st.expander("🌥️ Chemins OneDrive / Sources", expanded=False):
        autodetect = detect_onedrive_asf()
        st.markdown(f"**OneDrive détecté :** `{autodetect}`")
        st.markdown(f"**OneDrive courant (ASF_ONEDRIVE) :** `{ASF_ONEDRIVE}`")
        new_root = st.text_input(
            "Chemin OneDrive (override pour la session)",
            value=str(ASF_ONEDRIVE),
            help="Laisse vide pour conserver la détection automatique. Exemple : ~/Library/CloudStorage/OneDrive-XXX",
        )
        if st.button("🔄 Appliquer le chemin OneDrive (session)", key="btn_onedrive_override"):
            if new_root.strip():
                os.environ["ASF_ONEDRIVE_ROOT"] = new_root.strip()
                st.success(f"Chemin OneDrive surchargé pour la session : {new_root}")
                st.rerun()
            else:
                st.info("Aucun chemin saisi, la détection automatique reste active.")

    # ---------------------------------------------------------
    # SELECTION DU BLOC
    # ---------------------------------------------------------
    if "active_block" not in st.session_state:
        st.session_state.active_block = None

    def set_block(name):
        st.session_state.active_block = name if st.session_state.active_block != name else None

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        if st.button("⚙️ Paramoteur", width="stretch"):
            set_block("paramoteur")

    with col2:
        if st.button("🗂️ ParamDest", width="stretch"):
            set_block("paramdest")

    with col3:
        if st.button("📦 ParamBE", width="stretch"):
            set_block("parambe")

    with col4:
        if st.button("👥 ParamBenev", width="stretch"):
            set_block("parambenev")

    with col5:
        if st.button("✉️ ParaMail", width="stretch"):
            set_block("paramail")

    st.markdown("")

    # ============================================================
    # BLOCS UI
    # ============================================================

    # ------------------------------------------------------------
    # 1) PARAMOTEUR (SESSION ONLY)
    # ------------------------------------------------------------
    if st.session_state.active_block == "paramoteur":

        st.subheader("⚙️ Paramètres moteur (SESSION UNIQUEMENT)")

        # Initialisation runtime
        if not hasattr(state, "config_moteur"):
            state.config_moteur = {
                "SOLVER_VERSION": os.getenv("ASF_SOLVER_VERSION", "v3"),
                "MAX_BE_PER_FLIGHT": 20,
                "MAX_EQUIV_PER_VOLUNTEER": 20,
                "MAX_BENEV_PER_VOL": 0,
                "DUREE_MISSION_HEURES": 3,
                "MIN_HOURS_BETWEEN_FLIGHTS": 2,
            }

        cfg = state.config_moteur

        with st.form("form_param_moteur"):

            cfg["SOLVER_VERSION"] = st.selectbox(
                "Version solver OR-Tools",
                options=["v2", "v3"],
                index=0 if str(cfg.get("SOLVER_VERSION", "v2")).lower() == "v2" else 1,
                help="V2 = stable (capacité globale). V3 = capacité stricte par bénévole.",
            )

            colA, colB = st.columns(2)
            with colA:
                cfg["MAX_BE_PER_FLIGHT"] = st.number_input(
                    "Nb max BE par vol",
                    min_value=1,
                    value=int(cfg["MAX_BE_PER_FLIGHT"]),
                )

            with colB:
                cfg["MAX_EQUIV_PER_VOLUNTEER"] = st.number_input(
                    "Equivalents max par bénévole",
                    min_value=1,
                    value=int(cfg["MAX_EQUIV_PER_VOLUNTEER"]),
                )

            colC, colD = st.columns(2)
            with colC:
                cfg["MAX_BENEV_PER_VOL"] = st.number_input(
                    "Nb max bénévoles par vol (0 = illimité)",
                    min_value=0,
                    value=int(cfg["MAX_BENEV_PER_VOL"]),
                )

            with colD:
                cfg["DUREE_MISSION_HEURES"] = st.number_input(
                    "Durée mission (h avant vol)",
                    min_value=1,
                    value=int(cfg["DUREE_MISSION_HEURES"]),
                )

            cfg["MIN_HOURS_BETWEEN_FLIGHTS"] = st.number_input(
                "Ecart min entre 2 missions (heures)",
                min_value=0,
                value=int(cfg["MIN_HOURS_BETWEEN_FLIGHTS"]),
            )

            if st.form_submit_button("💾 Appliquer"):
                os.environ["ASF_SOLVER_VERSION"] = str(cfg.get("SOLVER_VERSION", "v3"))
                st.session_state["solver_version"] = str(cfg.get("SOLVER_VERSION", "v3"))
                state.config_moteur = cfg
                st.success("✔ Paramoteur mis à jour (SESSION ONLY).")


    # ------------------------------------------------------------
    # 2) PARAMDEST
    # ------------------------------------------------------------
    if st.session_state.active_block == "paramdest":

        st.subheader("🗂️ ParamDest (SESSION)")

        try:
            df = load_param_df(
                state,
                "df_param_dest",
                Path(state.tdb_tmp),
                SHEET_PARAM_DEST,
                column_map_param_dest,
                header=0
            )

            edited = st.data_editor(df, width="stretch", num_rows="dynamic")

            if st.button("💾 Valider ParamDest"):
                state.df_param_dest = edited
                st.success("✔ ParamDest mis à jour pour la session.")

        except PARAM_UI_ERRORS as e:
            logger.warning("Chargement ParamDest impossible: %s", e)
            st.error(f"❌ Erreur ParamDest : {e}")


    # ------------------------------------------------------------
    # 3) PARAMBE
    # ------------------------------------------------------------
    if st.session_state.active_block == "parambe":

        st.subheader("📦 ParamBE (SESSION)")

        try:
            df = load_param_df(
                state,
                "df_param_be",
                Path(state.tdb_tmp),
                SHEET_PARAM_BE,
                column_map_param_be,
                header=0
            )

            edited = st.data_editor(df, width="stretch", num_rows="dynamic")

            if st.button("💾 Valider ParamBE"):
                state.df_param_be = edited
                st.success("✔ ParamBE mis à jour pour la session.")

        except PARAM_UI_ERRORS as e:
            logger.warning("Chargement ParamBE impossible: %s", e)
            st.error(f"❌ Erreur ParamBE : {e}")


    # ------------------------------------------------------------
    # 4) PARAMBenev
    # ------------------------------------------------------------
    if st.session_state.active_block == "parambenev":

        st.subheader("👥 ParamBenev (SESSION)")

        try:
            df = load_param_df(
                state,
                "df_param_benev",
                Path(state.benev_tmp),
                SHEET_PARAM_BENEV,
                column_map_param_benev,
                header=0
            )

            edited = st.data_editor(df, width="stretch", num_rows="dynamic")

            if st.button("💾 Valider ParamBenev"):
                state.df_param_benev = edited
                st.success("✔ ParamBenev mis à jour pour la session.")

        except PARAM_UI_ERRORS as e:
            logger.warning("Chargement ParamBenev impossible: %s", e)
            st.error(f"❌ Erreur ParamBenev : {e}")

    # ------------------------------------------------------------
    # 5) PARAMAIL
    # ------------------------------------------------------------
    if st.session_state.active_block == "paramail":

        st.subheader("✉️ ParaMail (Air France / ASF Interne)")
        st.caption("Sépare les adresses par ';' ou ','.")

        defaults = get_email_defaults()
        air_defaults = defaults.get("airfrance", {})
        asf_defaults = defaults.get("asf_interne", {})

        colA, colB = st.columns(2)

        with colA:
            st.markdown("**Air France**")
            air_to = st.text_area(
                "Air France - To",
                value=air_defaults.get("to", ""),
                height=70,
            )
            air_cc = st.text_area(
                "Air France - CC",
                value=air_defaults.get("cc", ""),
                height=70,
            )
            air_bcc = st.text_area(
                "Air France - CCI",
                value=air_defaults.get("bcc", ""),
                height=70,
            )

        with colB:
            st.markdown("**ASF Interne**")
            asf_to = st.text_area(
                "ASF Interne - To",
                value=asf_defaults.get("to", ""),
                height=70,
            )
            asf_cc = st.text_area(
                "ASF Interne - CC",
                value=asf_defaults.get("cc", ""),
                height=70,
            )
            asf_bcc = st.text_area(
                "ASF Interne - CCI",
                value=asf_defaults.get("bcc", ""),
                height=70,
            )

        payload = {
            "airfrance": {
                "to": air_to,
                "cc": air_cc,
                "bcc": air_bcc,
            },
            "asf_interne": {
                "to": asf_to,
                "cc": asf_cc,
                "bcc": asf_bcc,
            },
        }

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("✅ Valider cette session uniquement"):
                set_email_defaults(payload, persist=False)
                st.success("✔ ParaMail mis à jour pour la session.")

        with col_btn2:
            if st.button("💾 Valider en dur"):
                set_email_defaults(payload, persist=True)
                st.success("✔ ParaMail enregistré en dur.")
