# asf_app/ui/ui_manual.py
# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

from asf_app.services.files_service import save_excel_sheet
from asf_app.services.input_service import load_normalized_sheet
from asf_app.state import get_state, sync_state_paths_to_engine
from scheduler.column_map import (
    column_map_benev_dispo,
    column_map_mag_central,
    column_map_param_benev,
    column_map_vols,
)
from scheduler.config_paths import (
    SHEET_BENEV_DISPO,
    SHEET_MAG_CENTRAL,
    SHEET_PARAM_BENEV,
    SHEET_VOLS,
)
from utils.datetime_utils import coerce_datetime, format_time_value
from utils.logging_utils import get_logger

logger = get_logger("ui_manual", console=False)

MANUAL_UI_ERRORS = (
    FileNotFoundError,
    OSError,
    PermissionError,
    KeyError,
    ValueError,
    TypeError,
    RuntimeError,
    pd.errors.ParserError,
)


# ============================================================
# HELPERS
# ============================================================

def load_df(path, sheet, mapping, header=0):
    return load_normalized_sheet(
        path=path,
        sheet_name=sheet,
        mapping=mapping,
        header=header
    ).reset_index(drop=True)


def write_excel_sheet(path: Path, sheet_name: str, df: pd.DataFrame):
    """Réécriture propre d’une feuille Excel."""
    try:
        save_excel_sheet(path, sheet_name, df)
        return True

    except MANUAL_UI_ERRORS as e:
        logger.warning("Ecriture Excel impossible pour %s (%s): %s", sheet_name, path, e)
        st.error(f"❌ Erreur écriture Excel ({sheet_name}) : {e}")
        return False


# ============================================================
# ONGLET MANUEL
# ============================================================

def render_tab_manual():

    state = get_state()

    st.header("➕ Ajouts manuels (Vol / Disponibilité / BE)")
    st.caption("Toutes les écritures se font sur les fichiers TMP (sync OneDrive si mode Graph activé).")

    # ==========================================================================
    # Chemins TMP uniquement (car l’AppState ne stocke PAS les chemins OneDrive)
    # ==========================================================================

    if not state.benev_tmp or not state.vols_tmp or not state.tdb_tmp:
        st.error("❌ Chemins TMP non initialisés. Recharge les fichiers d'entrée avant les ajouts manuels.")
        return

    benev_tmp = Path(str(state.benev_tmp))
    vols_tmp = Path(str(state.vols_tmp))
    tdb_tmp = Path(str(state.tdb_tmp))

    # =====================================================================
    # 1️⃣ AJOUT / MODIFICATION DISPONIBILITÉS BÉNÉVOLES
    # =====================================================================
    with st.expander("👥 Ajouter / modifier une disponibilité bénévole", expanded=False):

        # Chargement ParamBenev
        if state.df_param_benev is None:
            state.df_param_benev = load_df(benev_tmp, SHEET_PARAM_BENEV, column_map_param_benev)

        bene_list = sorted(state.df_param_benev["Benevole"].dropna().unique())

        bene_sel = st.selectbox("Choisir un bénévole", bene_list, index=None)

        if bene_sel:

            # Charger disponibilité
            if state.df_benev is None:
                state.df_benev = load_df(benev_tmp, SHEET_BENEV_DISPO, column_map_benev_dispo)

            df_dispo = state.df_benev

            df_filtered = df_dispo[df_dispo["Benevole"] == bene_sel].copy()
            df_filtered = df_filtered.reset_index().rename(columns={"index": "ROW_ORIG"})

            # Assurer que les colonnes horaires soient éditables en texte (sinon Streamlit les bloque)
            def _time_to_str(val):
                try:
                    t = coerce_datetime(val, errors="coerce").time()
                    return format_time_value(t, fmt="%H:%M", default="")
                except (AttributeError, TypeError, ValueError):
                    return str(val) if val is not None else ""

            for col in ["Heure_Arrivee", "Heure_Depart", "Heure_Arrivee_time", "Heure_Depart_time"]:
                if col in df_filtered.columns:
                    df_filtered[col] = df_filtered[col].apply(_time_to_str)

            st.caption(f"Disponibilités existantes pour **{bene_sel}**")

            col_cfg = {
                "ROW_ORIG": st.column_config.NumberColumn("ROW_ORIG", disabled=True),
            }
            # Forcer l'édition des heures comme texte (évite le verrouillage)
            for col in ["Heure_Arrivee", "Heure_Depart", "Heure_Arrivee_time", "Heure_Depart_time"]:
                if col in df_filtered.columns:
                    col_cfg[col] = st.column_config.TextColumn(col, disabled=False)

            edited = st.data_editor(
                df_filtered,
                width="stretch",
                num_rows="dynamic",
                hide_index=True,
                column_config=col_cfg,
            )

            if st.button("💾 Enregistrer disponibilités"):

                df_new = df_dispo.copy()
                edited = edited.copy()

                # Règle métier : Heure_Arrivee = HeureArrivée - 3h
                if "Heure_Arrivee" in edited.columns:
                    for i, row in edited.iterrows():
                        try:
                            h = coerce_datetime(row["Heure_Arrivee"]).time()
                            new_time = (datetime.combine(datetime.today(), h) - timedelta(hours=3)).time()
                            edited.at[i, "Heure_Arrivee"] = format_time_value(new_time, fmt="%H:%M:%S", default="")
                        except (AttributeError, TypeError, ValueError):
                            continue

                # Mise à jour
                for _, row in edited.iterrows():
                    idx = row["ROW_ORIG"]
                    df_new.loc[idx, ["Date", "Heure_Arrivee", "Heure_Depart"]] = \
                        row["Date"], row["Heure_Arrivee"], row["Heure_Depart"]

                ok = write_excel_sheet(benev_tmp, SHEET_BENEV_DISPO, df_new)
                if not ok:
                    st.stop()

                state.df_benev = df_new
                sync_state_paths_to_engine(state)
                st.success("✔ Disponibilités enregistrées")

    # =====================================================================
    # 2️⃣ AJOUT / MODIFICATION DES VOLS
    # =====================================================================
    with st.expander("✈️ Ajouter / modifier des vols", expanded=False):

        if state.df_vols is None:
            state.df_vols = load_df(vols_tmp, SHEET_VOLS, column_map_vols)

        df_vols = state.df_vols.copy()

        edited = st.data_editor(
            df_vols,
            width="stretch",
            num_rows="dynamic",
            hide_index=True,
        )

        if st.button("💾 Enregistrer vols"):

            ok = write_excel_sheet(vols_tmp, SHEET_VOLS, edited)
            if not ok:
                st.stop()

            state.df_vols = edited
            sync_state_paths_to_engine(state)
            st.success("✔ Vols mis à jour")

    # =====================================================================
    # 3️⃣ AJOUT / MODIFICATION EXPÉDITIONS (BE)
    # =====================================================================
    with st.expander("📦 Ajouter / modifier des expéditions (BE)", expanded=False):

        if state.df_be is None:
            state.df_be = load_df(tdb_tmp, SHEET_MAG_CENTRAL, column_map_mag_central, header=5)

        df_be = state.df_be.copy()

        edited = st.data_editor(
            df_be,
            width="stretch",
            num_rows="dynamic",
            hide_index=True,
            key="editor_be_manual",
        )

        if st.button("💾 Enregistrer BE"):

            ok = write_excel_sheet(tdb_tmp, SHEET_MAG_CENTRAL, edited)
            if not ok:
                st.stop()

            state.df_be = edited
            sync_state_paths_to_engine(state)
            st.success("✔ BE mis à jour")
