# -*- coding: utf-8 -*-
from __future__ import annotations

import asf_app.services.simulation_runner as sr


def test_run_ortools_simulation_forwards_parameters(monkeypatch):
    captured = {}

    def _fake_solver(**kwargs):
        captured.update(kwargs)
        return {"ok": True, "stats": {"runs": 1}}

    monkeypatch.setattr(sr, "solve_planning_ortools_simulation", _fake_solver)

    data_source_obj = object()
    result = sr.run_ortools_simulation(
        timeout_seconds=42,
        planifiables_only=False,
        verbose=True,
        priority_mode="benevoles",
        data_source_name="excel",
        data_source=data_source_obj,
        solver_version="v3",
    )

    assert result == {"ok": True, "stats": {"runs": 1}}
    assert captured == {
        "planifiables_only": False,
        "timeout_seconds": 42,
        "verbose": True,
        "priority_mode": "benevoles",
        "data_source": data_source_obj,
        "data_source_name": "excel",
        "solver_version": "v3",
    }


def test_run_ortools_simulation_dual_runs_both_modes(monkeypatch):
    calls = []

    def _fake_run(**kwargs):
        calls.append(kwargs["priority_mode"])
        return {"mode": kwargs["priority_mode"], "rows": 1}

    monkeypatch.setattr(sr, "run_ortools_simulation", _fake_run)

    result = sr.run_ortools_simulation_dual(
        timeout_seconds=99,
        planifiables_only=True,
        verbose=False,
        data_source_name="composite",
        data_source=None,
        solver_version="v2",
    )

    assert calls == ["colis", "benevoles"]
    assert result["selected"] == "colis"
    assert result["modes"]["colis"]["mode"] == "colis"
    assert result["modes"]["benevoles"]["mode"] == "benevoles"
