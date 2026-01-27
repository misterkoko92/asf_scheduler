# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import scheduler.config_paths as cp


@dataclass(frozen=True)
class AppConfig:
    onedrive_root: Path
    tmp_dir_base: Path
    output_planning_dir: Path
    use_graph_onedrive: bool
    is_streamlit_cloud: bool
    tableau_de_bord_src: Path
    planning_benevoles_src: Path
    planning_benevoles_src_legacy: Path
    vols_src: Path
    tableau_de_bord_remote: str
    planning_benevoles_remote: str
    vols_remote: str
    listes_colisage_remote_dir: str
    output_planning_remote_dir_template: str


def build_app_config(*, strict_sources: bool = False) -> AppConfig:
    """
    Snapshot immuable de la configuration runtime (évite les globals mutables).
    """
    cp.prepare_paths(copy_sources=False, strict_sources=strict_sources)
    return AppConfig(
        onedrive_root=Path(cp.ASF_ONEDRIVE),
        tmp_dir_base=Path(cp.TMP_DIR),
        output_planning_dir=Path(cp.OUTPUT_PLANNING_DIR),
        use_graph_onedrive=bool(cp.USE_GRAPH_ONEDRIVE),
        is_streamlit_cloud=bool(cp.IS_STREAMLIT_CLOUD),
        tableau_de_bord_src=Path(cp.TABLEAU_DE_BORD_SRC),
        planning_benevoles_src=Path(cp.PLANNING_BENEVOLES_SRC),
        planning_benevoles_src_legacy=Path(cp.PLANNING_BENEVOLES_SRC_LEGACY),
        vols_src=Path(cp.VOLS_SRC),
        tableau_de_bord_remote=str(cp.TABLEAU_DE_BORD_REMOTE),
        planning_benevoles_remote=str(cp.PLANNING_BENEVOLES_REMOTE),
        vols_remote=str(cp.VOLS_REMOTE),
        listes_colisage_remote_dir=str(cp.LISTES_COLISAGE_REMOTE_DIR),
        output_planning_remote_dir_template=str(cp.OUTPUT_PLANNING_REMOTE_DIR_TEMPLATE),
    )
