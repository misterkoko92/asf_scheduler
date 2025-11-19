# asf_app/config/paths.py
# -*- coding: utf-8 -*-
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import scheduler.config_paths as engine_paths


@dataclass
class AppPaths:
    tdb: Path
    benev: Path
    vols: Path

    @classmethod
    def from_session(cls, session_paths: Dict[str, str]) -> "AppPaths":
        return cls(
            tdb=Path(session_paths["tdb"]),
            benev=Path(session_paths["benev"]),
            vols=Path(session_paths["vols"]),
        )

    @classmethod
    def from_engine_defaults(cls) -> "AppPaths":
        """Permettrait de se baser sur les valeurs définies dans scheduler.config_paths."""
        return cls(
            tdb=engine_paths.TABLEAU_DE_BORD,
            benev=engine_paths.PLANNING_BENEVOLES,
            vols=engine_paths.VOLS,
        )

    def to_session_dict(self) -> Dict[str, str]:
        return {
            "tdb": str(self.tdb),
            "benev": str(self.benev),
            "vols": str(self.vols),
        }

    def sync_to_engine(self) -> None:
        """Applique les chemins courants dans les variables du moteur."""
        engine_paths.TABLEAU_DE_BORD = self.tdb
        engine_paths.PLANNING_BENEVOLES = self.benev
        engine_paths.VOLS = self.vols
