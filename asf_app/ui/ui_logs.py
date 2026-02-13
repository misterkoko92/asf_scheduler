# asf_app/ui/ui_logs.py
# -*- coding: utf-8 -*-

from __future__ import annotations

import io
import os
import pathlib
import platform
import shutil
import sys
import zipfile
from datetime import datetime

import streamlit as st

import scheduler.config_paths as cp
from asf_app.config.runtime import (
    get_listes_colisage_remote_dir,
    get_output_planning_dir,
    get_output_remote_dir_template,
    get_planning_benevoles_remote,
    get_tableau_de_bord_remote,
    get_tmp_dir,
    get_vols_remote,
    is_graph_onedrive,
)
from utils.datetime_utils import format_date_value

# =============================================================================
# 🔍 Détermination robuste de l’emplacement réel du fichier de logs
# =============================================================================

def resolve_log_file() -> pathlib.Path:
    """
    Détecte le fichier de logs selon l’environnement :
      • Développement (venv / streamlit run)
      • PyInstaller Windows (.exe)
      • PyInstaller macOS (.app)

    Renvoie un path SYSTEMATIQUE → asf_scheduler.log
    """

    # ----------------------------------------
    # 1) Version PyInstaller (Windows/.exe ou macOS/.app)
    # ----------------------------------------
    if getattr(sys, "frozen", False):
        # sys.executable = .../ASF Scheduler.app/Contents/MacOS/ASF Scheduler
        base = pathlib.Path(sys.executable).resolve().parent
        log_path = base / "asf_scheduler.log"
        return log_path

    # ----------------------------------------
    # 2) Version dev (Streamlit, venv, IDE)
    # ----------------------------------------
    return get_tmp_dir() / "asf_scheduler.log"


LOG_FILE = resolve_log_file()

# OneDrive cible
LOG_FILE_ONEDRIVE = get_output_planning_dir() / "asf_scheduler.log"


# =============================================================================
# 🧩 HELPERS
# =============================================================================

def pretty_mtime(path: pathlib.Path) -> str:
    """Retourne la dernière modification formatée."""
    try:
        ts = os.path.getmtime(path)
        return format_date_value(datetime.fromtimestamp(ts), fmt="%d/%m/%Y %H:%M:%S", default="N/A")
    except (OSError, TypeError, ValueError):
        return "N/A"


def write_log_file(path: pathlib.Path, content: str) -> bool:
    """
    Écrit dans le fichier log.
    Gère les répertoires manquants + erreurs de permission.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return True
    except (OSError, TypeError, ValueError) as e:
        st.error(f"⚠️ Impossible d'écrire dans le fichier log : {e}")
        return False


def sync_to_onedrive(tmp_log: pathlib.Path) -> bool:
    """
    Copie TMP → OneDrive si activé.
    """
    try:
        LOG_FILE_ONEDRIVE.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(tmp_log, LOG_FILE_ONEDRIVE)
        return True
    except (OSError, shutil.Error, TypeError, ValueError) as e:
        st.error(f"⚠️ Impossible de synchroniser vers OneDrive : {e}")
        return False


def read_log_file(path: pathlib.Path) -> str:
    """Lecture robuste du fichier de logs."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except (OSError, TypeError, ValueError) as e:
        st.error(f"⚠️ Erreur lors de la lecture des logs : {e}")
        return ""

def build_logs_export_bundle(log_path: pathlib.Path) -> bytes:
    """
    Create a zip bundle containing logs + minimal context info.
    Avoids dumping sensitive environment variables.
    """
    logs = read_log_file(log_path) if log_path.exists() else ""
    version_path = cp.BASE_DIR / "VERSION"
    app_version = "unknown"
    try:
        if version_path.exists():
            app_version = version_path.read_text(encoding="utf-8").strip()
    except (OSError, TypeError, ValueError):
        app_version = "unknown"
    info_lines = [
        f"timestamp={format_date_value(datetime.now(), fmt='%Y-%m-%d %H:%M:%S', default='')}",
        f"python={sys.version}",
        f"platform={platform.platform()}",
        f"streamlit_version={getattr(st, '__version__', 'unknown')}",
        f"app_version={app_version}",
        f"cwd={os.getcwd()}",
        f"streamlit_cloud={cp.IS_STREAMLIT_CLOUD}",
        f"onedrive_mode_graph={is_graph_onedrive()}",
        f"onedrive_mode={cp.ONEDRIVE_MODE}",
        f"graph_configured={bool(cp.GRAPH_CLIENT_ID and cp.GRAPH_TENANT_ID)}",
        f"tmp_dir={get_tmp_dir()}",
        f"output_dir={get_output_planning_dir()}",
        f"tdb_remote={get_tableau_de_bord_remote()}",
        f"benev_remote={get_planning_benevoles_remote()}",
        f"vols_remote={get_vols_remote()}",
        f"colisage_remote_dir={get_listes_colisage_remote_dir()}",
        f"output_remote_template={get_output_remote_dir_template()}",
        f"log_file={log_path}",
        f"log_exists={log_path.exists()}",
    ]
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("asf_scheduler.log", logs)
        zf.writestr("context.txt", "\n".join(info_lines))
    return payload.getvalue()


