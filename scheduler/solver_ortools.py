# -*- coding: utf-8 -*-
"""
Solveur de simulation OR-Tools pour ASF.

Objectif : proposer une alternative "boîte noire" au moteur existant pour
tester des plans, sans impacter la génération de planning principale.

Principes :
- S'appuie exclusivement sur les loaders existants (MAG CENTRAL, VOLS, BENEVOLES, Param*).
- Modélise BE → vols et bénévoles → vols avec contraintes de capacité, fréquence, quotas, temps min entre vols.
- Génère un planning/bilan dans le même format que le moteur principal pour affichage.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, time
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
try:
    from ortools.sat.python import cp_model
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    cp_model = None

from scheduler.data_sources import DataSource, resolve_data_source
from scheduler.config import (
    DUREE_MISSION_HEURES,
    MAX_BE_PER_FLIGHT,
    MAX_BENEV_PER_VOL,
    MAX_CAPACITE_PAR_VOL,
    MAX_EQUIV_PER_VOLUNTEER,
    MIN_HOURS_BETWEEN_FLIGHTS,
)
from utils.logging_utils import get_logger
from scheduler.planning_schema import normalize_planning_df
from utils.datetime_utils import (
    coerce_datetime,
    parse_date_value_as_date,
    parse_time_value_as_time,
    format_time_value,
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
        if verbose:
            print(msg)
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
    except Exception as exc:  # pragma: no cover - safety
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
    _add_dest_constraints(model, df_vols, dest_info, u)

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

    planning_df, bilan_df = _build_planning_bilan(
        extracted["affectations_be"],
        extracted["planning_benevoles"],
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
    return {
        "affectations_be": pd.DataFrame(),
        "planning_benevoles": pd.DataFrame(),
        "vols_utilises": pd.DataFrame(),
        "statistiques": {"status": status},
        "status": status,
        "be_non_planifies": pd.DataFrame(),
        "planning_df": pd.DataFrame(),
        "bilan_df": pd.DataFrame(),
        "dest_stats": pd.DataFrame(),
    }


def _validate_inputs(df_be: pd.DataFrame, df_vols: pd.DataFrame, df_benev: pd.DataFrame) -> List[str]:
    """Validation minimale des colonnes requises avant modélisation."""
    errors: List[str] = []
    if df_be is None or df_be.empty:
        errors.append("Aucun BE planifiable.")
    if df_vols is None or df_vols.empty:
        errors.append("Aucun vol.")
    else:
        required_vol_cols = ["Date_Vol", "Heure_Vol", "IATA"]
        missing = [c for c in required_vol_cols if c not in df_vols.columns]
        if missing:
            errors.append(f"Vols : colonnes manquantes {missing}")
    if df_benev is None or df_benev.empty:
        errors.append("Aucune disponibilité bénévole.")
    else:
        missing_b = [c for c in ["Date", "Heure_Arrivee_time", "Heure_Depart_time"] if c not in df_benev.columns]
        if missing_b:
            errors.append(f"Bénévoles : colonnes manquantes {missing_b}")
    return errors


def _build_dest_info(df_param_dest: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    jours_cols = [
        "Freq_Lundi",
        "Freq_Mardi",
        "Freq_Mercredi",
        "Freq_Jeudi",
        "Freq_Vendredi",
        "Freq_Samedi",
        "Freq_Dimanche",
    ]
    dest_info: Dict[str, Dict[str, Any]] = {}

    for _, row in df_param_dest.iterrows():
        dest_iata = str(row.get("Dest_IATA", "")).strip().upper()
        if not dest_iata:
            continue

        jours_autorises = []
        for idx, col in enumerate(jours_cols):
            val = row.get(col, 0)
            if val == 1 or (isinstance(val, str) and val.strip().lower() == "ok"):
                jours_autorises.append(idx)

        try:
            max_colis = int(row.get("Max_Colis_Par_Vol", MAX_CAPACITE_PAR_VOL))
        except Exception:
            max_colis = MAX_CAPACITE_PAR_VOL
        if max_colis <= 0:
            max_colis = MAX_CAPACITE_PAR_VOL

        try:
            max_vols = int(row.get("Freq_Semaine", 999))
        except Exception:
            max_vols = 999
        if max_vols <= 0:
            max_vols = 999  # 0 ou vide = pas de limite explicite

        dest_info[dest_iata] = {
            "max_colis": max_colis,
            "max_vols_semaine": max_vols,
            "jours_autorises": jours_autorises,
        }
    return dest_info


def _group_shipments(df_be: pd.DataFrame) -> pd.DataFrame:
    be_groups = (
        df_be.groupby("BE_Numero")
        .agg(
            {
                "Destination": "first",
                "BE_Nb_Colis": "sum",
                "BE_Expediteur": "first",
                "BE_Destinataire": "first",
                "Priorite": "first",
                "Equiv_Colis": "first",
                "BE_Type": "first",
            }
        )
        .reset_index()
    )
    be_groups.rename(
        columns={
            "Priorite": "priorite_moyenne",
            "Equiv_Colis": "poids_total",
            "BE_Nb_Colis": "nb_colis",
            "BE_Type": "type",
        },
        inplace=True,
    )
    return be_groups


def _parse_vols(df_vols_raw: pd.DataFrame, dest_info: Dict[str, Dict[str, Any]]) -> pd.DataFrame:
    def _parse_datetime(row: pd.Series) -> Optional[datetime]:
        date_val = row.get("Date_Vol_dt") or coerce_datetime(
            row.get("Date_Vol"), errors="coerce", dayfirst=True
        )
        if pd.isna(date_val):
            return None
        time_val = row.get("Heure_Vol_time") or _parse_time(row.get("Heure_Vol"))
        if time_val is None:
            time_val = time(0, 0)
        try:
            date_only = parse_date_value_as_date(date_val)
            if date_only is None:
                return None
            return datetime.combine(date_only, time_val)
        except Exception:
            return None

    df = df_vols_raw.copy()
    df["datetime"] = df.apply(_parse_datetime, axis=1)
    df = df[df["datetime"].notna()].copy()
    if "IATA" in df.columns:
        iata_series = df["IATA"]
    elif "Destination" in df.columns:
        iata_series = df["Destination"]
    else:
        iata_series = pd.Series([""] * len(df), index=df.index)
    df["dest_iata"] = iata_series.astype(str).str.strip().str.upper()
    df = df[df["dest_iata"] != ""].reset_index(drop=True)

    # Limiter aux jours autorisés si ParamDest fournit des règles
    mask_allowed = []
    for _, row in df.iterrows():
        dest = row["dest_iata"]
        if dest not in dest_info:
            mask_allowed.append(True)
            continue
        jours_autorises = dest_info[dest]["jours_autorises"] or list(range(7))
        mask_allowed.append(row["datetime"].weekday() in jours_autorises)
    df = df[pd.Series(mask_allowed, index=df.index)]
    df = df.reset_index(drop=True)
    return df


def _parse_benevoles(df_benev_raw: pd.DataFrame, df_param: pd.DataFrame) -> pd.DataFrame:
    df = df_benev_raw.copy()

    date_col = "Date_dt" if "Date_dt" in df.columns else "Date"
    df["date_obj"] = coerce_datetime(df[date_col], errors="coerce", dayfirst=True)
    df = df[df["date_obj"].notna()].copy()

    if "Heure_Arrivee_time" in df.columns:
        df["heure_debut"] = df["Heure_Arrivee_time"]
        df["heure_fin"] = df["Heure_Depart_time"]
    else:
        df["heure_debut"] = df["Heure_Arrivee"].apply(_parse_time)
        df["heure_fin"] = df["Heure_Depart"].apply(_parse_time)
    df = df[(df["heure_debut"].notna()) & (df["heure_fin"].notna())].copy()

    if "ID" in df.columns:
        df["ID"] = pd.to_numeric(df["ID"], errors="coerce").astype("Int64")

    if "Max_Exp_Jour" not in df.columns:
        df = df.merge(
            df_param[
                [
                    "ID",
                    "Max_Jours_Semaine",
                    "Max_Exp_Semaine",
                    "Max_Exp_Jour",
                    "Attente_Max_Heures",
                    "Benevole",
                    "Nom",
                    "Prenom",
                    "Prenom_Court",
                    "Telephone",
                ]
            ],
            on="ID",
            how="left",
        )

    df = df[df["ID"].notna()].copy()
    return df


def _parse_time(val: Any) -> Optional[time]:
    return parse_time_value_as_time(val)


# =====================================================================
# VARIABLES / CONTRAINTES
# =====================================================================

def _create_be_variables(
    model: cp_model.CpModel,
    be_groups: pd.DataFrame,
    df_vols: pd.DataFrame,
    dest_info: Dict[str, Dict[str, Any]],
) -> Dict[Tuple[int, int], cp_model.IntVar]:
    x: Dict[Tuple[int, int], cp_model.IntVar] = {}
    for be_idx, be in be_groups.iterrows():
        dest_be = str(be["Destination"]).strip().upper()
        for v_idx, vol in df_vols.iterrows():
            dest_vol = vol["dest_iata"]
            if dest_be != dest_vol:
                continue
            jour_vol = vol["datetime"].weekday()
            if dest_vol in dest_info and dest_info[dest_vol]["jours_autorises"]:
                if jour_vol not in dest_info[dest_vol]["jours_autorises"]:
                    continue
            x[(be_idx, v_idx)] = model.NewBoolVar(f"x_{be_idx}_{v_idx}")
    return x


def _create_benev_variables(
    model: cp_model.CpModel, df_benev: pd.DataFrame, df_vols: pd.DataFrame
) -> Tuple[Dict[Tuple[int, int], cp_model.IntVar], Dict[int, List[int]], List[int], List[int]]:
    y: Dict[Tuple[int, int], cp_model.IntVar] = {}
    benev_vols_compat: Dict[int, List[int]] = defaultdict(list)
    vols_with_benev: List[int] = []
    benev_ids: List[int] = []

    for _, benev in df_benev.iterrows():
        benev_id = int(benev["ID"])
        benev_ids.append(benev_id)
        benev_date = benev["date_obj"].date()
        benev_debut = benev["heure_debut"]
        benev_fin = benev["heure_fin"]

        # Sécurise les heures (peuvent parfois arriver en string)
        benev_debut = benev_debut if isinstance(benev_debut, time) else _parse_time(benev_debut)
        benev_fin = benev_fin if isinstance(benev_fin, time) else _parse_time(benev_fin)
        if benev_debut is None or benev_fin is None:
            continue

        for v_idx, vol in df_vols.iterrows():
            vol_date = vol["datetime"].date()
            if benev_date != vol_date:
                continue

            heure_debut_requise = vol["datetime"] - timedelta(hours=DUREE_MISSION_HEURES)
            heure_fin_requise = vol["datetime"]

            benev_debut_dt = datetime.combine(benev_date, benev_debut)
            benev_fin_dt = datetime.combine(benev_date, benev_fin)

            if benev_debut_dt <= heure_debut_requise and benev_fin_dt >= heure_fin_requise:
                y[(benev_id, v_idx)] = model.NewBoolVar(f"y_{benev_id}_{v_idx}")
                benev_vols_compat[benev_id].append(v_idx)
                vols_with_benev.append(v_idx)

    return y, benev_vols_compat, list(sorted(set(vols_with_benev))), benev_ids


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
    vols_with_benev_set = set(vols_with_benev)
    # Interdire l'utilisation de vols sans bénévole compatible
    for (be_idx, v_idx), var in list(x.items()):
        if v_idx not in vols_with_benev_set:
            model.Add(var == 0)
    # BE expédié au plus 1 fois
    for be_idx in be_groups.index:
        vars_be = [x[(e, v)] for (e, v) in x if e == be_idx]
        if vars_be:
            model.Add(sum(vars_be) <= 1)

    # Capacité, charge, activation de vol
    for v_idx, vol in df_vols.iterrows():
        dest = vol["dest_iata"]
        max_capa = dest_info.get(dest, {}).get("max_colis", MAX_CAPACITE_PAR_VOL)

        be_in_flight: List[cp_model.IntVar] = []
        weights: List[int] = []

        for be_idx, be in be_groups.iterrows():
            if (be_idx, v_idx) in x:
                be_in_flight.append(x[(be_idx, v_idx)])
                weights.append(int(be["poids_total"]))

        if be_in_flight:
            model.Add(charge[v_idx] == sum(w * var for w, var in zip(weights, be_in_flight)))
            model.Add(charge[v_idx] <= max_capa)
            model.Add(nb_be[v_idx] == sum(be_in_flight))
            model.Add(nb_be[v_idx] <= MAX_BE_PER_FLIGHT)
            model.Add(sum(be_in_flight) > 0).OnlyEnforceIf(u[v_idx])
            model.Add(sum(be_in_flight) == 0).OnlyEnforceIf(u[v_idx].Not())
        else:
            model.Add(charge[v_idx] == 0)
            model.Add(nb_be[v_idx] == 0)
            model.Add(u[v_idx] == 0)


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
    # Staff par vol et capacité équivalente
    for v_idx in df_vols.index:
        staff_vars = [y[(b, v)] for (b, v) in y if v == v_idx]
        if staff_vars:
            model.Add(nb_benev[v_idx] == sum(staff_vars))
            model.Add(nb_benev[v_idx] >= 1).OnlyEnforceIf(u[v_idx])
            model.Add(nb_benev[v_idx] == 0).OnlyEnforceIf(u[v_idx].Not())
            if MAX_BENEV_PER_VOL is not None:
                model.Add(nb_benev[v_idx] <= MAX_BENEV_PER_VOL)
            # Charge globale contrainte par capacité bénévole
            model.Add(MAX_EQUIV_PER_VOLUNTEER * nb_benev[v_idx] >= charge[v_idx])

    # Temps minimum entre deux vols d'un même bénévole
    for benev_id in df_param["ID"].dropna().unique():
        vols = benev_vols_compat.get(int(benev_id), [])
        vols_sorted = sorted(vols, key=lambda vid: df_vols.loc[vid, "datetime"])
        for i, v1 in enumerate(vols_sorted):
            for v2 in vols_sorted[i + 1 :]:
                if (benev_id, v1) in y and (benev_id, v2) in y:
                    t1 = df_vols.loc[v1, "datetime"]
                    t2 = df_vols.loc[v2, "datetime"]
                    delta = abs((t2 - t1).total_seconds() / 3600)
                    if delta < MIN_HOURS_BETWEEN_FLIGHTS:
                        model.Add(y[(benev_id, v1)] + y[(benev_id, v2)] <= 1)

    # Quotas hebdo / jour
    for _, params in df_param.iterrows():
        benev_id = params.get("ID")
        if pd.isna(benev_id):
            continue
        benev_id = int(benev_id)
        missions = [(b, v) for (b, v) in y if b == benev_id]
        if not missions:
            continue

        max_sem = int(params.get("Max_Exp_Semaine", 999) or 999)
        max_jour = int(params.get("Max_Exp_Jour", 999) or 999)
        max_jours = int(params.get("Max_Jours_Semaine", 7) or 7)

        model.Add(sum(y[m] for m in missions) <= max_sem)

        vols_par_jour: Dict[datetime.date, List[Tuple[int, int]]] = defaultdict(list)
        for _, v in missions:
            vols_par_jour[df_vols.loc[v, "datetime"].date()].append((benev_id, v))
        for vols_jour in vols_par_jour.values():
            model.Add(sum(y[m] for m in vols_jour) <= max_jour)

        if len(vols_par_jour) > 1:
            jour_vars = {}
            for jour, vols_jour in vols_par_jour.items():
                jv = model.NewBoolVar(f"j_{benev_id}_{jour}")
                jour_vars[jour] = jv
                model.Add(sum(y[m] for m in vols_jour) >= 1).OnlyEnforceIf(jv)
                model.Add(sum(y[m] for m in vols_jour) == 0).OnlyEnforceIf(jv.Not())
            model.Add(sum(jour_vars.values()) <= max_jours)


def _add_dest_constraints(
    model: cp_model.CpModel,
    df_vols: pd.DataFrame,
    dest_info: Dict[str, Dict[str, Any]],
    u: Dict[int, cp_model.IntVar],
) -> None:
    for dest, info in dest_info.items():
        max_sem = info["max_vols_semaine"]
        vols_dest = [v for v, vol in df_vols.iterrows() if vol["dest_iata"] == dest]
        if vols_dest:
            vols_par_sem: Dict[Tuple[int, int], List[int]] = defaultdict(list)
            for v in vols_dest:
                sem = df_vols.loc[v, "datetime"].isocalendar()[1]
                year = df_vols.loc[v, "datetime"].isocalendar()[0]
                vols_par_sem[(year, sem)].append(v)
            for vols in vols_par_sem.values():
                model.Add(sum(u[v] for v in vols) <= max_sem)


def _optimize_equilibrage(
    model: cp_model.CpModel,
    solver: cp_model.CpSolver,
    y: Dict[Tuple[int, int], cp_model.IntVar],
    df_param: pd.DataFrame,
    verbose: bool,
) -> None:
    charges: List[cp_model.IntVar] = []
    for benev_id in df_param["ID"].dropna().unique():
        missions = [y[(b, v)] for (b, v) in y if b == int(benev_id)]
        if missions:
            c = model.NewIntVar(0, 100, f"c_{int(benev_id)}")
            model.Add(c == sum(missions))
            charges.append(c)

    if len(charges) > 1:
        max_c = model.NewIntVar(0, 100, "max_c")
        min_c = model.NewIntVar(0, 100, "min_c")
        model.AddMaxEquality(max_c, charges)
        model.AddMinEquality(min_c, charges)
        model.Minimize(max_c - min_c)
        status = solver.Solve(model)
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            delta = solver.ObjectiveValue()
            if verbose:
                print(f"[ORTOOLS] Phase équilibre : écart={int(delta)}")
            model.Add(max_c - min_c <= int(delta) + 1)


# =====================================================================
# EXTRACTION
# =====================================================================

def _extract_results(
    *,
    solver: cp_model.CpSolver,
    x: Dict[Tuple[int, int], cp_model.IntVar],
    y: Dict[Tuple[int, int], cp_model.IntVar],
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
    affectations = []
    be_affectes = set()

    for (be_idx, v_idx), var in x.items():
        if solver.Value(var) == 1:
            be = be_groups.loc[be_idx]
            vol = df_vols.loc[v_idx]
            be_num = be["BE_Numero"]
            be_affectes.add(be_num)
            affectations.append(
                {
                    "BE_Numero": be_num,
                    "BE_Expediteur": be.get("BE_Expediteur", ""),
                    "BE_Destinataire": be.get("BE_Destinataire", ""),
                    "Destination": be["Destination"],
                    "BE_Nb_Colis": int(be["nb_colis"]),
                    "BE_Poids_Equiv": int(be["poids_total"]),
                    "BE_Type": be.get("type", ""),
                    "Vol_Routing": vol.get("Routing", ""),
                    "Vol_Date": vol.get("Date_Vol") or vol["datetime"].date(),
                    "Vol_Heure": vol.get("Heure_Vol") or format_time_value(vol["datetime"].time(), fmt="%Hh%M", default=""),
                    "Vol_Numero": vol.get("Numero_Vol", ""),
                    "Vol_Destination": vol.get("Destination", vol.get("dest_iata", "")),
                    "Vol_Index": v_idx,
                }
            )

    df_affectations = pd.DataFrame(affectations)

    planning_benevoles = []
    for (benev_id, v_idx), var in y.items():
        if solver.Value(var) == 1:
            vol = df_vols.loc[v_idx]
            benev_info = df_param_benev[df_param_benev["ID"] == benev_id]
            nom = (
                benev_info["Benevole"].iloc[0]
                if len(benev_info) > 0
                else f"ID_{benev_id}"
            )
            phone = benev_info["Telephone"].iloc[0] if len(benev_info) > 0 else ""
            planning_benevoles.append(
                {
                    "Benevole_ID": benev_id,
                    "Benevole": nom,
                    "Telephone": phone,
                    "Vol_Index": v_idx,
                    "Vol_Date": vol.get("Date_Vol") or vol["datetime"].date(),
                    "Vol_Heure": vol.get("Heure_Vol") or format_time_value(vol["datetime"].time(), fmt="%Hh%M", default=""),
                    "Vol_Numero": vol.get("Numero_Vol", ""),
                    "Destination": vol.get("Destination", vol.get("dest_iata", "")),
                    "Charge_Equiv": int(solver.Value(charge[v_idx])),
                    "Nb_BE": int(solver.Value(nb_be[v_idx])),
                }
            )

    df_planning_benev = pd.DataFrame(planning_benevoles)

    vols_utilises = []
    for v_idx in df_vols.index:
        if solver.Value(u[v_idx]) == 1:
            vol = df_vols.loc[v_idx]
            nb_benev = sum(1 for (b, v) in y if v == v_idx and solver.Value(y[(b, v)]) == 1)
            vols_utilises.append(
                {
                    "Vol_Numero": vol.get("Numero_Vol", ""),
                    "Date": vol.get("Date_Vol") or vol["datetime"].date(),
                    "Heure": vol.get("Heure_Vol") or format_time_value(vol["datetime"].time(), fmt="%Hh%M", default=""),
                    "Destination": vol.get("Destination", vol.get("dest_iata", "")),
                    "Charge": int(solver.Value(charge[v_idx])),
                    "Nb_BE": int(solver.Value(nb_be[v_idx])),
                    "Nb_Benevoles": nb_benev,
                    "Vol_Index": v_idx,
                }
            )

    df_vols_utilises = pd.DataFrame(vols_utilises)

    df_non_planifies = df_be_original[~df_be_original["BE_Numero"].isin(be_affectes)].copy()

    # Détail par destination
    dest_stats_rows: List[Dict[str, Any]] = []
    if not df_be_original.empty:
        be_by_dest = df_be_original.groupby("Destination")["BE_Nb_Colis"].sum().fillna(0)
        be_count_by_dest = df_be_original.groupby("Destination")["BE_Numero"].nunique()
        aff_by_dest = (
            df_affectations.groupby("Destination")[["BE_Numero", "BE_Nb_Colis"]]
            .agg({"BE_Numero": "nunique", "BE_Nb_Colis": "sum"})
            if not df_affectations.empty
            else pd.DataFrame(columns=["BE_Numero", "BE_Nb_Colis"])
        )
        for dest, total_colis in be_by_dest.items():
            be_pl = int(aff_by_dest.loc[dest, "BE_Numero"]) if dest in aff_by_dest.index else 0
            colis_pl = int(aff_by_dest.loc[dest, "BE_Nb_Colis"]) if dest in aff_by_dest.index else 0
            dest_stats_rows.append(
                {
                    "Destination": dest,
                    "BE_total": int(be_count_by_dest.get(dest, 0)),
                    "BE_planifies": be_pl,
                    "Colis_total": int(total_colis),
                    "Colis_expedies": colis_pl,
                }
            )
    df_dest_stats = pd.DataFrame(dest_stats_rows)

    stats = {
        "status": "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE",
        "priority_mode": priority_mode,
        "nb_be_total": len(be_groups),
        "nb_be_envoyes": len(be_affectes),
        "taux_be": round(len(be_affectes) / len(be_groups) * 100, 1) if len(be_groups) else 0,
        "nb_vols_utilises": len(df_vols_utilises),
        "nb_benevoles_mobilises": len(df_planning_benev["Benevole_ID"].unique())
        if not df_planning_benev.empty
        else 0,
        "nb_colis_total": int(pd.to_numeric(df_be_original.get("BE_Nb_Colis", 0), errors="coerce").fillna(0).sum()),
        "nb_colis_expedies": int(df_affectations["BE_Nb_Colis"].sum()) if not df_affectations.empty else 0,
    }
    stats["taux_colis"] = (
        round(stats["nb_colis_expedies"] / stats["nb_colis_total"] * 100, 1)
        if stats["nb_colis_total"]
        else 0
    )

    if verbose:
        print("[ORTOOLS] Résumé :", stats)

    return {
        "affectations_be": df_affectations,
        "planning_benevoles": df_planning_benev,
        "vols_utilises": df_vols_utilises,
        "statistiques": stats,
        "status": stats["status"],
        "be_non_planifies": df_non_planifies,
        "dest_stats": df_dest_stats,
    }


def _build_planning_bilan(
    df_affectations: pd.DataFrame,
    df_planning_benev: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Recompose un planning au format proche du moteur principal :
      - 1 ligne par BE, avec bénévole associé (répartition greedy).
    """
    if df_affectations.empty or df_planning_benev.empty:
        return pd.DataFrame(), pd.DataFrame()

    # indexer affectations par vol
    affect_by_vol: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for _, row in df_affectations.iterrows():
        affect_by_vol[int(row["Vol_Index"])].append(row.to_dict())

    benev_by_vol: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for _, row in df_planning_benev.iterrows():
        benev_by_vol[int(row["Vol_Index"])].append(row.to_dict())

    planning_rows: List[Dict[str, Any]] = []
    for vol_idx, be_list in affect_by_vol.items():
        benev_list = benev_by_vol.get(vol_idx, [])
        if not benev_list:
            continue

        # Répartition greedy pour afficher Benevole / ID / Telephone
        load_map = {b["Benevole_ID"]: 0 for b in benev_list}

        for be in sorted(be_list, key=lambda x: x["BE_Poids_Equiv"], reverse=True):
            benev_sorted = sorted(load_map.items(), key=lambda kv: kv[1])
            chosen_id, current_load = benev_sorted[0]
            load_map[chosen_id] = current_load + int(be["BE_Poids_Equiv"])

            benev_info = next((b for b in benev_list if b["Benevole_ID"] == chosen_id), None) or {}
            planning_rows.append(
                {
                    "Date_Vol": be["Vol_Date"],
                    "Heure_Vol": be["Vol_Heure"]
                    if isinstance(be["Vol_Heure"], str)
                    else str(be["Vol_Heure"]),
                    "Numero_Vol": be.get("Vol_Numero", ""),
                    "Destination": be.get("Vol_Destination", ""),
                    "BE_Numero": be["BE_Numero"],
                    "BE_Nb_Colis": be.get("BE_Nb_Colis", 0),
                    "BE_Nb_Equiv": be.get("BE_Poids_Equiv", 0),
                    "BE_Expediteur": be.get("BE_Expediteur", ""),
                    "BE_Destinataire": be.get("BE_Destinataire", ""),
                    "BE_Type": be.get("BE_Type", ""),
                    "Routing": be.get("Vol_Routing", ""),
                    "Benevole": benev_info.get("Benevole", ""),
                    "ID": benev_info.get("Benevole_ID", ""),
                    "Telephone": benev_info.get("Telephone", ""),
                }
            )

    planning_df = pd.DataFrame(planning_rows)
    if not planning_df.empty:
        planning_df = planning_df.sort_values(
            ["Date_Vol", "Heure_Vol", "Numero_Vol", "Destination", "BE_Numero"]
        )

    # Bilan
    planned_be = set(planning_df["BE_Numero"].tolist()) if not planning_df.empty else set()
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
