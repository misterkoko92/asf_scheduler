# asf_app/ui/ui_inputs.py
# -*- coding: utf-8 -*-

import os
from datetime import datetime, date, timedelta
import pandas as pd
from utils.datetime_utils import coerce_datetime, format_date_value
import streamlit as st
from pathlib import Path
import shutil

from asf_app.state import get_state, get_tmp_dir, sync_state_paths_to_engine

import scheduler.config_paths as cp
from asf_app.config.runtime import (
    is_graph_onedrive,
    get_tableau_de_bord_src,
    get_planning_benevoles_src,
    get_vols_src,
    get_tableau_de_bord_remote,
    get_planning_benevoles_remote,
    get_vols_remote,
)
from asf_app.config.session_context import (
    get_session_context,
    ensure_session_context,
    refresh_session_context,
)
from scheduler.config_paths import (
    IS_STREAMLIT_CLOUD,
    CLOUD_MESSAGE,
)

# Loaders normalisés
from loaders.load_shipments import load_shipments_df
from loaders.load_vols_api import load_vols_api, store_vols_api_sheet
from asf_app.services.input_service import (
    load_tdb,
    load_benev,
    load_vols,
    InputLoadError,
    get_benev_source_message,
)
from utils.logging_utils import get_logger



# -------------------------------------------------------------------------
# HELPERS
# -------------------------------------------------------------------------

logger = get_logger("ui_inputs", console=False)

DEFAULT_TMP_NAMES = {
    "tdb": "TABLEAU_DE_BORD.xlsx",
    "benev": "PLANNING_BENEVOLES.xlsx",
    "vols": "VOLS.xlsx",
}


def _default_tmp_path(key_name: str) -> Path:
    return get_tmp_dir() / DEFAULT_TMP_NAMES.get(key_name, f"{key_name}.xlsx")

def pretty_mtime(path: Path) -> str:
    try:
        ts = path.stat().st_mtime
        dt = datetime.fromtimestamp(ts)
        return format_date_value(dt, fmt="%d/%m/%Y à %H:%M", default="N/A")
    except Exception:
        return "N/A"


def ensure_tmp_file(src_path: Path, filename: str, *, overwrite: bool = False) -> Path:
    """
    Assure la présence d’un fichier dans le TMP moteur.
    Copie si absent. Ne remplace pas si déjà là.
    """
    tmp_dir = get_tmp_dir()
    dst = tmp_dir / filename
    if src_path.exists() and (overwrite or not dst.exists()):
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dst)
    return dst


def pick_planning_dates(state):
    """
    Sélecteur de période de planning (début/fin) stocké dans le state.
    """
    today = date.today()
    next_monday = today + timedelta(days=(7 - today.weekday()))
    default_start = state.api_start_date or next_monday
    default_end = state.api_end_date or (default_start + timedelta(days=6))

    st.subheader("🗓️ Période du planning")
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        start = st.date_input("Date de début", value=default_start, key="plan_start")
    with col_s2:
        # La date de fin suit automatiquement la date de début (+6)
        auto_end = start + timedelta(days=6)
        st.write(f"Date de fin (auto) : **{auto_end:%d/%m/%Y}**")
        end = auto_end

    if end < start:
        st.error("La date de fin doit être après la date de début.")
    state.api_start_date = start
    state.api_end_date = end


def benev_last_message(path: Path) -> str:
    return get_benev_source_message(path)


# -------------------------------------------------------------------------
# LOADING FONCTIONS — écrivent dans state
# -------------------------------------------------------------------------

def load_tdb_file(state, force=False):
    if not force and state.df_be is not None and state.df_param_be is not None:
        return

    try:
        data = load_tdb(Path(state.tdb_tmp))
        state.df_be = data.df_be
        state.df_param_be = data.df_param_be
        state.df_param_dest = data.df_param_dest
    except FileNotFoundError as e:
        logger.error("TABLEAU DE BORD manquant: %s", e)
        st.error(f"❌ {e}")
    except Exception as e:
        logger.error("Erreur chargement TABLEAU DE BORD: %s", e)
        st.error(f"❌ Erreur chargement TABLEAU DE BORD : {e}")


def load_benev_file(state, force=False):
    if not force and state.df_benev is not None and state.df_param_benev is not None:
        return

    try:
        data = load_benev(Path(state.benev_tmp))
        state.df_param_benev = data.df_param_benev
        state.df_benev = data.df_benev
    except FileNotFoundError as e:
        logger.error("Planning Bénévoles manquant: %s", e)
        st.error(f"❌ {e}")
    except Exception as e:
        logger.error("Erreur chargement Bénévoles: %s", e)
        st.error(f"❌ Erreur chargement Bénévoles : {e}")


