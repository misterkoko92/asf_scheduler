# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from typing import Optional

import scheduler.config_paths as cp


def _get_session_context():
    try:
        from asf_app.config.session_context import get_session_context
        return get_session_context()
    except Exception:
        return None


def get_app_config():
    ctx = _get_session_context()
    return ctx.config if ctx is not None else None


def get_tmp_dir() -> Path:
    ctx = _get_session_context()
    if ctx is not None:
        return ctx.tmp_dir
    return cp.TMP_DIR


def get_onedrive_root() -> Path:
    cfg = get_app_config()
    return cfg.onedrive_root if cfg is not None else cp.ASF_ONEDRIVE


def get_output_planning_dir() -> Path:
    cfg = get_app_config()
    return cfg.output_planning_dir if cfg is not None else cp.OUTPUT_PLANNING_DIR


def is_graph_onedrive() -> bool:
    cfg = get_app_config()
    return cfg.use_graph_onedrive if cfg is not None else cp.is_graph_onedrive()


def get_tableau_de_bord_src() -> Path:
    cfg = get_app_config()
    return cfg.tableau_de_bord_src if cfg is not None else cp.TABLEAU_DE_BORD_SRC


def get_planning_benevoles_src() -> Path:
    cfg = get_app_config()
    return cfg.planning_benevoles_src if cfg is not None else cp.PLANNING_BENEVOLES_SRC


def get_planning_benevoles_src_legacy() -> Path:
    cfg = get_app_config()
    return cfg.planning_benevoles_src_legacy if cfg is not None else cp.PLANNING_BENEVOLES_SRC_LEGACY


def get_vols_src() -> Path:
    cfg = get_app_config()
    return cfg.vols_src if cfg is not None else cp.VOLS_SRC


def get_tableau_de_bord_remote() -> str:
    cfg = get_app_config()
    return cfg.tableau_de_bord_remote if cfg is not None else cp.TABLEAU_DE_BORD_REMOTE


def get_planning_benevoles_remote() -> str:
    cfg = get_app_config()
    return cfg.planning_benevoles_remote if cfg is not None else cp.PLANNING_BENEVOLES_REMOTE


def get_vols_remote() -> str:
    cfg = get_app_config()
    return cfg.vols_remote if cfg is not None else cp.VOLS_REMOTE


def get_listes_colisage_remote_dir() -> str:
    cfg = get_app_config()
    return cfg.listes_colisage_remote_dir if cfg is not None else cp.LISTES_COLISAGE_REMOTE_DIR


def get_output_remote_dir_template() -> str:
    cfg = get_app_config()
    return cfg.output_planning_remote_dir_template if cfg is not None else cp.OUTPUT_PLANNING_REMOTE_DIR_TEMPLATE


def get_output_remote_dir(year: int) -> str:
    template = get_output_remote_dir_template()
    return template.format(year=year)


def get_output_remote_path(year: int, filename: str) -> str:
    return f"{get_output_remote_dir(year).strip('/')}/{filename}"
