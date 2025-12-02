# asf_app/config/paths.py
# -*- coding: utf-8 -*-
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import scheduler.config_paths as engine_paths


# =====================================================================
#  AppPaths : couche "interface" entre Streamlit et le moteur
# =====================================================================
@dataclass
class AppPaths:
    """
    Représente les 3 fichiers sources utilisés dans l'UI :
    - TABLEAU DE BORD (TDB)
    - PLANNING BENEVOLES (Benev)
    - VOLS (Vols.xlsx)

    L’UI manipule seulement AppPaths.
    Le moteur lit seulement scheduler.config_paths.*
    sync_to_engine() permet d’injecter les choix utilisateurs dans le moteur.
    """

    tdb: Path
    benev: Path
    vols: Path

    # -----------------------------------------------------------------
    # Création depuis st.session_state.paths (UI)
    # -----------------------------------------------------------------
    @classmethod
    def from_session(cls, session_paths: Dict[str, str]) -> "AppPaths":
        """
        session_paths provient de l’UI :
        st.session_state.paths = {"tdb": "...", "benev": "...", "vols": "..."}
        """
        return cls(
            tdb=Path(session_paths["tdb"]).resolve(),
            benev=Path(session_paths["benev"]).resolve(),
            vols=Path(session_paths["vols"]).resolve(),
        )

    # -----------------------------------------------------------------
    # Génération automatique depuis les valeurs par défaut du moteur
    # (fallback silencieux si aucun fichier importé par l’utilisateur)
    # -----------------------------------------------------------------
    @classmethod
    def from_engine_defaults(cls) -> "AppPaths":
        """
        Fallback permettant d’utiliser les chemins trouvés automatiquement
        par scheduler.config_paths (OneDrive ou fallback local).
        """
        # On s'assure que les fichiers temporaires sont préparés avant de lire
        engine_paths.prepare_paths(copy_sources=True)
        return cls(
            tdb=Path(engine_paths.TABLEAU_DE_BORD).resolve(),
            benev=Path(engine_paths.PLANNING_BENEVOLES).resolve(),
            vols=Path(engine_paths.VOLS).resolve(),
        )

    # -----------------------------------------------------------------
    # Conversion vers format session_state
    # -----------------------------------------------------------------
    def to_session_dict(self) -> Dict[str, str]:
        """Utilisé pour mettre à jour st.session_state.paths."""
        return {
            "tdb": str(self.tdb),
            "benev": str(self.benev),
            "vols": str(self.vols),
        }

    # -----------------------------------------------------------------
    # Synchronisation vers le moteur
    # -----------------------------------------------------------------
    def sync_to_engine(self) -> None:
        """
        Applique les chemin sélectionnés par l’utilisateur
        -> directement dans scheduler.config_paths.

        ATTENTION :
        - Cette méthode doit être appelée AVANT tout appel au moteur.
        - Utilisée dans app.py après le chargement des fichiers.
        """
        engine_paths.TABLEAU_DE_BORD = self.tdb
        engine_paths.PLANNING_BENEVOLES = self.benev
        engine_paths.VOLS = self.vols

        # Dans ta version plus avancée, tu peux ajouter :
        # engine_paths._update_internal_temp_paths()
        # pour re-générer automatiquement les fichiers temporaires.

    # -----------------------------------------------------------------
    # Vérification utilitaire (affichage dans UI)
    # -----------------------------------------------------------------
    def exists(self) -> Dict[str, bool]:
        """
        Permet d’afficher dans l’UI si les 3 fichiers existent réellement.
        """
        return {
            "tdb": self.tdb.exists(),
            "benev": self.benev.exists(),
            "vols": self.vols.exists(),
        }
