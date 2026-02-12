# -*- coding: utf-8 -*-
"""
Service dédié au lancement du solveur OR-Tools en mode simulation.
L'UI reste simple et appelle uniquement ces fonctions.
"""

from __future__ import annotations

from typing import Any, Dict

from scheduler.solver_router import solve_planning_ortools_simulation
from scheduler.data_sources import DataSource


def run_ortools_simulation(
    *,
    timeout_seconds: int = 180,
    planifiables_only: bool = True,
    verbose: bool = False,
    priority_mode: str = "colis",
    data_source_name: str | None = None,
    data_source: DataSource | None = None,
    solver_version: str | None = None,
) -> Dict[str, Any]:
    """
    Lance le solveur OR-Tools et retourne un dict contenant
    planning_df, bilan_df, stats, et tables intermédiaires.
    """
    return solve_planning_ortools_simulation(
        planifiables_only=planifiables_only,
        timeout_seconds=timeout_seconds,
        verbose=verbose,
        priority_mode=priority_mode,
        data_source=data_source,
        data_source_name=data_source_name,
        solver_version=solver_version,
    )


def run_ortools_simulation_dual(
    *,
    timeout_seconds: int = 180,
    planifiables_only: bool = True,
    verbose: bool = False,
    data_source_name: str | None = None,
    data_source: DataSource | None = None,
    solver_version: str | None = None,
) -> Dict[str, Any]:
    """
    Lance deux simulations : priorité colis (par défaut) et priorité bénévoles.
    Retourne un dict {modes: {colis: res, benevoles: res}, selected: 'colis'}.
    """
    modes = {}
    modes["colis"] = run_ortools_simulation(
        timeout_seconds=timeout_seconds,
        planifiables_only=planifiables_only,
        verbose=verbose,
        priority_mode="colis",
        data_source=data_source,
        data_source_name=data_source_name,
        solver_version=solver_version,
    )
    modes["benevoles"] = run_ortools_simulation(
        timeout_seconds=timeout_seconds,
        planifiables_only=planifiables_only,
        verbose=verbose,
        priority_mode="benevoles",
        data_source=data_source,
        data_source_name=data_source_name,
        solver_version=solver_version,
    )
    return {"modes": modes, "selected": "colis"}
