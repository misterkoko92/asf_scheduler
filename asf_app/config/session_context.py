# -*- coding: utf-8 -*-
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import streamlit as st

import scheduler.config_paths as cp
from scheduler.data_sources import ExcelSourcePaths

from .app_config import AppConfig, build_app_config

SESSION_CTX_KEY = "session_context"

SESSION_CONTEXT_ERRORS = (
    FileNotFoundError,
    OSError,
    PermissionError,
    RuntimeError,
    TypeError,
    ValueError,
    AttributeError,
    ImportError,
)


@dataclass
class SessionContext:
    config: AppConfig
    session_id: str
    tmp_dir: Path
    source_paths: ExcelSourcePaths


def _copy_source(src: Path, dst: Path, *, strict: bool) -> None:
    if not src.exists():
        if strict:
            raise FileNotFoundError(f"Source introuvable: {src}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.touch(exist_ok=True)
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _download_source(remote_path: str, dst: Path, *, strict: bool) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        cp.download_onedrive_file(remote_path, dst, interactive=False)
    except SESSION_CONTEXT_ERRORS:
        if strict:
            raise FileNotFoundError(f"Source OneDrive introuvable: {remote_path}")
    if strict and not dst.exists():
        raise FileNotFoundError(f"Source OneDrive introuvable: {remote_path}")


def _prepare_session_sources(config: AppConfig, tmp_dir: Path, *, strict_sources: bool) -> ExcelSourcePaths:
    tdb_dst = tmp_dir / "TABLEAU_DE_BORD.xlsx"
    benev_dst = tmp_dir / "PLANNING_BENEVOLES.xlsx"
    vols_dst = tmp_dir / "VOLS.xlsx"

    if config.use_graph_onedrive:
        _download_source(config.tableau_de_bord_remote, tdb_dst, strict=strict_sources)
        _download_source(config.planning_benevoles_remote, benev_dst, strict=strict_sources)
        _download_source(config.vols_remote, vols_dst, strict=strict_sources)
    else:
        benev_src = (
            config.planning_benevoles_src
            if config.planning_benevoles_src.exists()
            else config.planning_benevoles_src_legacy
        )
        _copy_source(config.tableau_de_bord_src, tdb_dst, strict=strict_sources)
        _copy_source(benev_src, benev_dst, strict=strict_sources)
        _copy_source(config.vols_src, vols_dst, strict=strict_sources)

    return ExcelSourcePaths(
        tableau_de_bord=tdb_dst,
        planning_benevoles=benev_dst,
        vols=vols_dst,
    )


def _sync_state_from_context(ctx: SessionContext) -> None:
    try:
        from asf_app.state import get_state

        state = get_state()
        state.tdb_tmp = ctx.source_paths.tableau_de_bord
        state.benev_tmp = ctx.source_paths.planning_benevoles
        state.vols_tmp = ctx.source_paths.vols
    except (ImportError, AttributeError, RuntimeError, TypeError, ValueError):
        return


def create_session_context(*, strict_sources: bool = False) -> SessionContext:
    config = build_app_config(strict_sources=strict_sources)
    session_id = st.session_state.get("session_id") or str(uuid4())
    st.session_state["session_id"] = session_id
    tmp_dir = config.tmp_dir_base / f"session_{session_id}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    source_paths = _prepare_session_sources(config, tmp_dir, strict_sources=strict_sources)
    ctx = SessionContext(
        config=config,
        session_id=session_id,
        tmp_dir=tmp_dir,
        source_paths=source_paths,
    )
    _sync_state_from_context(ctx)
    return ctx


def ensure_session_context(*, strict_sources: bool = False) -> SessionContext:
    ctx = st.session_state.get(SESSION_CTX_KEY)
    if isinstance(ctx, SessionContext):
        return ctx
    ctx = create_session_context(strict_sources=strict_sources)
    st.session_state[SESSION_CTX_KEY] = ctx
    return ctx


def get_session_context() -> SessionContext | None:
    ctx = st.session_state.get(SESSION_CTX_KEY)
    return ctx if isinstance(ctx, SessionContext) else None


def refresh_session_context(*, strict_sources: bool = False) -> SessionContext:
    """
    Force un rechargement des sources dans le TMP de session.
    """
    ctx = ensure_session_context(strict_sources=strict_sources)
    source_paths = _prepare_session_sources(ctx.config, ctx.tmp_dir, strict_sources=strict_sources)
    new_ctx = SessionContext(
        config=ctx.config,
        session_id=ctx.session_id,
        tmp_dir=ctx.tmp_dir,
        source_paths=source_paths,
    )
    st.session_state[SESSION_CTX_KEY] = new_ctx
    _sync_state_from_context(new_ctx)
    return new_ctx
