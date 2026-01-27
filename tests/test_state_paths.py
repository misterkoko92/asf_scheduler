# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from asf_app.state import AppState, get_excel_source_paths, sync_state_paths_to_engine
import scheduler.config_paths as cp
import asf_app.state as app_state


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
