# asf_app/config/directories.py
# -*- coding: utf-8 -*-
"""
Gestion centralisée des dossiers utilisés par l’UI Streamlit.

Ce module :
- remplace l'ancien path_manager
- fournit un point unique pour tous les chemins configurables
- persiste dans st.session_state
- peut synchroniser certains chemins vers scheduler.config_paths (moteur)
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import streamlit as st
import scheduler.config_paths as engine_paths


# =====================================================================
#  Utilitaires
# =====================================================================

def normalize(path: Path) -> Path:
    """Nettoyage standard (expanduser + resolve)."""
    return Path(str(path)).expanduser().resolve()


# =====================================================================
#  AppDirectories : gestion de TOUS les dossiers UI
# =====================================================================

@dataclass
class AppDirectories:
    """
    Gère les dossiers utilisés par l’UI :

    - planning_validated : dossiers où les plannings validés sont stockés/lus
    - exports            : dossier d'export (PDF, fichiers utilisateurs…)
    - logs               : dossier pour logs UI/scheduler
    """

    planning_validated: Path
    exports: Path
    logs: Path

    # -----------------------------------------------------------------
    #  Constructeurs
    # -----------------------------------------------------------------

    @classmethod
    def default(cls) -> "AppDirectories":
        """
        Valeurs par défaut → OneDrive ASF (détection auto par l’engine).
        Utilisées au premier lancement.
        """
        base = engine_paths.ASF_ONEDRIVE

        return cls(
            planning_validated=normalize(
                base / "Planning MAB" / "ASFmm PLANNING 2025"
            ),
            exports=normalize(
                base / "Planning MAB" / "Exports"
            ),
            logs=normalize(
                Path.home() / ".asf_scheduler_logs"
            ),
        )

    # -----------------------------------------------------------------
    #  Reconstruction depuis dictionnaire (session Streamlit)
    # -----------------------------------------------------------------

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "AppDirectories":
        return cls(
            planning_validated=normalize(Path(data["planning_validated"])),
            exports=normalize(Path(data["exports"])),
            logs=normalize(Path(data["logs"])),
        )

    @classmethod
    def load_from_session(cls) -> "AppDirectories":
        """
        Charge AppDirectories depuis st.session_state["directories"].
        Si absent → crée avec defaults.
        """
        if "directories" not in st.session_state:
            inst = cls.default()
            st.session_state["directories"] = inst.to_dict()
            return inst

        return cls.from_dict(st.session_state["directories"])

    # -----------------------------------------------------------------
    #  Serialisation Streamlit
    # -----------------------------------------------------------------

    def to_dict(self) -> Dict[str, str]:
        return {
            "planning_validated": str(self.planning_validated),
            "exports": str(self.exports),
            "logs": str(self.logs),
        }

    def to_session(self):
        st.session_state["directories"] = self.to_dict()

    # -----------------------------------------------------------------
    #  Vérification existence
    # -----------------------------------------------------------------

    def exists(self) -> Dict[str, bool]:
        """Pour affichage dans l’UI."""
        return {
            "planning_validated": self.planning_validated.exists(),
            "exports": self.exports.exists(),
            "logs": self.logs.exists(),
        }

    # -----------------------------------------------------------------
    #  Synchronisation vers moteur
    # -----------------------------------------------------------------

    def sync_to_engine(self):
        """
        Propager certaines valeurs UI vers le moteur.

        ⚠ On ne synchronise pas planning_validated → réservé à l'UI.
        """
        # Le moteur utilise OUTPUT_PLANNING_DIR pour PLANNING/BILAN
        engine_paths.OUTPUT_PLANNING_DIR = normalize(self.exports)

        # Création des dossiers si absents
        self.planning_validated.mkdir(parents=True, exist_ok=True)
        self.exports.mkdir(parents=True, exist_ok=True)
        self.logs.mkdir(parents=True, exist_ok=True)
