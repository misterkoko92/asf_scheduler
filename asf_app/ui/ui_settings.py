# asf_app/ui/ui_settings.py
# -*- coding: utf-8 -*-

"""
Onglet : Réglages des chemins
Permet de configurer :
 - le dossier des plannings validés
 - le dossier des exports
 - le dossier des logs
avec persistance dans st.session_state
et synchronisation avec le moteur (scheduler.config_paths).
"""

import streamlit as st
from pathlib import Path

from asf_app.config.directories import AppDirectories


# =====================================================================
#  Utilitaires internes
# =====================================================================

def _ensure_session_dirs():
    """
    Initialise st.session_state.directories avec les valeurs par défaut
    à la première ouverture.
    """
    if "directories" not in st.session_state:
        default = AppDirectories.default()
        st.session_state.directories = default.to_session_dict()


def _load_dirs() -> AppDirectories:
    """Charge AppDirectories depuis session_state."""
    return AppDirectories.from_session(st.session_state["directories"])


def _save_dirs(dirs: AppDirectories):
    """Sauvegarde AppDirectories → session_state."""
    st.session_state["directories"] = dirs.to_session_dict()


# =====================================================================
#  UI PRINCIPALE
# =====================================================================

def render_tab_settings():

    st.header("⚙️ Réglages des chemins")

    _ensure_session_dirs()
    dirs = _load_dirs()

    st.markdown(
        """
        Configure les dossiers utilisés par l'application :
        - 📁 **Planning validés** (chargés dans l’onglet Communications)
        - 📂 **Exports / résultats** du moteur
        - 🧾 **Logs** (optionnel)
        """
    )
    st.divider()

    # -------------------------------------------------------------
    # 1) Affichage + sélecteur : dossier plannings validés
    # -------------------------------------------------------------

    st.subheader("📁 Dossier des plannings validés")

    col1, col2 = st.columns([3, 1])

    with col1:
        st.text_input(
            "Chemin du dossier",
            value=str(dirs.planning_validated),
            key="dir_planning_validated",
        )

    with col2:
        if dirs.planning_validated.exists():
            st.success("✓ Existe")
        else:
            st.error("✗ Introuvable")

    st.markdown("**Sélectionner un nouveau dossier :**")
    new_pv = st.file_uploader(
        "Choisir un fichier dans le dossier voulu",
        type=["xlsx"],
        key="dir_picker_pv",
    )
    if new_pv is not None:
        chosen_dir = Path(new_pv.name).expanduser().resolve().parent
        dirs.planning_validated = chosen_dir
        _save_dirs(dirs)
        st.success(f"Dossier mis à jour : {chosen_dir}")

    st.divider()

    # -------------------------------------------------------------
    # 2) Dossier EXPORTS
    # -------------------------------------------------------------

    st.subheader("📂 Dossier export moteur")

    col1, col2 = st.columns([3, 1])
    with col1:
        st.text_input(
            "Chemin export",
            value=str(dirs.exports),
            key="dir_exports",
        )
    with col2:
        st.success("✓ Existe") if dirs.exports.exists() else st.error("✗ Introuvable")

    new_exp = st.file_uploader(
        "Choisir un fichier dans le dossier voulu",
        type=["xlsx"],
        key="dir_picker_exports",
    )
    if new_exp is not None:
        chosen = Path(new_exp.name).expanduser().resolve().parent
        dirs.exports = chosen
        _save_dirs(dirs)
        st.success(f"Dossier mis à jour : {chosen}")

    st.divider()

    # -------------------------------------------------------------
    # 3) Dossier LOGS
    # -------------------------------------------------------------

    st.subheader("🧾 Dossier logs")

    col1, col2 = st.columns([3, 1])
    with col1:
        st.text_input(
            "Chemin logs",
            value=str(dirs.logs),
            key="dir_logs",
        )
    with col2:
        st.success("✓ Existe") if dirs.logs.exists() else st.error("✗ Introuvable")

    new_logs = st.file_uploader(
        "Choisir un fichier dans le dossier voulu",
        type=["txt", "log"],
        key="dir_picker_logs",
    )
    if new_logs is not None:
        chosen = Path(new_logs.name).expanduser().resolve().parent
        dirs.logs = chosen
        _save_dirs(dirs)
        st.success(f"Dossier mis à jour : {chosen}")

    st.divider()

    # -------------------------------------------------------------
    # 4) Boutons action
    # -------------------------------------------------------------

    colA, colB, colC = st.columns(3)

    # --- enregistrer ---
    with colA:
        if st.button("💾 Enregistrer dans la session"):
            dirs = AppDirectories(
                planning_validated=Path(st.session_state["dir_planning_validated"]),
                exports=Path(st.session_state["dir_exports"]),
                logs=Path(st.session_state["dir_logs"])
            )
            _save_dirs(dirs)
            st.success("Chemins enregistrés dans la session.")

    # --- sync moteur ---
    with colB:
        if st.button("🔄 Synchroniser avec le moteur"):
            dirs.sync_to_engine()
            st.success("Chemins synchronisés avec le moteur.")

    # --- reset ---
    with colC:
        if st.button("♻️ Restaurer valeurs par défaut"):
            default = AppDirectories.default()
            _save_dirs(default)
            st.success("Valeurs par défaut restaurées.")

    st.divider()

    st.caption("Ces réglages sont utilisés par l’onglet Communication et les exports.")