# =============================================================================
# 🖥️ INTERFACE
# =============================================================================

def render_tab_logs():

    st.header("📜 Logs du moteur ASF — Diagnostic & suivi")

    # ----------------------------------------------------------------------
    # MODE EXPERT : synchronisation OneDrive
    # ----------------------------------------------------------------------
    sync_enabled = st.checkbox(
        "☁️ Synchroniser également dans OneDrive (mode expert, avancé)",
        help=(
            "Active la synchronisation vers OneDrive. "
            "Recommandé uniquement pour partager les logs entre plusieurs machines."
        ),
        value=False,
        key="log_sync_choice"
    )

    st.caption(f"📄 Local : `{LOG_FILE}`")
    if sync_enabled:
        st.caption(f"☁️ OneDrive : `{LOG_FILE_ONEDRIVE}`")

    st.markdown("---")

    # ----------------------------------------------------------------------
    # ACTIONS
    # ----------------------------------------------------------------------
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])

    with col1:
        reload_now = st.button("🔄 Recharger", width="stretch")

    with col2:
        clear = st.button("🗑️ Vider le log", width="stretch")

    with col3:
        download = st.button("⬇ Télécharger le log", width="stretch")
    with col4:
        st.download_button(
            "📤 Exporter logs",
            data=build_logs_export_bundle(LOG_FILE),
            file_name="asf_logs_export.zip",
            mime="application/zip",
            use_container_width=True,
        )

    # ----------------------------------------------------------------------
    # Vidage du fichier
    # ----------------------------------------------------------------------
    if clear:
        ok = write_log_file(LOG_FILE, "")
        if ok and sync_enabled:
            sync_to_onedrive(LOG_FILE)
        st.success("✔ Log vidé.")
        st.experimental_rerun()
        return

    # ----------------------------------------------------------------------
    # Lecture du fichier
    # ----------------------------------------------------------------------
    if not LOG_FILE.exists():
        st.info("Aucun log trouvé. Le moteur n'a peut-être rien écrit pour l’instant.")
        try:
            LOG_FILE.touch()
        except OSError:
            pass
        return

    logs = read_log_file(LOG_FILE)

    # ----------------------------------------------------------------------
    # Infos fichier
    # ----------------------------------------------------------------------
    size = LOG_FILE.stat().st_size if LOG_FILE.exists() else 0

    st.caption(
        f"📦 Taille : {size} octets — 🕒 Modifié : {pretty_mtime(LOG_FILE)}"
    )

    # ----------------------------------------------------------------------
    # Zone d’affichage
    # ----------------------------------------------------------------------
    st.text_area(
        "Logs ASF",
        value=logs,
        height=600,
        key="log_content_display"
    )

    # Bouton pour afficher le contenu brut (diagnostic)
    with st.expander("Afficher le contenu brut (diagnostic)"):
        try:
            raw = LOG_FILE.read_bytes()
            st.code(raw.decode("utf-8", errors="replace"))
        except OSError as e:
            st.error(f"Erreur lecture brut : {e}")

    # ----------------------------------------------------------------------
    # Téléchargement
    # ----------------------------------------------------------------------
    if download:
        st.download_button(
            "⬇ Télécharger asf_scheduler.log",
            data=logs.encode("utf-8"),
            file_name="asf_scheduler.log",
            mime="text/plain"
        )

    # ----------------------------------------------------------------------
    # Reload
    # ----------------------------------------------------------------------
    if reload_now:
        # Compat Streamlit >=1.30 (st.rerun) et anciens (experimental_rerun)
        try:
            if hasattr(st, "rerun"):
                st.rerun()
            else:
                st.experimental_rerun()
        except (AttributeError, RuntimeError):
            pass

    st.markdown("---")

    # ----------------------------------------------------------------------
    # Bloc diagnostic technique (optionnel)
    # ----------------------------------------------------------------------
    with st.expander("🛠️ Diagnostic technique (environnement)", expanded=False):

        st.write("**Mode exécution** :")
        st.code(
            f"sys.frozen = {getattr(sys, 'frozen', False)}\n"
            f"executable = {sys.executable}\n"
            f"cwd = {os.getcwd()}"
        )

        st.write("**Emplacements détectés** :")
        st.code(
            f"LOG_FILE = {LOG_FILE}\n"
            f"LOG_FILE_ONEDRIVE = {LOG_FILE_ONEDRIVE}"
        )

        st.write("**Permissions** :")
        try:
            test = LOG_FILE.open("a")
            test.close()
            st.success("✔ Écriture locale autorisée")
        except OSError as e:
            st.error(f"❌ Écriture locale impossible : {e}")

        if sync_enabled:
            try:
                LOG_FILE_ONEDRIVE.parent.mkdir(parents=True, exist_ok=True)
                st.success("✔ OneDrive accessible")
            except OSError as e:
                st.error(f"❌ OneDrive inaccessible : {e}")