def load_vols_file(state, force=False):
    if not force and state.df_vols is not None:
        return

    try:
        df_param_dest = state.df_param_dest
        tdb_path = Path(state.tdb_tmp) if state.tdb_tmp is not None else None
        state.df_vols = load_vols(Path(state.vols_tmp), param_dest_df=df_param_dest, tdb_path=tdb_path)
    except FileNotFoundError as e:
        logger.error("Vols manquant: %s", e)
        st.error(f"❌ {e}")
    except InputLoadError as e:
        logger.error("Erreur chargement Vols: %s", e)
        st.error(f"❌ {e}")
    except Exception as e:
        logger.error("Erreur chargement Vols: %s", e)
        st.error(f"❌ Erreur chargement Vols : {e}")


# -------------------------------------------------------------------------
# TMP REWRITE / REFRESH
# -------------------------------------------------------------------------

def overwrite_tmp_file(uploaded_file, state, key_name, reload_func):
    """
    key_name ∈ {"tdb","benev","vols"}
    """
    if uploaded_file is None:
        return

    tmp_path = getattr(state, f"{key_name}_tmp")

    try:
        with open(tmp_path, "wb") as f:
            f.write(uploaded_file.read())
        cp.sync_local_file_to_onedrive(tmp_path)

        # Invalidate dataframes
        if key_name == "tdb":
            state.df_be = None
            state.df_param_be = None
            state.df_param_dest = None
        elif key_name == "benev":
            state.df_benev = None
            state.df_param_benev = None
        elif key_name == "vols":
            state.df_vols = None

        reload_func(state, force=True)
        sync_state_paths_to_engine(state)
        st.success("✔ Fichier mis à jour dans le dossier TMP")

    except Exception as e:
        st.error(f"❌ Erreur mise à jour TMP : {e}")


def refresh_from_onedrive(state, src_path, key_name, reload_func):
    """
    Copie depuis OneDrive vers TMP et recharge les df.
    """
    try:
        name_map = {
            "tdb": Path(state.tdb_tmp).name if state.tdb_tmp else DEFAULT_TMP_NAMES["tdb"],
            "benev": Path(state.benev_tmp).name if state.benev_tmp else DEFAULT_TMP_NAMES["benev"],
            "vols": Path(state.vols_tmp).name if state.vols_tmp else DEFAULT_TMP_NAMES["vols"],
        }
        dst_name = name_map.get(key_name, Path(src_path).name if src_path else DEFAULT_TMP_NAMES.get(key_name, "data.xlsx"))
        if is_graph_onedrive():
            remote_map = {
                "tdb": get_tableau_de_bord_remote(),
                "benev": get_planning_benevoles_remote(),
                "vols": get_vols_remote(),
            }
            remote_path = remote_map.get(key_name, "")
            dst = get_tmp_dir() / dst_name
            cp.download_onedrive_file(remote_path, dst, interactive=False)
        else:
            dst = ensure_tmp_file(Path(src_path), dst_name, overwrite=True)
        setattr(state, f"{key_name}_tmp", dst)

        # reset dfs
        if key_name == "tdb":
            state.df_be = None
            state.df_param_be = None
            state.df_param_dest = None
        elif key_name == "benev":
            state.df_benev = None
            state.df_param_benev = None
        elif key_name == "vols":
            state.df_vols = None

        reload_func(state, force=True)
        sync_state_paths_to_engine(state)
        st.success(f"✔ Rechargé depuis OneDrive : {src_path.name}")

    except Exception as e:
        st.error(f"❌ Erreur refresh OneDrive : {e}")


def refresh_all(state):
    try:
        ctx = refresh_session_context(strict_sources=True)
    except FileNotFoundError as exc:
        logger.error("Sources manquantes: %s", exc)
        st.error(f"❌ {exc}")
        return
    st.session_state.pop("source_error", None)
    if ctx is not None:
        state.tdb_tmp = ctx.source_paths.tableau_de_bord
        state.benev_tmp = ctx.source_paths.planning_benevoles
        state.vols_tmp = ctx.source_paths.vols
    state.df_be = state.df_param_be = state.df_param_dest = None
    state.df_benev = state.df_param_benev = None
    state.df_vols = None
    load_tdb_file(state, force=True)
    load_benev_file(state, force=True)
    load_vols_file(state, force=True)
    sync_state_paths_to_engine(state)
    st.success("✔ Tous les fichiers ont été rechargés depuis OneDrive.")


# -------------------------------------------------------------------------
# UI PRINCIPALE
# -------------------------------------------------------------------------

