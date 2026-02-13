# -*- coding: utf-8 -*-
"""
Solveur de simulation OR-Tools V3 pour ASF.

Objectif : introduire une capacité stricte par bénévole (Max_Colis_Vol)
en plus des contraintes existantes, sans impacter la V2.

Principes :
- S'appuie exclusivement sur les loaders existants (MAG CENTRAL, VOLS, BENEVOLES, Param*).
- Modélise BE → vols, bénévoles → vols et BE → bénévoles (assignation).
- Respecte la capacité par destination et la limite individuelle par bénévole.
- Génère un planning/bilan dans le même format que le moteur principal pour affichage.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

try:
    from ortools.sat.python import cp_model
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    cp_model = None

from scheduler.config import (
    MAX_BE_PER_FLIGHT,
    MAX_EQUIV_PER_VOLUNTEER,
)
from scheduler.data_sources import DataSource, resolve_data_source
from scheduler.planning_schema import normalize_planning_df
from scheduler.solver_ortools_common import (
    add_be_constraints as _core_add_be_constraints,
)
from scheduler.solver_ortools_common import (
    add_benev_constraints as _core_add_benev_constraints,
)
from scheduler.solver_ortools_common import (
    add_dest_constraints as _core_add_dest_constraints,
)
from scheduler.solver_ortools_common import (
    add_physical_flight_exclusivity_constraints as _core_add_physical_flight_exclusivity_constraints,
)
from scheduler.solver_ortools_common import (
    add_physical_flight_routing_priority_constraints as _core_add_physical_flight_routing_priority_constraints,
)
from scheduler.solver_ortools_common import (
    build_dest_info as _core_build_dest_info,
)
from scheduler.solver_ortools_common import (
    build_planning_bilan as _core_build_planning_bilan,
)
from scheduler.solver_ortools_common import (
    build_vols_compatibility_df as _core_build_vols_compatibility_df,
)
from scheduler.solver_ortools_common import (
    create_be_variables as _core_create_be_variables,
)
from scheduler.solver_ortools_common import (
    create_benev_variables as _core_create_benev_variables,
)
from scheduler.solver_ortools_common import (
    empty_result as _core_empty_result,
)
from scheduler.solver_ortools_common import (
    extract_solver_results as _core_extract_solver_results,
)
from scheduler.solver_ortools_common import (
    group_shipments as _core_group_shipments,
)
from scheduler.solver_ortools_common import (
    optimize_equilibrage as _core_optimize_equilibrage,
)
from scheduler.solver_ortools_common import (
    parse_benevoles as _core_parse_benevoles,
)
from scheduler.solver_ortools_common import (
    parse_time as _core_parse_time,
)
from scheduler.solver_ortools_common import (
    parse_vols as _core_parse_vols,
)
from scheduler.solver_ortools_common import (
    summarize_vols_compatibility as _core_summarize_vols_compatibility,
)
from scheduler.solver_ortools_common import (
    validate_inputs as _core_validate_inputs,
)
from utils.datetime_utils import format_time_value
from utils.logging_utils import get_logger

SOLVER_LOAD_ERRORS = (
    FileNotFoundError,
    OSError,
    PermissionError,
    RuntimeError,
    ValueError,
    TypeError,
    KeyError,
    ImportError,
    AttributeError,
)


# =====================================================================
# PUBLIC API
# =====================================================================

def solve_planning_ortools(
    *,
    planifiables_only: bool = True,
    timeout_seconds: int = 180,
    verbose: bool = False,
    priority_mode: str = "colis",
    data_source: DataSource | None = None,
    data_source_name: str | None = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """
    Exécute OR-Tools pour la génération principale du planning.
    Retourne (planning_df, bilan_df, stats).
    """
    result = solve_planning_ortools_simulation(
        planifiables_only=planifiables_only,
        timeout_seconds=timeout_seconds,
        verbose=verbose,
        priority_mode=priority_mode,
        data_source=data_source,
        data_source_name=data_source_name,
    )

    planning_df = result.get("planning_df", pd.DataFrame())
    bilan_df = result.get("bilan_df", pd.DataFrame())
    stats = result.get("statistiques", {}) or {}
    stats["priority_mode"] = result.get("priority_mode", priority_mode)
    stats["status"] = result.get("status", stats.get("status", "UNKNOWN"))
    return planning_df, bilan_df, stats


def solve_planning_ortools_simulation(
    *,
    planifiables_only: bool = True,
    timeout_seconds: int = 180,
    verbose: bool = False,
    dry_run: bool = False,
    priority_mode: str = "colis",  # "colis" ou "benevoles"
    data_source: DataSource | None = None,
    data_source_name: str | None = None,
) -> Dict[str, Any]:
    """
    Exécute le solveur OR-Tools et retourne un planning/bilan simulés.
    Pensé pour l'onglet Simulation uniquement.
    """

    if cp_model is None:
        return _empty_result("ORTOOLS_MISSING")

    # Logger (console + fichier)
    logger = get_logger("ortools_sim", console=verbose)
    def _log(msg: str):
        logger.info(msg)

    # -----------------------------------------------------------------
    # 1) Chargement des données
    # -----------------------------------------------------------------
    try:
        source = data_source or resolve_data_source(data_source_name)
        ds_name = getattr(source, "name", type(source).__name__)

        df_param_dest = source.load_param_dest()
        df_param_be = source.load_param_be()
        df_param_benev = source.load_param_benev()

        df_be = source.load_shipments_df(
            df_param_be,
            planifiables_only=planifiables_only,
        )
        if df_be.empty:
            return _empty_result("AUCUN_BE")

        df_vols_raw = source.load_vols_df(df_param_dest)
        if df_vols_raw.empty:
            return _empty_result("AUCUN_VOL")

        df_benev_raw = source.load_benevoles_df(df_param_benev)
        if df_benev_raw.empty:
            return _empty_result("AUCUN_BENEVOLE")

        _log(
            f"[ORTOOLS] Data source={ds_name} | "
            f"BE={len(df_be)} vols={len(df_vols_raw)} dispo={len(df_benev_raw)}"
        )
    except SOLVER_LOAD_ERRORS as exc:  # pragma: no cover - safety
        _log(f"[ORTOOLS] Erreur chargement : {exc}")
        return _empty_result("ERREUR_CHARGEMENT")

    # Validation précoce
    errs = _validate_inputs(df_be, df_vols_raw, df_benev_raw)
    if errs:
        for e in errs:
            _log(f"[ORTOOLS] Validation input : {e}")
        return _empty_result("ERREUR_DONNEES")

    # -----------------------------------------------------------------
    # 2) Prétraitements / parsing
    # -----------------------------------------------------------------
    dest_info = _build_dest_info(df_param_dest)
    be_groups = _group_shipments(df_be)
    df_vols = _parse_vols(df_vols_raw, dest_info)
    df_benev = _parse_benevoles(df_benev_raw, df_param_benev)

    if df_vols.empty:
        _log("[ORTOOLS] Aucun vol valide après parsing.")
        return _empty_result("AUCUN_VOL_VALIDE")
    if df_benev.empty:
        _log("[ORTOOLS] Aucune disponibilité bénévole valide après parsing.")
        return _empty_result("AUCUN_BENEVOLE_VALIDE")

    if dry_run:
        _log(f"[ORTOOLS][DRY RUN] BE={len(be_groups)}, vols={len(df_vols)}, benevoles={len(df_benev)}")
        return {
            "statistiques": {
                "status": "DRY_RUN",
                "nb_be": len(be_groups),
                "nb_vols": len(df_vols),
                "nb_benevoles": len(df_benev),
            },
            "status": "DRY_RUN",
            "planning_df": pd.DataFrame(),
            "bilan_df": pd.DataFrame(),
        }

    # Dictionnaires utilitaires
    priority_map = dict(zip(df_param_be["Type"], df_param_be["Priorite_Type"]))

    # -----------------------------------------------------------------
    # 3) Modèle CP-SAT
    # -----------------------------------------------------------------
    model = cp_model.CpModel()

    x = _create_be_variables(model, be_groups, df_vols, dest_info)
    if not x:
        return _empty_result("AUCUNE_AFFECTATION_POSSIBLE")

    y, benev_vols_compat, vols_with_benev, benev_ids = _create_benev_variables(
        model, df_benev, df_vols
    )

    vols_diag_pre = _build_vols_compatibility_df(df_vols, x, y)
    vols_diag_summary_pre = _summarize_vols_compatibility(vols_diag_pre)
    if vols_diag_summary_pre["nb_vols_sans_benevole_compatible"] > 0:
        sample = vols_diag_pre[vols_diag_pre["Benev_Compat_Count"] == 0].head(5)
        _log(
            "[ORTOOLS] Vols sans bénévole compatible: "
            f"{vols_diag_summary_pre['nb_vols_sans_benevole_compatible']}/{vols_diag_summary_pre['nb_vols_total']} "
            f"(exemples: {sample[['Numero_Vol', 'Date_Vol', 'Heure_Vol', 'Dest_IATA']].to_dict(orient='records')})"
        )
    if vols_diag_summary_pre["nb_vols_sans_be_compatible"] > 0:
        sample = vols_diag_pre[vols_diag_pre["BE_Compat_Count"] == 0].head(5)
        _log(
            "[ORTOOLS] Vols sans BE compatible: "
            f"{vols_diag_summary_pre['nb_vols_sans_be_compatible']}/{vols_diag_summary_pre['nb_vols_total']} "
            f"(exemples: {sample[['Numero_Vol', 'Date_Vol', 'Heure_Vol', 'Dest_IATA']].to_dict(orient='records')})"
        )

    benev_by_vol: Dict[int, List[int]] = defaultdict(list)
    for (benev_id, v_idx) in y.keys():
        benev_by_vol[v_idx].append(benev_id)

    z = _create_assignment_variables(model, x, benev_by_vol)
    max_colis_by_benev = _build_benev_max_colis_map(df_param_benev)

    # Disponibilités totales (en minutes) par bénévole pour pondérer les choix
    benev_avail_minutes: Dict[int, int] = defaultdict(int)
    for _, row in df_benev.iterrows():
        bid = int(row["ID"])
        debut = row.get("heure_debut")
        fin = row.get("heure_fin")
        if isinstance(debut, time) and isinstance(fin, time):
            delta = (datetime.combine(datetime.today(), fin) - datetime.combine(datetime.today(), debut)).total_seconds() / 60
            if delta > 0:
                benev_avail_minutes[bid] += int(delta)

    # Diagnostic : BE sans aucun vol compatible
    be_without_option = []
    for be_idx in be_groups.index:
        if not any(k[0] == be_idx for k in x.keys()):
            be_num = be_groups.loc[be_idx, "BE_Numero"]
            be_without_option.append(be_num)
    if be_without_option:
        _log(f"[ORTOOLS] BE sans vol compatible : {len(be_without_option)} → {be_without_option}")

    # Diagnostic : bénévoles sans vol compatible
    benev_without_option = [bid for bid in benev_ids if len(benev_vols_compat.get(bid, [])) == 0]
    if benev_without_option:
        _log(f"[ORTOOLS] Bénévoles sans vol compatible : {len(benev_without_option)} → {benev_without_option}")

    u, charge, nb_be, nb_benev = {}, {}, {}, {}
    for v_idx in df_vols.index:
        u[v_idx] = model.NewBoolVar(f"u_v{v_idx}")
        charge[v_idx] = model.NewIntVar(0, 10_000, f"charge_v{v_idx}")
        nb_be[v_idx] = model.NewIntVar(0, MAX_BE_PER_FLIGHT, f"nb_be_v{v_idx}")
        nb_benev[v_idx] = model.NewIntVar(0, 100, f"nb_benev_v{v_idx}")

    _add_be_constraints(
        model,
        be_groups,
        df_vols,
        x,
        u,
        charge,
        nb_be,
        dest_info,
        vols_with_benev,
    )
    _add_physical_flight_routing_priority_constraints(model, df_vols, x, u, vols_with_benev)
    _add_benev_constraints(
        model,
        y,
        u,
        charge,
        nb_benev,
        df_vols,
        df_param_benev,
        benev_vols_compat,
    )
    _add_assignment_constraints(
        model,
        be_groups,
        x,
        y,
        z,
        benev_by_vol,
        max_colis_by_benev,
    )
    _add_dest_constraints(model, df_vols, dest_info, u)
    _add_physical_flight_exclusivity_constraints(model, df_vols, u)

    # -----------------------------------------------------------------
    # 4) Optimisation hiérarchique
    # -----------------------------------------------------------------
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = timeout_seconds
    solver.parameters.num_search_workers = 8

    # Objectifs hiérarchiques — selon mode de priorité
    # Préparation poids et bénévoles utilisés
    weights = []
    for (be_idx, v_idx) in x:
        be = be_groups.loc[be_idx]
        prio = priority_map.get(be["type"], be["priorite_moyenne"])
        poids_pondere = be["poids_total"] * (10 - prio if prio is not None else 10)
        weights.append(poids_pondere)

    benev_used = {}
    benev_missions = {}
    for benev_id in benev_ids:
        bvar = model.NewBoolVar(f"b_used_{benev_id}")
        benev_used[benev_id] = bvar
        vols = benev_vols_compat.get(int(benev_id), [])
        miss_var = model.NewIntVar(0, 50, f"missions_{benev_id}")
        benev_missions[benev_id] = miss_var
        if vols:
            model.Add(miss_var == sum(y[(benev_id, v)] for v in vols if (benev_id, v) in y))
            model.Add(miss_var >= 1).OnlyEnforceIf(bvar)
            model.Add(miss_var == 0).OnlyEnforceIf(bvar.Not())
        else:
            model.Add(miss_var == 0)
            model.Add(bvar == 0)

    def _phase_max_weight():
        model.Maximize(sum(w * var for w, var in zip(weights, x.values())))
        _log("[ORTOOLS] Phase — maximisation poids")
        st = solver.Solve(model)
        if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return None
        max_w = solver.ObjectiveValue()
        model.Add(sum(w * var for w, var in zip(weights, x.values())) >= int(max_w))
        _log(f"[ORTOOLS] Poids max atteint = {max_w:.2f}")
        return max_w

    def _phase_min_vols():
        _log("[ORTOOLS] Phase — minimisation nb vols")
        model.Minimize(sum(u.values()))
        st = solver.Solve(model)
        if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return None
        min_f = int(round(solver.ObjectiveValue()))
        model.Add(sum(u.values()) <= min_f)
        _log(f"[ORTOOLS] Nb vols minimum = {min_f}")
        return min_f

    def _phase_max_benev():
        _log("[ORTOOLS] Phase — maximisation bénévoles utilisés")
        model.Maximize(sum(benev_used.values()))
        st = solver.Solve(model)
        if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return None
        max_b = int(round(solver.ObjectiveValue()))
        model.Add(sum(benev_used.values()) >= max_b)
        _log(f"[ORTOOLS] Bénévoles max utilisés = {max_b}")
        return max_b

    def _phase_min_benev():
        _log("[ORTOOLS] Phase — minimisation bénévoles affectés")
        model.Minimize(sum(nb_benev.values()))
        st = solver.Solve(model)
        if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return None
        min_b = int(round(solver.ObjectiveValue()))
        model.Add(sum(nb_benev.values()) <= min_b)
        _log(f"[ORTOOLS] Bénévoles min affectés = {min_b}")
        return min_b

    def _phase_min_excess_missions():
        _log("[ORTOOLS] Phase — minimisation surplus de missions (>1 par bénévole)")
        excess_vars = []
        for bid, miss in benev_missions.items():
            exc = model.NewIntVar(0, 50, f"excess_{bid}")
            model.Add(exc >= miss - 1)
            model.Add(exc >= 0)
            excess_vars.append(exc)
        model.Minimize(sum(excess_vars))
        st = solver.Solve(model)
        if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return None
        min_exc = int(round(solver.ObjectiveValue()))
        model.Add(sum(excess_vars) <= min_exc)
        _log(f"[ORTOOLS] Surplus missions total = {min_exc}")
        return min_exc

    def _phase_min_weighted_availability():
        _log("[ORTOOLS] Phase — minimisation pondérée par disponibilités (privilégier peu disponibles)")
        terms = []
        for bid, miss in benev_missions.items():
            avail = benev_avail_minutes.get(int(bid), 0)
            weight = max(1, avail)  # éviter 0
            terms.append(miss * weight)
        model.Minimize(sum(terms))
        st = solver.Solve(model)
        if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return None
        _log("[ORTOOLS] Pondération disponibilités appliquée")
        return solver.ObjectiveValue()

    mode = priority_mode.lower()
    if mode not in ("colis", "benevoles"):
        mode = "colis"

    if mode == "colis":
        # 1) Poids, 2) Vols min, 3) Bénévoles min, 4) Équilibrage + résolution finale
        if _phase_max_weight() is None:
            return _empty_result("INFAISABLE")
        if _phase_min_vols() is None:
            return _empty_result("INFAISABLE")
        if _phase_min_benev() is None:
            return _empty_result("INFAISABLE")
        _phase_min_excess_missions()
        _phase_min_weighted_availability()
        _optimize_equilibrage(model, solver, y, df_param_benev, verbose)
        _log("[ORTOOLS] Phase finale — contraintes poids/vols/bénévoles équilibrées")
        model.Minimize(sum(u.values()))
        status = solver.Solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return _empty_result("INFAISABLE")
    else:
        # Mode priorité bénévoles : 1) poids, 2) vols min (évite split), 3) bénév max, 4) surplus missions, 5) pondération dispos, 6) équilibrage
        if _phase_max_weight() is None:
            return _empty_result("INFAISABLE")
        if _phase_min_vols() is None:
            return _empty_result("INFAISABLE")
        if _phase_max_benev() is None:
            return _empty_result("INFAISABLE")
        _phase_min_excess_missions()
        _phase_min_weighted_availability()
        _optimize_equilibrage(model, solver, y, df_param_benev, verbose)
        _log("[ORTOOLS] Phase finale — contraintes bénévoles/poids/vols équilibrées")
        model.Minimize(sum(u.values()))
        status = solver.Solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return _empty_result("INFAISABLE")

    # -----------------------------------------------------------------
    # 5) Extraction des résultats + format planning/bilan
    # -----------------------------------------------------------------
    extracted = _extract_results(
        solver=solver,
        x=x,
        y=y,
        z=z,
        u=u,
        charge=charge,
        nb_be=nb_be,
        be_groups=be_groups,
        df_be_original=df_be,
        df_vols=df_vols,
        df_benev=df_benev,
        df_param_benev=df_param_benev,
        status=status,
        verbose=verbose,
        priority_mode=mode,
    )

    planning_df, bilan_df = _build_planning_bilan_v3(
        extracted["affectations_be"],
        extracted.get("assignations_benev", []),
        be_groups,
        df_vols,
        df_param_benev,
    )
    planning_df = normalize_planning_df(planning_df)

    # Logs diagnostics : BE non planifiés et bénévoles non utilisés
    be_non_planifies_df = extracted.get("be_non_planifies", pd.DataFrame())
    if be_non_planifies_df is not None and not be_non_planifies_df.empty:
        _log(f"[ORTOOLS] BE non planifiés : {len(be_non_planifies_df)} → {be_non_planifies_df['BE_Numero'].astype(str).tolist()}")

    benev_used_final = set()
    for (bid, v_idx), var in y.items():
        if solver.Value(var) == 1:
            benev_used_final.add(int(bid))
    benev_not_used = [b for b in benev_ids if b not in benev_used_final]
    if benev_not_used:
        _log(f"[ORTOOLS] Bénévoles disponibles mais non utilisés : {len(benev_not_used)} → {benev_not_used}")

    return {
        **extracted,
        "planning_df": planning_df,
        "bilan_df": bilan_df,
        "dest_stats": extracted.get("dest_stats", pd.DataFrame()),
        "priority_mode": mode,
    }


# =====================================================================
# HELPERS – données
# =====================================================================

def _empty_result(status: str) -> Dict[str, Any]:
    return _core_empty_result(status, include_assignations=True)


def _validate_inputs(df_be: pd.DataFrame, df_vols: pd.DataFrame, df_benev: pd.DataFrame) -> List[str]:
    return _core_validate_inputs(df_be, df_vols, df_benev)


def _build_dest_info(df_param_dest: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    return _core_build_dest_info(df_param_dest)


def _build_benev_max_colis_map(df_param_benev: pd.DataFrame) -> Dict[int, int]:
    max_map: Dict[int, int] = {}
    if df_param_benev is None or df_param_benev.empty:
        return max_map
    if "Max_Colis_Vol" not in df_param_benev.columns:
        return max_map
    for _, row in df_param_benev.iterrows():
        benev_id = row.get("ID")
        if pd.isna(benev_id):
            continue
        try:
            bid = int(benev_id)
        except (TypeError, ValueError):
            continue
        raw_val = row.get("Max_Colis_Vol", None)
        try:
            val = int(raw_val)
        except (TypeError, ValueError):
            val = MAX_EQUIV_PER_VOLUNTEER
        if val <= 0:
            val = MAX_EQUIV_PER_VOLUNTEER
        max_map[bid] = val
    return max_map


def _group_shipments(df_be: pd.DataFrame) -> pd.DataFrame:
    return _core_group_shipments(df_be)


def _build_vols_compatibility_df(
    df_vols: pd.DataFrame,
    x: Dict[Tuple[int, int], cp_model.IntVar],
    y: Dict[Tuple[int, int], cp_model.IntVar],
    *,
    u: Dict[int, cp_model.IntVar] | None = None,
    solver: cp_model.CpSolver | None = None,
) -> pd.DataFrame:
    return _core_build_vols_compatibility_df(df_vols, x, y, u=u, solver=solver)


def _summarize_vols_compatibility(df_diag: pd.DataFrame) -> Dict[str, int]:
    return _core_summarize_vols_compatibility(df_diag)


def _parse_vols(df_vols_raw: pd.DataFrame, dest_info: Dict[str, Dict[str, Any]]) -> pd.DataFrame:
    return _core_parse_vols(df_vols_raw, dest_info)


def _parse_benevoles(df_benev_raw: pd.DataFrame, df_param: pd.DataFrame) -> pd.DataFrame:
    return _core_parse_benevoles(
        df_benev_raw,
        df_param,
        extra_param_columns=("Max_Colis_Vol",),
    )


def _parse_time(val: Any) -> Optional[time]:
    return _core_parse_time(val)


# =====================================================================
# VARIABLES / CONTRAINTES
# =====================================================================

def _create_be_variables(
    model: cp_model.CpModel,
    be_groups: pd.DataFrame,
    df_vols: pd.DataFrame,
    dest_info: Dict[str, Dict[str, Any]],
) -> Dict[Tuple[int, int], cp_model.IntVar]:
    return _core_create_be_variables(model, be_groups, df_vols, dest_info)


def _create_benev_variables(
    model: cp_model.CpModel, df_benev: pd.DataFrame, df_vols: pd.DataFrame
) -> Tuple[Dict[Tuple[int, int], cp_model.IntVar], Dict[int, List[int]], List[int], List[int]]:
    return _core_create_benev_variables(model, df_benev, df_vols)


def _create_assignment_variables(
    model: cp_model.CpModel,
    x: Dict[Tuple[int, int], cp_model.IntVar],
    benev_by_vol: Dict[int, List[int]],
) -> Dict[Tuple[int, int, int], cp_model.IntVar]:
    z: Dict[Tuple[int, int, int], cp_model.IntVar] = {}
    for (be_idx, v_idx) in x.keys():
        benevs = benev_by_vol.get(v_idx, [])
        for benev_id in benevs:
            z[(be_idx, benev_id, v_idx)] = model.NewBoolVar(f"z_{be_idx}_{benev_id}_{v_idx}")
    return z


def _add_assignment_constraints(
    model: cp_model.CpModel,
    be_groups: pd.DataFrame,
    x: Dict[Tuple[int, int], cp_model.IntVar],
    y: Dict[Tuple[int, int], cp_model.IntVar],
    z: Dict[Tuple[int, int, int], cp_model.IntVar],
    benev_by_vol: Dict[int, List[int]],
    max_colis_by_benev: Dict[int, int],
) -> None:
    # 1) Chaque BE affecté à un vol est assigné à exactement 1 bénévole
    for (be_idx, v_idx), x_var in x.items():
        benevs = benev_by_vol.get(v_idx, [])
        if not benevs:
            model.Add(x_var == 0)
            continue
        z_vars = [z[(be_idx, b, v_idx)] for b in benevs if (be_idx, b, v_idx) in z]
        if z_vars:
            model.Add(sum(z_vars) == x_var)
            for b in benevs:
                if (be_idx, b, v_idx) in z:
                    model.Add(z[(be_idx, b, v_idx)] <= y[(b, v_idx)])
        else:
            model.Add(x_var == 0)

    # 2) Capacité stricte par bénévole et par vol
    be_weights = {be_idx: int(be["poids_total"]) for be_idx, be in be_groups.iterrows()}
    z_by_benev_vol: Dict[Tuple[int, int], List[Tuple[int, cp_model.IntVar]]] = defaultdict(list)
    for (be_idx, benev_id, v_idx), var in z.items():
        z_by_benev_vol[(benev_id, v_idx)].append((be_idx, var))

    for (benev_id, v_idx), items in z_by_benev_vol.items():
        max_cap = max_colis_by_benev.get(benev_id, MAX_EQUIV_PER_VOLUNTEER)
        model.Add(
            sum(be_weights[be_idx] * var for be_idx, var in items) <= max_cap * y[(benev_id, v_idx)]
        )


def _add_be_constraints(
    model: cp_model.CpModel,
    be_groups: pd.DataFrame,
    df_vols: pd.DataFrame,
    x: Dict[Tuple[int, int], cp_model.IntVar],
    u: Dict[int, cp_model.IntVar],
    charge: Dict[int, cp_model.IntVar],
    nb_be: Dict[int, cp_model.IntVar],
    dest_info: Dict[str, Dict[str, Any]],
    vols_with_benev: List[int],
) -> None:
    _core_add_be_constraints(
        model,
        be_groups,
        df_vols,
        x,
        u,
        charge,
        nb_be,
        dest_info,
        vols_with_benev,
    )


def _add_benev_constraints(
    model: cp_model.CpModel,
    y: Dict[Tuple[int, int], cp_model.IntVar],
    u: Dict[int, cp_model.IntVar],
    charge: Dict[int, cp_model.IntVar],
    nb_benev: Dict[int, cp_model.IntVar],
    df_vols: pd.DataFrame,
    df_param: pd.DataFrame,
    benev_vols_compat: Dict[int, List[int]],
) -> None:
    _core_add_benev_constraints(
        model,
        y,
        u,
        charge,
        nb_benev,
        df_vols,
        df_param,
        benev_vols_compat,
        enforce_equiv_capacity=False,
    )


def _add_dest_constraints(
    model: cp_model.CpModel,
    df_vols: pd.DataFrame,
    dest_info: Dict[str, Dict[str, Any]],
    u: Dict[int, cp_model.IntVar],
) -> None:
    _core_add_dest_constraints(model, df_vols, dest_info, u)


def _add_physical_flight_exclusivity_constraints(
    model: cp_model.CpModel,
    df_vols: pd.DataFrame,
    u: Dict[int, cp_model.IntVar],
) -> None:
    _core_add_physical_flight_exclusivity_constraints(model, df_vols, u)


def _add_physical_flight_routing_priority_constraints(
    model: cp_model.CpModel,
    df_vols: pd.DataFrame,
    x: Dict[Tuple[int, int], cp_model.IntVar],
    u: Dict[int, cp_model.IntVar],
    vols_with_benev: List[int],
) -> None:
    _core_add_physical_flight_routing_priority_constraints(model, df_vols, x, u, vols_with_benev)


def _optimize_equilibrage(
    model: cp_model.CpModel,
    solver: cp_model.CpSolver,
    y: Dict[Tuple[int, int], cp_model.IntVar],
    df_param: pd.DataFrame,
    verbose: bool,
) -> None:
    _core_optimize_equilibrage(model, solver, y, df_param, verbose)


# =====================================================================
# EXTRACTION
# =====================================================================

def _extract_results(
    *,
    solver: cp_model.CpSolver,
    x: Dict[Tuple[int, int], cp_model.IntVar],
    y: Dict[Tuple[int, int], cp_model.IntVar],
    z: Dict[Tuple[int, int, int], cp_model.IntVar],
    u: Dict[int, cp_model.IntVar],
    charge: Dict[int, cp_model.IntVar],
    nb_be: Dict[int, cp_model.IntVar],
    be_groups: pd.DataFrame,
    df_be_original: pd.DataFrame,
    df_vols: pd.DataFrame,
    df_benev: pd.DataFrame,
    df_param_benev: pd.DataFrame,
    status: int,
    verbose: bool = False,
    priority_mode: str = "colis",
) -> Dict[str, Any]:
    return _core_extract_solver_results(
        solver=solver,
        x=x,
        y=y,
        u=u,
        charge=charge,
        nb_be=nb_be,
        be_groups=be_groups,
        df_be_original=df_be_original,
        df_vols=df_vols,
        df_param_benev=df_param_benev,
        status=status,
        verbose=verbose,
        priority_mode=priority_mode,
        include_assignations=True,
        z=z,
    )


def _build_planning_bilan(
    df_affectations: pd.DataFrame,
    df_planning_benev: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    return _core_build_planning_bilan(df_affectations, df_planning_benev)


def _build_planning_bilan_v3(
    df_affectations: pd.DataFrame,
    assignations_benev: List[Dict[str, Any]],
    be_groups: pd.DataFrame,
    df_vols: pd.DataFrame,
    df_param_benev: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Reconstruit le planning à partir des assignations BE → bénévole (z).
    """
    if not assignations_benev:
        return pd.DataFrame(), pd.DataFrame()

    benev_info_by_id: Dict[int, Dict[str, Any]] = {}
    if df_param_benev is not None and not df_param_benev.empty:
        for _, row in df_param_benev.iterrows():
            bid = row.get("ID")
            if pd.isna(bid):
                continue
            try:
                benev_info_by_id[int(bid)] = row.to_dict()
            except (TypeError, ValueError):
                continue

    planning_rows: List[Dict[str, Any]] = []
    for assign in assignations_benev:
        be_idx = assign["BE_Index"]
        benev_id = assign["Benevole_ID"]
        v_idx = assign["Vol_Index"]
        be = be_groups.loc[be_idx]
        vol = df_vols.loc[v_idx]

        benev_info = benev_info_by_id.get(int(benev_id), {})
        nom = benev_info.get("Benevole", "")
        if nom is None or (isinstance(nom, float) and pd.isna(nom)) or str(nom).strip() == "":
            nom = f"ID_{benev_id}"
        phone = benev_info.get("Telephone", "")
        if phone is None or (isinstance(phone, float) and pd.isna(phone)):
            phone = ""

        planning_rows.append(
            {
                "Date_Vol": vol.get("Date_Vol") or vol["datetime"].date(),
                "Heure_Vol": vol.get("Heure_Vol") or format_time_value(vol["datetime"].time(), fmt="%Hh%M", default=""),
                "Numero_Vol": vol.get("Numero_Vol", ""),
                "Destination": vol.get("Destination", vol.get("dest_iata", "")),
                "BE_Numero": be["BE_Numero"],
                "BE_Nb_Colis": int(be["nb_colis"]),
                "BE_Nb_Equiv": int(be["poids_total"]),
                "BE_Expediteur": be.get("BE_Expediteur", ""),
                "BE_Destinataire": be.get("BE_Destinataire", ""),
                "BE_Type": be.get("type", ""),
                "Routing": vol.get("Routing", ""),
                "Benevole": nom,
                "ID": benev_id,
                "Telephone": phone,
            }
        )

    planning_df = pd.DataFrame(planning_rows)
    if not planning_df.empty:
        planning_df = planning_df.sort_values(
            ["Date_Vol", "Heure_Vol", "Numero_Vol", "Destination", "BE_Numero"]
        )

    bilan_rows = []
    if not df_affectations.empty:
        for _, row in df_affectations.iterrows():
            bilan_rows.append(
                {
                    "Date_Vol": row["Vol_Date"],
                    "Numero_Vol": row.get("Vol_Numero", ""),
                    "Destination": row.get("Vol_Destination", ""),
                    "BE_Numero": row["BE_Numero"],
                    "Nb_Colis": row.get("BE_Nb_Colis", 0),
                    "Nb_Equiv": row.get("BE_Poids_Equiv", 0),
                    "Partant": "OUI",
                    "Raison": "OK",
                }
            )

    bilan_df = pd.DataFrame(bilan_rows)
    return planning_df, bilan_df
