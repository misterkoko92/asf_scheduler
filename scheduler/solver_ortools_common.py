# -*- coding: utf-8 -*-
"""Noyau commun des helpers OR-Tools (V2/V3).

Ce module centralise les fonctions pures partagées entre solver_ortools.py
et solver_ortools_v3.py afin de réduire la duplication sans changer
le comportement métier.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd

try:
    from ortools.sat.python import cp_model
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    cp_model = None

from scheduler.config import (
    DUREE_MISSION_HEURES,
    MAX_BE_PER_FLIGHT,
    MAX_BENEV_PER_VOL,
    MAX_CAPACITE_PAR_VOL,
    MAX_EQUIV_PER_VOLUNTEER,
    MIN_HOURS_BETWEEN_FLIGHTS,
)
from utils.datetime_utils import (
    coerce_datetime,
    parse_date_value_as_date,
    parse_time_value_as_time,
)
from utils.logging_utils import get_logger


def empty_result(status: str, *, include_assignations: bool = False) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
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
    if include_assignations:
        payload["assignations_benev"] = []
    return payload


def validate_inputs(
    df_be: pd.DataFrame,
    df_vols: pd.DataFrame,
    df_benev: pd.DataFrame,
) -> List[str]:
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
        missing_b = [
            c
            for c in ["Date", "Heure_Arrivee_time", "Heure_Depart_time"]
            if c not in df_benev.columns
        ]
        if missing_b:
            errors.append(f"Bénévoles : colonnes manquantes {missing_b}")
    return errors


def build_dest_info(df_param_dest: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
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
        except (TypeError, ValueError, OverflowError):
            max_colis = MAX_CAPACITE_PAR_VOL
        if max_colis <= 0:
            max_colis = MAX_CAPACITE_PAR_VOL

        try:
            max_vols = int(row.get("Freq_Semaine", 999))
        except (TypeError, ValueError, OverflowError):
            max_vols = 999
        if max_vols <= 0:
            max_vols = 999  # 0 ou vide = pas de limite explicite

        dest_info[dest_iata] = {
            "max_colis": max_colis,
            "max_vols_semaine": max_vols,
            "jours_autorises": jours_autorises,
        }
    return dest_info


def group_shipments(df_be: pd.DataFrame) -> pd.DataFrame:
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


def parse_time(val: Any) -> Optional[time]:
    return parse_time_value_as_time(val)


def parse_vols(
    df_vols_raw: pd.DataFrame,
    dest_info: Dict[str, Dict[str, Any]],
) -> pd.DataFrame:
    def _normalize_flight_number_key(raw_val: Any) -> str:
        value = str(raw_val or "").strip().upper()
        if not value:
            return ""
        return "".join(ch for ch in value if ch.isalnum())

    def _parse_datetime(row: pd.Series) -> Optional[datetime]:
        date_val = row.get("Date_Vol_dt") or coerce_datetime(
            row.get("Date_Vol"),
            errors="coerce",
            dayfirst=True,
        )
        if pd.isna(date_val):
            return None
        time_val = row.get("Heure_Vol_time") or parse_time(row.get("Heure_Vol"))
        if time_val is None:
            time_val = time(0, 0)
        try:
            date_only = parse_date_value_as_date(date_val)
            if date_only is None:
                return None
            return datetime.combine(date_only, time_val)
        except (TypeError, ValueError):
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

    if "Route_Pos" in df.columns:
        route_pos_series = pd.to_numeric(df["Route_Pos"], errors="coerce")
    elif "route_pos" in df.columns:
        route_pos_series = pd.to_numeric(df["route_pos"], errors="coerce")
    else:
        inferred_positions: List[int] = []
        for _, row in df.iterrows():
            dest_code = str(row.get("dest_iata", "")).strip().upper()
            routing_raw = str(row.get("Routing", "")).strip().upper()
            parts = [
                p
                for p in routing_raw.replace(",", "-").split("-")
                if str(p).strip()
            ]
            route_pos = 1
            for idx, code in enumerate(parts[1:], start=1):
                if str(code).strip().upper() == dest_code:
                    route_pos = idx
                    break
            inferred_positions.append(route_pos)
        route_pos_series = pd.Series(inferred_positions, index=df.index, dtype="float64")
    df["route_pos"] = route_pos_series.fillna(1).astype(int).clip(lower=1)

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

    # Clé de vol "physique" : même date/heure/numéro = même avion, quel que soit Dest_IATA.
    keys: List[str] = []
    for row_idx, row in df.iterrows():
        dt_val = row["datetime"]
        date_key = dt_val.date().isoformat()
        time_key = dt_val.strftime("%H:%M")
        num_key = _normalize_flight_number_key(row.get("Numero_Vol", ""))
        if num_key:
            keys.append(f"{date_key}|{time_key}|{num_key}")
        else:
            keys.append(f"{date_key}|{time_key}|IDX{row_idx}")
    df["physical_flight_key"] = keys
    return df


def parse_benevoles(
    df_benev_raw: pd.DataFrame,
    df_param: pd.DataFrame,
    *,
    extra_param_columns: Sequence[str] = (),
) -> pd.DataFrame:
    df = df_benev_raw.copy()

    date_col = "Date_dt" if "Date_dt" in df.columns else "Date"
    df["date_obj"] = coerce_datetime(df[date_col], errors="coerce", dayfirst=True)
    df = df[df["date_obj"].notna()].copy()

    if "Heure_Arrivee_time" in df.columns:
        df["heure_debut"] = df["Heure_Arrivee_time"]
        df["heure_fin"] = df["Heure_Depart_time"]
    else:
        df["heure_debut"] = df["Heure_Arrivee"].apply(parse_time)
        df["heure_fin"] = df["Heure_Depart"].apply(parse_time)
    df = df[(df["heure_debut"].notna()) & (df["heure_fin"].notna())].copy()

    if "ID" in df.columns:
        df["ID"] = pd.to_numeric(df["ID"], errors="coerce").astype("Int64")

    if "Max_Exp_Jour" not in df.columns:
        param_columns = [
            "ID",
            *extra_param_columns,
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
        # Conserve l'ordre mais évite les doublons de colonnes
        unique_param_columns = list(dict.fromkeys(param_columns))
        df = df.merge(
            df_param[unique_param_columns],
            on="ID",
            how="left",
        )

    df = df[df["ID"].notna()].copy()
    return df


def create_be_variables(
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


def create_benev_variables(
    model: cp_model.CpModel,
    df_benev: pd.DataFrame,
    df_vols: pd.DataFrame,
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
        benev_debut = benev_debut if isinstance(benev_debut, time) else parse_time(benev_debut)
        benev_fin = benev_fin if isinstance(benev_fin, time) else parse_time(benev_fin)
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


def add_be_constraints(
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


def add_benev_constraints(
    model: cp_model.CpModel,
    y: Dict[Tuple[int, int], cp_model.IntVar],
    u: Dict[int, cp_model.IntVar],
    charge: Dict[int, cp_model.IntVar],
    nb_benev: Dict[int, cp_model.IntVar],
    df_vols: pd.DataFrame,
    df_param: pd.DataFrame,
    benev_vols_compat: Dict[int, List[int]],
    *,
    enforce_equiv_capacity: bool,
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
            if enforce_equiv_capacity:
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

        vols_par_jour: Dict[date, List[Tuple[int, int]]] = defaultdict(list)
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


def add_dest_constraints(
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


def add_physical_flight_exclusivity_constraints(
    model: cp_model.CpModel,
    df_vols: pd.DataFrame,
    u: Dict[int, cp_model.IntVar],
) -> None:
    groups: Dict[str, List[int]] = defaultdict(list)
    for v_idx, row in df_vols.iterrows():
        key = str(row.get("physical_flight_key", "")).strip()
        if not key:
            continue
        groups[key].append(v_idx)

    for vols in groups.values():
        if len(vols) > 1:
            model.Add(sum(u[v] for v in vols) <= 1)


def add_physical_flight_routing_priority_constraints(
    model: cp_model.CpModel,
    df_vols: pd.DataFrame,
    x: Dict[Tuple[int, int], cp_model.IntVar],
    u: Dict[int, cp_model.IntVar],
    vols_with_benev: List[int],
) -> None:
    x_by_vol: Dict[int, List[cp_model.IntVar]] = defaultdict(list)
    for (_, v_idx), var in x.items():
        x_by_vol[v_idx].append(var)

    vols_with_benev_set = set(vols_with_benev)
    groups: Dict[str, List[int]] = defaultdict(list)
    for v_idx, row in df_vols.iterrows():
        key = str(row.get("physical_flight_key", "")).strip()
        if key:
            groups[key].append(v_idx)

    for vols in groups.values():
        candidates = [v for v in vols if v in vols_with_benev_set and x_by_vol.get(v)]
        if len(candidates) < 2:
            continue

        min_route_pos = min(int(df_vols.loc[v, "route_pos"]) for v in candidates)
        non_priority_vols = [v for v in candidates if int(df_vols.loc[v, "route_pos"]) > min_route_pos]
        if not non_priority_vols:
            continue

        # Règle métier: en conflit sur un même vol physique, on garde la 1re destination du routing.
        for v_idx in non_priority_vols:
            model.Add(u[v_idx] == 0)
            for var in x_by_vol[v_idx]:
                model.Add(var == 0)


def build_vols_compatibility_df(
    df_vols: pd.DataFrame,
    x: Dict[Tuple[int, int], cp_model.IntVar],
    y: Dict[Tuple[int, int], cp_model.IntVar],
    *,
    u: Dict[int, cp_model.IntVar] | None = None,
    solver: cp_model.CpSolver | None = None,
) -> pd.DataFrame:
    be_count_by_vol: Dict[int, int] = defaultdict(int)
    benev_count_by_vol: Dict[int, int] = defaultdict(int)
    for (_, v_idx) in x.keys():
        be_count_by_vol[int(v_idx)] += 1
    for (_, v_idx) in y.keys():
        benev_count_by_vol[int(v_idx)] += 1

    rows: List[Dict[str, Any]] = []
    for v_idx, row in df_vols.iterrows():
        date_val = row.get("Date_Vol") or row.get("datetime")
        hour_val = row.get("Heure_Vol")
        used_flag: int | None = None
        if u is not None and solver is not None and v_idx in u:
            used_flag = int(solver.Value(u[v_idx]))
        rows.append(
            {
                "Vol_Index": int(v_idx),
                "Date_Vol": date_val,
                "Heure_Vol": hour_val,
                "Numero_Vol": row.get("Numero_Vol", ""),
                "Destination": row.get("Destination", row.get("dest_iata", "")),
                "Dest_IATA": row.get("dest_iata", row.get("IATA", "")),
                "Routing": row.get("Routing", ""),
                "Route_Pos": int(row.get("route_pos", 1) or 1),
                "Physical_Flight_Key": row.get("physical_flight_key", ""),
                "BE_Compat_Count": int(be_count_by_vol.get(int(v_idx), 0)),
                "Benev_Compat_Count": int(benev_count_by_vol.get(int(v_idx), 0)),
                "Used": used_flag,
            }
        )
    return pd.DataFrame(rows)


def summarize_vols_compatibility(df_diag: pd.DataFrame) -> Dict[str, int]:
    if df_diag is None or df_diag.empty:
        return {
            "nb_vols_total": 0,
            "nb_vols_sans_be_compatible": 0,
            "nb_vols_sans_benevole_compatible": 0,
            "nb_vols_sans_compatibilite_complete": 0,
            "nb_vols_non_utilises_avec_compatibilite": 0,
        }

    be_compat = pd.to_numeric(df_diag.get("BE_Compat_Count"), errors="coerce").fillna(0).astype(int)
    benev_compat = pd.to_numeric(df_diag.get("Benev_Compat_Count"), errors="coerce").fillna(0).astype(int)
    used = pd.to_numeric(df_diag.get("Used"), errors="coerce")

    has_full_compat = (be_compat > 0) & (benev_compat > 0)
    summary = {
        "nb_vols_total": int(len(df_diag)),
        "nb_vols_sans_be_compatible": int((be_compat == 0).sum()),
        "nb_vols_sans_benevole_compatible": int((benev_compat == 0).sum()),
        "nb_vols_sans_compatibilite_complete": int((~has_full_compat).sum()),
        "nb_vols_non_utilises_avec_compatibilite": int(((used == 0) & has_full_compat).sum()) if not used.isna().all() else 0,
    }
    return summary


def optimize_equilibrage(
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
                get_logger("ortools_sim", console=True).info(
                    "[ORTOOLS] Phase équilibre : écart=%s",
                    int(delta),
                )
            model.Add(max_c - min_c <= int(delta) + 1)


def build_planning_bilan(
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