def render_tab_inputs():
    st.header("📁 Fichiers d’entrée — OneDrive + TMP")
    state = get_state()

    cloud_mode = IS_STREAMLIT_CLOUD
    if "source_error" in st.session_state:
        st.error(f"❌ {st.session_state['source_error']}")
    if cloud_mode and not is_graph_onedrive():
        st.warning(CLOUD_MESSAGE)

    if is_graph_onedrive():
        st.info("Mode OneDrive Graph actif. Connexion requise pour charger/écrire les fichiers.")
        client = cp.get_graph_client()
        if client is None:
            st.error("Graph non configuré : vérifier ASF_GRAPH_CLIENT_ID / ASF_GRAPH_TENANT_ID.")
        else:
            token_ok = client.acquire_token_silent() is not None
            if token_ok:
                st.success("Connexion OneDrive active.")
            else:
                flow_key = "graph_device_flow"
                if flow_key not in st.session_state and st.button("🔑 Se connecter à OneDrive"):
                    st.session_state[flow_key] = cp.begin_onedrive_device_flow()
                flow = st.session_state.get(flow_key)
                if flow and flow.get("message"):
                    st.info(flow["message"])
                    if st.button("✅ J'ai terminé l'authentification"):
                        ok = cp.complete_onedrive_device_flow(flow)
                        if ok:
                            st.success("Connexion OneDrive validée.")
                            st.session_state.pop(flow_key, None)
                            st.rerun()

    # Initialisation TMP si besoin (copies déjà préparées côté session context)
    ctx = get_session_context()
    if ctx is None:
        try:
            ctx = ensure_session_context(strict_sources=True)
        except FileNotFoundError as exc:
            st.session_state["source_error"] = str(exc)
            ctx = None

    if state.tdb_tmp is None:
        state.tdb_tmp = ctx.source_paths.tableau_de_bord if ctx else _default_tmp_path("tdb")
    if state.benev_tmp is None:
        state.benev_tmp = ctx.source_paths.planning_benevoles if ctx else _default_tmp_path("benev")
    if state.vols_tmp is None:
        state.vols_tmp = ctx.source_paths.vols if ctx else _default_tmp_path("vols")
    sync_state_paths_to_engine(state)

    # Chargements (évite d'afficher des erreurs sur Cloud si fichiers vides)
    if not cloud_mode or is_graph_onedrive() or state.tdb_tmp.stat().st_size > 0:
        load_tdb_file(state)
    if not cloud_mode or is_graph_onedrive() or state.benev_tmp.stat().st_size > 0:
        load_benev_file(state)
    if not cloud_mode or is_graph_onedrive() or state.vols_tmp.stat().st_size > 0:
        load_vols_file(state)

    # ----- bouton refresh global ----
    if (not cloud_mode or is_graph_onedrive()) and st.button("🔄 Recharger TOUS les fichiers depuis OneDrive"):
        refresh_all(state)

    # Sélecteur de période
    pick_planning_dates(state)

    col_tdb, col_benev, col_vols = st.columns(3)

    # ---------------------------------------------------------------------
    # TDB
    # ---------------------------------------------------------------------
    with col_tdb:
        st.subheader("📘 Tableau de bord")
        st.write(f"TMP : `{state.tdb_tmp.name}`")
        st.write(f"🕒 Modifié : {pretty_mtime(state.tdb_tmp)}")

        # BE planifiables
        try:
            df_be = load_shipments_df(planifiables_only=True, tdb_path=state.tdb_tmp)
            if df_be is not None and not df_be.empty:
                counts = (
                    df_be["Destination"]
                    .astype(str)
                    .str.strip()
                    .replace("", pd.NA)
                    .dropna()
                    .value_counts()
                    .to_dict()
                )
                st.write(
                    "📦 BE planifiables : "
                    + ", ".join([f"{d} ({c})" for d, c in counts.items()])
                )
            else:
                st.write("📦 Aucun BE planifiable.")
        except Exception as e:
            st.error(f"❌ Erreur BE : {e}")

        if (not cloud_mode or is_graph_onedrive()) and st.button("🔄 Recharger TDB depuis OneDrive"):
            refresh_from_onedrive(state, get_tableau_de_bord_src(), "tdb", load_tdb_file)

        file = st.file_uploader("Importer TABLEAU_DE_BORD.xlsx", type=["xlsx"], key="up_tdb")
        if file:
            overwrite_tmp_file(file, state, "tdb", load_tdb_file)

    # ---------------------------------------------------------------------
    # BENEVOLES
    # ---------------------------------------------------------------------
    with col_benev:
        st.subheader("👥 Bénévoles")
        st.write(f"TMP : `{state.benev_tmp.name}`")
        st.write(f"🕒 Modifié : {pretty_mtime(state.benev_tmp)}")
        st.write(f"Dernier message traité : {benev_last_message(state.benev_tmp)}")

        if (not cloud_mode or is_graph_onedrive()) and st.button("🔄 Recharger Bénévoles depuis OneDrive"):
            refresh_from_onedrive(state, get_planning_benevoles_src(), "benev", load_benev_file)

        file = st.file_uploader("Importer Planning Bénévoles.xlsx", type=["xlsx"], key="up_benev")
        if file:
            overwrite_tmp_file(file, state, "benev", load_benev_file)

    # ---------------------------------------------------------------------
    # VOLS
    # ---------------------------------------------------------------------
    with col_vols:
        st.subheader("✈️ Vols")
        st.write(f"TMP : `{state.vols_tmp.name}`")
        st.write(f"🕒 Modifié : {pretty_mtime(state.vols_tmp)}")

        # Semaine détectée
        try:
            dfv = state.df_vols
            if dfv is not None and "Date_Vol" in dfv.columns:
                dates = coerce_datetime(dfv["Date_Vol"], errors="coerce", dayfirst=True, format="%d/%m/%y")
                dates = dates.dropna()
                if not dates.empty:
                    dmin, dmax = dates.min(), dates.max()
                    st.write(f"🗓️ Du {dmin:%d/%m} au {dmax:%d/%m} "
                             f"(sem. {dmin.isocalendar()[1]})")
        except Exception as e:
            st.error(f"❌ Erreur lecture Vols : {e}")

        source_choice = st.radio(
            "Source vols",
            ["Fichier Excel", "API Air France (CDG ➜ ParamDest, AF)"],
            index=0 if state.vols_source != "api" else 1,
        )
        state.vols_source = "api" if source_choice.endswith("AF)") else "excel"

        if state.vols_source == "api":
            st.info(
                "Appel direct API Air France (origin CDG, operating AF) pour les destinations ParamDest. "
                "Limite 1 requête/s et 100/jour. Clé attendue dans `AF_API_KEY` (env ou secrets)."
            )
            cache_info = ""
            cache_path = get_tmp_dir() / "vols_api_cache.parquet"
            if cache_path.exists():
                mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
                cache_info = f"(cache du {mtime:%d/%m à %Hh%M})"
                st.write(f"Cache disponible {cache_info}")
                if st.button(f"Charger le dernier cache"):
                    try:
                        state.df_vols = pd.read_parquet(cache_path)
                        st.success(f"Vols chargés depuis cache {cache_info}")
                    except Exception as e:
                        st.error(f"❌ Erreur lecture cache : {e}")
            else:
                st.write("Aucun cache API disponible pour l'instant.")

            if state.api_start_date and state.api_end_date:
                if st.button("Appeler l'API Air France"):
                    try:
                        df_api = load_vols_api(state.api_start_date, state.api_end_date)
                        state.df_vols = df_api
                        if df_api is not None:
                            st.success(f"{len(df_api)} vols chargés via API (du {state.api_start_date:%d/%m} au {state.api_end_date:%d/%m}).")
                            try:
                                df_api.to_parquet(cache_path, index=False)
                            except Exception:
                                pass
                            # Sauvegarde dans Vols.xlsx (feuille API-SXX-YYYY en dernière position)
                            try:
                                sheet_name = store_vols_api_sheet(df_api, state.api_start_date)
                                st.info(f"Données API sauvegardées dans VOLS.xlsx (onglet {sheet_name}).")
                                # Copie dans la version TMP (VOLS) pour affichage immédiat
                                try:
                                    from loaders.load_vols_api import copy_api_sheet_to_tmp
                                    copy_api_sheet_to_tmp(sheet_name)
                                    from loaders.load_vols import load_vols_df
                                    state.df_vols = load_vols_df(
                                        vols_path=Path(state.vols_tmp),
                                        param_dest_df=state.df_param_dest,
                                    )
                                except Exception:
                                    pass
                            except Exception as e:
                                st.warning(f"Vols API chargés mais non sauvegardés dans Excel : {e}")
                        else:
                            st.warning("Aucun vol retourné par l'API.")
                    except Exception as e:
                        st.error(f"❌ Erreur API AF : {e}")
            else:
                st.warning("Sélectionne une période avant d'appeler l'API.")
        else:
            if (not cloud_mode or is_graph_onedrive()) and st.button("🔄 Recharger Vols depuis OneDrive"):
                refresh_from_onedrive(state, get_vols_src(), "vols", load_vols_file)

            file = st.file_uploader("Importer Vols.xlsx", type=["xlsx"], key="up_vols")
            if file:
                overwrite_tmp_file(file, state, "vols", load_vols_file)
