# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import asf_app.state as app_state
import scheduler.config_paths as cp
from asf_app.state import AppState, get_excel_source_paths, sync_state_paths_to_engine
from scheduler.data_sources import ExcelSourcePaths


def test_sync_state_paths_does_not_mutate_engine(monkeypatch, tmp_path):
    monkeypatch.setattr(app_state.st, "session_state", {})
    original_tdb = Path(cp.TABLEAU_DE_BORD)
    original_benev = Path(cp.PLANNING_BENEVOLES)
    original_vols = Path(cp.VOLS)

    state = AppState(
        tdb_tmp=tmp_path / "tdb.xlsx",
        benev_tmp=tmp_path / "benev.xlsx",
        vols_tmp=tmp_path / "vols.xlsx",
    )

    sync_state_paths_to_engine(state)

    assert Path(cp.TABLEAU_DE_BORD) == original_tdb
    assert Path(cp.PLANNING_BENEVOLES) == original_benev
    assert Path(cp.VOLS) == original_vols
    assert app_state.st.session_state["paths"]["tdb"].endswith("tdb.xlsx")


def test_get_excel_source_paths_uses_state(tmp_path):
    state = AppState(
        tdb_tmp=tmp_path / "tdb.xlsx",
        benev_tmp=tmp_path / "benev.xlsx",
        vols_tmp=tmp_path / "vols.xlsx",
    )
    paths = get_excel_source_paths(state)
    assert paths.tableau_de_bord.name == "tdb.xlsx"
    assert paths.planning_benevoles.name == "benev.xlsx"
    assert paths.vols.name == "vols.xlsx"


def test_app_state_log_appends():
    state = AppState()
    state.log("hello-state")
    assert state.last_engine_logs[-1] == "hello-state"


def test_sync_state_paths_ignores_cache_clear_failures(monkeypatch, tmp_path):
    monkeypatch.setattr(app_state.st, "session_state", {})
    state = AppState(
        tdb_tmp=tmp_path / "tdb.xlsx",
        benev_tmp=tmp_path / "benev.xlsx",
        vols_tmp=tmp_path / "vols.xlsx",
    )

    import loaders.load_benevoles as load_benevoles
    import loaders.load_params as load_params
    import loaders.load_shipments as load_shipments
    import loaders.load_vols as load_vols
    import scheduler.be_manager as be_manager

    monkeypatch.setattr(be_manager, "reset_param_be_cache", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    monkeypatch.setattr(load_params, "clear_param_caches", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    monkeypatch.setattr(load_shipments, "clear_shipments_cache", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    monkeypatch.setattr(load_benevoles, "clear_benevoles_cache", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    monkeypatch.setattr(load_vols, "clear_vols_cache", lambda: (_ for _ in ()).throw(RuntimeError("x")))

    sync_state_paths_to_engine(state)
    assert app_state.st.session_state["paths"]["tdb"].endswith("tdb.xlsx")


def test_get_tmp_dir_uses_session_context_when_available(monkeypatch, tmp_path):
    ctx = type("Ctx", (), {"tmp_dir": tmp_path / "ctx_tmp"})()
    monkeypatch.setattr(app_state, "_get_session_context", lambda: ctx)
    out = app_state.get_tmp_dir()
    assert out == ctx.tmp_dir
    assert out.exists()


def test_get_tmp_dir_falls_back_to_config_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(app_state, "_get_session_context", lambda: None)
    monkeypatch.setattr(cp, "TMP_DIR", tmp_path / "cp_tmp")
    out = app_state.get_tmp_dir()
    assert out == cp.TMP_DIR
    assert out.exists()


def test_app_state_planning_helpers_and_reset_all():
    state = AppState(
        tdb_tmp=Path("tdb.xlsx"),
        benev_tmp=Path("benev.xlsx"),
        vols_tmp=Path("vols.xlsx"),
    )
    assert state.has_all_inputs() is True

    state.set_planning(planning_df=object(), bilan_df=object(), scenario="demo")
    assert state.ready_for_communication is True
    assert state.last_scenario == "demo"

    state.clear_planning()
    assert state.planning_df is None
    assert state.bilan_df is None
    assert state.ready_for_communication is False
    assert state.last_engine_logs == []

    state.df_be = object()
    state.df_vols = object()
    state.df_benev = object()
    state.df_param_be = object()
    state.df_param_benev = object()
    state.df_param_dest = object()
    state.reset_all()
    assert state.df_be is None
    assert state.df_vols is None
    assert state.df_benev is None
    assert state.df_param_be is None
    assert state.df_param_benev is None
    assert state.df_param_dest is None


def test_get_state_and_reset_state_manage_streamlit_session(monkeypatch):
    monkeypatch.setattr(app_state.st, "session_state", {})
    first = app_state.get_state()
    second = app_state.get_state()
    assert first is second
    app_state.reset_state()
    third = app_state.get_state()
    assert third is not first


def test_get_excel_source_paths_uses_session_context_when_present(monkeypatch, tmp_path):
    ctx_paths = ExcelSourcePaths(
        tableau_de_bord=tmp_path / "ctx_tdb.xlsx",
        planning_benevoles=tmp_path / "ctx_benev.xlsx",
        vols=tmp_path / "ctx_vols.xlsx",
    )
    monkeypatch.setattr(app_state, "_get_session_context", lambda: type("Ctx", (), {"source_paths": ctx_paths})())
    out = app_state.get_excel_source_paths(AppState())
    assert out is ctx_paths
