# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import asf_app.state as app_state
import scheduler.config_paths as cp
from asf_app.state import AppState, get_excel_source_paths, sync_state_paths_to_engine


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
