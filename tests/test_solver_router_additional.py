# -*- coding: utf-8 -*-
from __future__ import annotations

import pandas as pd

import scheduler.solver_router as router


def test_normalize_version_variants():
    assert router._normalize_version(None) == "v3"
    assert router._normalize_version("v2") == "v2"
    assert router._normalize_version("2") == "v2"
    assert router._normalize_version("V3") == "v3"
    assert router._normalize_version("3") == "v3"
    assert router._normalize_version("unknown") == "v3"


def test_get_solver_version_explicit_overrides_env(monkeypatch):
    monkeypatch.setenv("ASF_SOLVER_VERSION", "v2")
    assert router.get_solver_version(explicit="v3") == "v3"


def test_solve_planning_ortools_dispatches_both_versions(monkeypatch):
    out_v2 = (pd.DataFrame([{"mode": "v2"}]), pd.DataFrame(), {"v": 2})
    out_v3 = (pd.DataFrame([{"mode": "v3"}]), pd.DataFrame(), {"v": 3})
    monkeypatch.setattr(router, "solve_planning_ortools_v2", lambda **_kwargs: out_v2)
    monkeypatch.setattr(router, "solve_planning_ortools_v3", lambda **_kwargs: out_v3)

    assert router.solve_planning_ortools(solver_version="v2")[2]["v"] == 2
    assert router.solve_planning_ortools(solver_version="v3")[2]["v"] == 3


def test_solve_planning_ortools_simulation_dispatches_both_versions(monkeypatch):
    out_v2 = {"solver": "v2", "planning_df": pd.DataFrame()}
    out_v3 = {"solver": "v3", "planning_df": pd.DataFrame()}
    monkeypatch.setattr(router, "solve_planning_ortools_simulation_v2", lambda **_kwargs: out_v2)
    monkeypatch.setattr(router, "solve_planning_ortools_simulation_v3", lambda **_kwargs: out_v3)

    assert router.solve_planning_ortools_simulation(solver_version="v2")["solver"] == "v2"
    assert router.solve_planning_ortools_simulation(solver_version="v3")["solver"] == "v3"
