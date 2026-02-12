# -*- coding: utf-8 -*-
"""
Router V2/V3 pour le solveur OR-Tools.
Permet de basculer par variable d'environnement ou param explicite.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Tuple

import pandas as pd

from scheduler.solver_ortools import (
    solve_planning_ortools as solve_planning_ortools_v2,
    solve_planning_ortools_simulation as solve_planning_ortools_simulation_v2,
)
from scheduler.solver_ortools_v3 import (
    solve_planning_ortools as solve_planning_ortools_v3,
    solve_planning_ortools_simulation as solve_planning_ortools_simulation_v3,
)

SOLVER_VERSION_ENV = "ASF_SOLVER_VERSION"
DEFAULT_SOLVER_VERSION = "v3"
VALID_SOLVER_VERSIONS = {"v2", "v3"}


def _normalize_version(value: str | None) -> str:
    if not value:
        return DEFAULT_SOLVER_VERSION
    val = str(value).strip().lower()
    if val in {"2", "v2"}:
        return "v2"
    if val in {"3", "v3"}:
        return "v3"
    return DEFAULT_SOLVER_VERSION


def get_solver_version(explicit: str | None = None) -> str:
    if explicit:
        return _normalize_version(explicit)
    return _normalize_version(os.getenv(SOLVER_VERSION_ENV))


def solve_planning_ortools(
    *,
    planifiables_only: bool = True,
    timeout_seconds: int = 180,
    verbose: bool = False,
    priority_mode: str = "colis",
    data_source=None,
    data_source_name: str | None = None,
    solver_version: str | None = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    version = get_solver_version(solver_version)
    if version == "v3":
        return solve_planning_ortools_v3(
            planifiables_only=planifiables_only,
            timeout_seconds=timeout_seconds,
            verbose=verbose,
            priority_mode=priority_mode,
            data_source=data_source,
            data_source_name=data_source_name,
        )
    return solve_planning_ortools_v2(
        planifiables_only=planifiables_only,
        timeout_seconds=timeout_seconds,
        verbose=verbose,
        priority_mode=priority_mode,
        data_source=data_source,
        data_source_name=data_source_name,
    )


def solve_planning_ortools_simulation(
    *,
    planifiables_only: bool = True,
    timeout_seconds: int = 180,
    verbose: bool = False,
    dry_run: bool = False,
    priority_mode: str = "colis",
    data_source=None,
    data_source_name: str | None = None,
    solver_version: str | None = None,
) -> Dict[str, Any]:
    version = get_solver_version(solver_version)
    if version == "v3":
        return solve_planning_ortools_simulation_v3(
            planifiables_only=planifiables_only,
            timeout_seconds=timeout_seconds,
            verbose=verbose,
            dry_run=dry_run,
            priority_mode=priority_mode,
            data_source=data_source,
            data_source_name=data_source_name,
        )
    return solve_planning_ortools_simulation_v2(
        planifiables_only=planifiables_only,
        timeout_seconds=timeout_seconds,
        verbose=verbose,
        dry_run=dry_run,
        priority_mode=priority_mode,
        data_source=data_source,
        data_source_name=data_source_name,
    )
