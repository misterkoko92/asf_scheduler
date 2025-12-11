# -*- coding: utf-8 -*-
"""
Service dédié au lancement du solveur OR-Tools en mode simulation.
L'UI reste simple et appelle uniquement ces fonctions.
"""

from __future__ import annotations

from typing import Any, Dict

from scheduler.solver_ortools import solve_planning_ortools_simulation


def run_ortools_simulation(
    *,
    timeout_seconds: int = 180,
    planifiables_only: bool = True,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Lance le solveur OR-Tools et retourne un dict contenant
    planning_df, bilan_df, stats, et tables intermédiaires.
    """
    return solve_planning_ortools_simulation(
        planifiables_only=planifiables_only,
        timeout_seconds=timeout_seconds,
        verbose=verbose,
    )

