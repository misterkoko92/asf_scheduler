from pathlib import Path
from typing import Any, cast

import pandas as pd
import streamlit as st

from asf_app.config.runtime import get_tableau_de_bord_src, is_graph_onedrive
from asf_app.services.simulation_runner import run_ortools_simulation_dual
from asf_app.state import get_excel_source_paths, get_state
from scheduler.data_sources import ExcelDataSource
from scheduler.planning_schema import normalize_planning_df
from scheduler.planning_views import build_export_view
from scheduler.solver_router import get_solver_version
from utils.benevole_utils import count_benevoles_with_dispo
from utils.datetime_utils import coerce_datetime, parse_date_series, parse_time_series
from utils.ui_helpers import (
    build_iata_city_maps,
    format_be_label,
    format_vol_label,
    sort_planning_df,
)


# Backward compatibility wrapper (historical name kept in code paths)
def _sort_planning(df):
    return sort_planning_df(df)


def _style_manual_df(df: pd.DataFrame):
    if df is None or df.empty:
        return df
    mask_manual = (
        df["_MANUEL"] == True if "_MANUEL" in df.columns else pd.Series(False, index=df.index)  # noqa: E712
    )
    df_display = df.drop(columns=["_MANUEL"], errors="ignore")

    def _apply(_df):
        styles = pd.DataFrame("", index=_df.index, columns=_df.columns)
        styles.loc[mask_manual[mask_manual].index] = "background-color: #f2f2f2"
        return styles

    return df_display.style.apply(_apply, axis=None)


def _normalize_be_key(value: object) -> str:
    return (
        str(value if value is not None else "")
        .replace(".0", "")
        .strip()
    )


def _to_int_or_zero(value: object) -> int:
    try:
        numeric = pd.to_numeric(value, errors="coerce")
    except (TypeError, ValueError):
        return 0
    if pd.isna(numeric):
        return 0
    return int(numeric)


def _build_reason_context(
    *,
    df_plan: pd.DataFrame | None,
    df_vols_src: pd.DataFrame | None,
    df_dispo_src: pd.DataFrame | None,
    start_dt,
    end_dt,
) -> dict[str, Any]:
    context: dict[str, Any] = {
        "vols": pd.DataFrame(),
        "dispos": pd.DataFrame(),
        "plan_load": {},
    }

    if df_vols_src is not None and not df_vols_src.empty:
        vols = df_vols_src.copy()
        vols["_Dest_Code"] = (
            vols.get("IATA", vols.get("Dest_IATA", vols.get("Destination", pd.Series(dtype=object))))
            .astype(str)
            .str.strip()
            .str.upper()
        )
        vols["_Date_dt"] = parse_date_series(vols.get("Date_Vol", pd.Series(dtype=object)))
        if start_dt is not None and end_dt is not None:
            vols = vols[(vols["_Date_dt"] >= start_dt) & (vols["_Date_dt"] <= end_dt)]
        vols["_Vol_Numero"] = vols.get("Numero_Vol", pd.Series(dtype=object)).astype(str).str.strip()
        vols_hour_dt = parse_time_series(
            vols.get("Heure_Vol", pd.Series(dtype=object)),
            allow_hour_only=True,
            allow_general_fallback=True,
            strip_spaces=True,
            lowercase=True,
        )
        vols["_Heure_Min"] = (
            vols_hour_dt.dt.hour.fillna(0).astype(int) * 60
            + vols_hour_dt.dt.minute.fillna(0).astype(int)
        )
        invalid_hour = vols_hour_dt.isna()
        vols.loc[invalid_hour, "_Heure_Min"] = pd.NA
        vols["_Date_only"] = vols["_Date_dt"].dt.date
        vols["_Max_Colis"] = pd.to_numeric(vols.get("Max_Colis", pd.Series(dtype=object)), errors="coerce")
        context["vols"] = vols

    if df_dispo_src is not None and not df_dispo_src.empty:
        dispos = df_dispo_src.copy()
        if "Date_dt" in dispos.columns:
            dispos["_Date_dt"] = coerce_datetime(dispos["Date_dt"], errors="coerce")
        else:
            dispos["_Date_dt"] = parse_date_series(dispos.get("Date", pd.Series(dtype=object)))
        if start_dt is not None and end_dt is not None:
            dispos = dispos[(dispos["_Date_dt"] >= start_dt) & (dispos["_Date_dt"] <= end_dt)]
        arr_col = "Heure_Arrivee_time" if "Heure_Arrivee_time" in dispos.columns else "Heure_Arrivee"
        dep_col = "Heure_Depart_time" if "Heure_Depart_time" in dispos.columns else "Heure_Depart"
        arr_dt = parse_time_series(
            dispos.get(arr_col, pd.Series(dtype=object)),
            allow_hour_only=True,
            allow_general_fallback=True,
            strip_spaces=True,
            lowercase=True,
        )
        dep_dt = parse_time_series(
            dispos.get(dep_col, pd.Series(dtype=object)),
            allow_hour_only=True,
            allow_general_fallback=True,
            strip_spaces=True,
            lowercase=True,
        )
        dispos["_Arr_Min"] = arr_dt.dt.hour.fillna(0).astype(int) * 60 + arr_dt.dt.minute.fillna(0).astype(int)
        dispos["_Dep_Min"] = dep_dt.dt.hour.fillna(0).astype(int) * 60 + dep_dt.dt.minute.fillna(0).astype(int)
        dispos.loc[arr_dt.isna(), "_Arr_Min"] = pd.NA
        dispos.loc[dep_dt.isna(), "_Dep_Min"] = pd.NA
        dispos["_Date_only"] = dispos["_Date_dt"].dt.date
        context["dispos"] = dispos

    if df_plan is not None and not df_plan.empty:
        plan_local = df_plan.copy()
        plan_local["_Date_dt"] = parse_date_series(plan_local.get("Date_Vol", pd.Series(dtype=object)))
        heure_dt = parse_time_series(
            plan_local.get("Heure_Vol", pd.Series(dtype=object)),
            allow_hour_only=True,
            allow_general_fallback=True,
            strip_spaces=True,
            lowercase=True,
        )
        plan_local["_Heure_Min"] = heure_dt.dt.hour.fillna(0).astype(int) * 60 + heure_dt.dt.minute.fillna(0).astype(int)
        plan_local.loc[heure_dt.isna(), "_Heure_Min"] = pd.NA
        plan_local["_Date_only"] = plan_local["_Date_dt"].dt.date
        plan_local["_Vol_Numero"] = plan_local.get("Numero_Vol", pd.Series(dtype=object)).astype(str).str.strip()
        plan_local["_Charge"] = pd.to_numeric(
            plan_local.get("BE_Nb_Equiv", plan_local.get("Equiv_Colis", plan_local.get("BE_Nb_Colis", 0))),
            errors="coerce",
        ).fillna(0)
        load_map = (
            plan_local.groupby(["_Date_only", "_Heure_Min", "_Vol_Numero"], dropna=True)["_Charge"].sum().to_dict()
        )
        context["plan_load"] = load_map

    return context


def _infer_non_affectation_reason(
    *,
    dest_code: str,
    reason_context: dict[str, Any],
) -> str:
    if not dest_code:
        return "Destination manquante"

    vols = cast(pd.DataFrame, reason_context.get("vols", pd.DataFrame()))
    dispos = cast(pd.DataFrame, reason_context.get("dispos", pd.DataFrame()))
    plan_load = cast(dict[tuple[object, object, object], float], reason_context.get("plan_load", {}))

    if vols is None or vols.empty:
        return f"Aucun vol vers {dest_code} sur la période"

    vols_dest = vols[vols["_Dest_Code"] == str(dest_code).upper()].copy()
    if vols_dest.empty:
        return f"Aucun vol vers {dest_code} sur la période"

    vols_sched = vols_dest[vols_dest["_Date_only"].notna() & vols_dest["_Heure_Min"].notna()].copy()
    if vols_sched.empty:
        return f"Vols vers {dest_code} sans horaire exploitable"

    if dispos is None or dispos.empty:
        return "Aucun bénévole disponible sur les créneaux vols"

    has_benev_available = False
    for _, flight in vols_sched.iterrows():
        day_rows = dispos[dispos["_Date_only"] == flight["_Date_only"]]
        if day_rows.empty:
            continue
        ok_rows = day_rows[
            day_rows["_Arr_Min"].notna()
            & day_rows["_Dep_Min"].notna()
            & (day_rows["_Arr_Min"] <= int(flight["_Heure_Min"]))
            & (day_rows["_Dep_Min"] >= int(flight["_Heure_Min"]))
        ]
        if not ok_rows.empty:
            has_benev_available = True
            break
    if not has_benev_available:
        return "Aucun bénévole disponible sur les créneaux vols"

    cap_known = vols_sched["_Max_Colis"].notna().any()
    if cap_known:
        has_remaining_capacity = False
        for _, flight in vols_sched.iterrows():
            cap = flight.get("_Max_Colis")
            if pd.isna(cap):
                has_remaining_capacity = True
                break
            key = (flight["_Date_only"], flight["_Heure_Min"], flight["_Vol_Numero"])
            used = float(plan_load.get(key, 0))
            if used < float(cap):
                has_remaining_capacity = True
                break
        if not has_remaining_capacity:
            return "Capacité vols atteinte sur la période"

    return "Conflit de contraintes (priorités/quotas)"


def _recompute_bilan(
    df_plan: pd.DataFrame,
    *,
    df_be_src: pd.DataFrame | None = None,
    df_vols_src: pd.DataFrame | None = None,
    df_dispo_src: pd.DataFrame | None = None,
    start_dt=None,
    end_dt=None,
) -> pd.DataFrame:
    cols = []
    reason_context: dict[str, Any] | None = None
    if (df_vols_src is not None and not df_vols_src.empty) or (
        df_dispo_src is not None and not df_dispo_src.empty
    ):
        reason_context = _build_reason_context(
            df_plan=df_plan,
            df_vols_src=df_vols_src,
            df_dispo_src=df_dispo_src,
            start_dt=start_dt,
            end_dt=end_dt,
        )

    df_plan_local = pd.DataFrame()
    if df_plan is not None and not df_plan.empty:
        df_plan_local = df_plan.copy()
        df_plan_local["_BE_Key"] = df_plan_local.get("BE_Numero", "").apply(_normalize_be_key)
        df_plan_local = df_plan_local[df_plan_local["_BE_Key"] != ""]

        for _, row in df_plan_local.iterrows():
            nb_colis = row.get("BE_Nb_Colis", row.get("BE_Nb_Colis_MAG", 0))
            nb_equiv = row.get("BE_Nb_Equiv", row.get("Equiv_Colis", 0))
            cols.append(
                {
                    "Date_Vol": row.get("Date_Vol", ""),
                    "Numero_Vol": row.get("Numero_Vol", ""),
                    "Destination": row.get("Destination", ""),
                    "BE_Numero": row.get("_BE_Key", ""),
                    "Nb_Colis": nb_colis if pd.notna(nb_colis) else 0,
                    "Nb_Equiv": nb_equiv if pd.notna(nb_equiv) else 0,
                    "Partant": "OUI",
                    "Raison": "MANUEL" if row.get("_MANUEL", False) else "OK",
                    "BE_Destinataire": row.get("BE_Destinataire", ""),
                    "_MANUEL": bool(row.get("_MANUEL", False)),
                }
            )

    if df_be_src is not None and not df_be_src.empty:
        df_be_local = df_be_src.copy()
        df_be_local["_BE_Key"] = df_be_local.get("BE_Numero", "").apply(_normalize_be_key)
        df_be_local = df_be_local[df_be_local["_BE_Key"] != ""].copy()

        planned_keys = set(df_plan_local.get("_BE_Key", pd.Series(dtype=str)))
        non_planifies = (
            df_be_local[~df_be_local["_BE_Key"].isin(planned_keys)]
            .drop_duplicates(subset=["_BE_Key"], keep="first")
        )
        for _, row in non_planifies.iterrows():
            nb_colis = row.get("BE_Nb_Colis", row.get("BE_Nb_Colis_MAG", 0))
            nb_equiv = row.get("Equiv_Colis", row.get("BE_Nb_Equiv", 0))
            raison_val = row.get("Raison", "")
            raison_raw = "" if pd.isna(raison_val) else str(raison_val).strip()
            dest_code = str(row.get("Destination", "")).strip().upper()
            if reason_context is not None:
                inferred_reason = _infer_non_affectation_reason(
                    dest_code=dest_code,
                    reason_context=reason_context,
                )
            else:
                inferred_reason = "NON AFFECTE"
            cols.append(
                {
                    "Date_Vol": "",
                    "Numero_Vol": "",
                    "Destination": dest_code,
                    "BE_Numero": row.get("_BE_Key", ""),
                    "Nb_Colis": nb_colis if pd.notna(nb_colis) else 0,
                    "Nb_Equiv": nb_equiv if pd.notna(nb_equiv) else 0,
                    "Partant": "NON",
                    "Raison": raison_raw or inferred_reason,
                    "BE_Destinataire": row.get("BE_Destinataire", ""),
                    "_MANUEL": False,
                }
            )

    out = pd.DataFrame(cols)
    if out.empty:
        return out
    out["Partant_Order"] = out["Partant"].map({"OUI": 0, "NON": 1}).fillna(2)
    out = out.sort_values(["Partant_Order", "BE_Numero"], kind="mergesort").drop(columns=["Partant_Order"])
    return out.reset_index(drop=True)


def _recompute_vols(df_plan: pd.DataFrame) -> pd.DataFrame:
    if df_plan is None or df_plan.empty:
        return pd.DataFrame()
    df = df_plan.copy()
    df["_MANUEL"] = df.get("_MANUEL", False)
    agg = (
        df.groupby(["Date_Vol", "Numero_Vol", "Destination"], as_index=False)
        .agg(
            {
                "Heure_Vol": "first",
                "BE_Numero": "count",
                "Benevole": pd.Series.nunique,
                "_MANUEL": "max",
            }
        )
        .rename(columns={"BE_Numero": "Nb_BE", "Benevole": "Nb_Benevoles"})
    )
    return agg


def _recompute_benev(df_plan: pd.DataFrame) -> pd.DataFrame:
    if df_plan is None or df_plan.empty:
        return pd.DataFrame()
    rows = []
    for _, row in df_plan.iterrows():
        rows.append(
            {
                "Benevole": row.get("Benevole", ""),
                "Date_Vol": row.get("Date_Vol", ""),
                "Heure_Vol": row.get("Heure_Vol", ""),
                "Numero_Vol": row.get("Numero_Vol", ""),
                "Destination": row.get("Destination", ""),
                "BE_Numero": row.get("BE_Numero", ""),
                "_MANUEL": bool(row.get("_MANUEL", False)),
            }
        )
    df = pd.DataFrame(rows)
    return df[df["Benevole"].astype(str).str.strip() != ""]


def _recompute_dest_stats(
    df_plan: pd.DataFrame,
    *,
    df_vols_src: pd.DataFrame | None = None,
    df_paramdest: pd.DataFrame | None = None,
    start_dt=None,
    end_dt=None,
) -> pd.DataFrame:
    if df_plan is None or df_plan.empty:
        return pd.DataFrame()

    def _norm_dest(series: pd.Series) -> pd.Series:
        out = series.astype(str).str.strip().str.upper()
        return out.replace({"NAN": "", "NONE": "", "<NA>": ""})

    def _build_dest_maps(df_param: pd.DataFrame | None) -> tuple[dict[str, str], dict[str, str]]:
        iata_to_city: dict[str, str] = {}
        city_to_iata: dict[str, str] = {}
        if df_param is None or df_param.empty:
            return iata_to_city, city_to_iata
        for _, row in df_param.iterrows():
            iata = str(row.get("Dest_IATA", "")).strip().upper()
            city = str(row.get("Dest_Ville", row.get("Destination", ""))).strip().upper()
            if not iata:
                continue
            iata_to_city[iata] = city or iata
            if city:
                city_to_iata[city] = iata
        return iata_to_city, city_to_iata

    iata_to_city, city_to_iata = _build_dest_maps(df_paramdest)

    def _dest_to_key(value: object) -> str:
        raw = str(value if value is not None else "").strip().upper()
        if raw in ("", "NAN", "NONE", "<NA>"):
            return ""
        if raw in iata_to_city:
            return raw
        if raw in city_to_iata:
            return city_to_iata[raw]
        return raw

    def _build_allowed_days_map(df_param: pd.DataFrame | None) -> dict[str, set[int]]:
        if df_param is None or df_param.empty:
            return {}
        days_cols = [
            "Freq_Lundi",
            "Freq_Mardi",
            "Freq_Mercredi",
            "Freq_Jeudi",
            "Freq_Vendredi",
            "Freq_Samedi",
            "Freq_Dimanche",
        ]
        out: dict[str, set[int]] = {}
        for _, row in df_param.iterrows():
            dest = str(row.get("Dest_IATA", "")).strip().upper()
            if not dest:
                continue
            allowed: set[int] = set()
            for idx, col in enumerate(days_cols):
                val = row.get(col, 0)
                sval = str(val).strip().lower()
                if val == 1 or sval == "1" or sval == "ok":
                    allowed.add(idx)
            out[dest] = allowed
        return out

    def _parse_hour_key(series: pd.Series) -> pd.Series:
        parsed = parse_time_series(
            series,
            allow_hour_only=True,
            allow_general_fallback=True,
            strip_spaces=True,
            lowercase=True,
        )
        return parsed.dt.strftime("%H:%M").fillna(series.astype(str).str.strip())

    df = df_plan.copy()
    df["_MANUEL"] = df.get("_MANUEL", False)
    df["_Dest_Raw"] = _norm_dest(df.get("Destination", pd.Series(dtype=object)))
    df["_Dest_Key"] = df["_Dest_Raw"].apply(_dest_to_key)
    df = df[df["_Dest_Key"] != ""].copy()
    df["Destination"] = df["_Dest_Key"].map(iata_to_city).fillna(df["_Dest_Raw"])
    agg = (
        df.groupby("_Dest_Key", as_index=False)
        .agg(
            {
                "Destination": "first",
                "BE_Numero": "count",
                "BE_Nb_Colis": "sum",
                "BE_Nb_Equiv": "sum",
                "_MANUEL": "max",
            }
        )
        .rename(columns={"BE_Numero": "Nb_BE", "BE_Nb_Colis": "Nb_Colis", "BE_Nb_Equiv": "Nb_Equiv"})
    )

    # Vols utilisés (uniques) depuis le planning final
    plan_keys = df.copy()
    plan_keys["_Dest_Key"] = plan_keys.get("_Dest_Key", plan_keys.get("Destination", pd.Series(dtype=object)).apply(_dest_to_key))
    plan_keys["_Date_dt"] = parse_date_series(plan_keys.get("Date_Vol", pd.Series(dtype=object)))
    plan_keys["_Heure_Key"] = _parse_hour_key(plan_keys.get("Heure_Vol", pd.Series(dtype=object)))
    plan_keys["_Vol_Numero"] = plan_keys.get("Numero_Vol", pd.Series(dtype=object)).astype(str).str.strip()
    used_counts = (
        plan_keys[["_Dest_Key", "_Date_dt", "_Heure_Key", "_Vol_Numero"]]
        .dropna(subset=["_Dest_Key", "_Date_dt"])
        .query("_Dest_Key != ''")
        .drop_duplicates()
        .groupby("_Dest_Key")
        .size()
        .to_dict()
    )

    # Vols existants (uniques) depuis df_vols, filtrés par jours autorisés ParamDest
    existing_counts: dict[str, int] = {}
    if df_vols_src is not None and not df_vols_src.empty:
        vols = df_vols_src.copy()
        vols["_Dest_Raw"] = _norm_dest(
            vols.get("IATA", vols.get("Dest_IATA", vols.get("Destination", pd.Series(dtype=object))))
        )
        vols["_Dest_Key"] = vols["_Dest_Raw"].apply(_dest_to_key)
        vols["_Date_dt"] = parse_date_series(vols.get("Date_Vol", pd.Series(dtype=object)))
        vols["_Heure_Key"] = _parse_hour_key(vols.get("Heure_Vol", pd.Series(dtype=object)))
        vols["_Vol_Numero"] = vols.get("Numero_Vol", pd.Series(dtype=object)).astype(str).str.strip()
        vols = vols[vols["_Dest_Key"] != ""]

        if start_dt is not None and end_dt is not None:
            vols = vols[(vols["_Date_dt"] >= start_dt) & (vols["_Date_dt"] <= end_dt)]

        allowed_days_map = _build_allowed_days_map(df_paramdest)
        if not vols.empty and allowed_days_map:
            keep = []
            for _, row in vols.iterrows():
                dest = str(row.get("_Dest_Key", "")).strip().upper()
                dt_val = row.get("_Date_dt")
                if pd.isna(dt_val):
                    keep.append(False)
                    continue
                allowed = allowed_days_map.get(dest, set())
                if not allowed:
                    keep.append(True)
                    continue
                keep.append(int(dt_val.weekday()) in allowed)
            vols = vols[pd.Series(keep, index=vols.index)]

        existing_counts = (
            vols[["_Dest_Key", "_Date_dt", "_Heure_Key", "_Vol_Numero"]]
            .dropna(subset=["_Dest_Key", "_Date_dt"])
            .query("_Dest_Key != ''")
            .drop_duplicates()
            .groupby("_Dest_Key")
            .size()
            .astype(int)
            .to_dict()
        )

    agg["Nb_Vols_Existant"] = agg["_Dest_Key"].map(existing_counts).fillna(0).astype(int)
    agg["Nb_Vols_Utilises"] = agg["_Dest_Key"].map(used_counts).fillna(0).astype(int)

    ordered_cols = [
        "Destination",
        "Nb_Vols_Existant",
        "Nb_Vols_Utilises",
        "Nb_BE",
        "Nb_Colis",
        "Nb_Equiv",
        "_MANUEL",
    ]
    return agg[ordered_cols].sort_values("Destination", kind="mergesort").reset_index(drop=True)


def _recompute_be_non_planifies(df_plan: pd.DataFrame, df_be_src: pd.DataFrame) -> pd.DataFrame:
    if df_be_src is None or df_be_src.empty:
        return pd.DataFrame()
    planned = set(df_plan["BE_Numero"].astype(str)) if df_plan is not None and not df_plan.empty else set()
    df_src = df_be_src.copy()
    df_src["BE_Numero_str"] = df_src["BE_Numero"].astype(str)
    return df_src[~df_src["BE_Numero_str"].isin(planned)]


def _recompute_bilan_benevoles(
    df_plan: pd.DataFrame,
    df_dispo_src: pd.DataFrame,
    *,
    df_parambenev: pd.DataFrame,
    start_dt,
    end_dt,
) -> pd.DataFrame:
    """
    - Nombre de disponibilités (0..7) sur la semaine
    - Nombre de jours affectés (unique dates)
    - Nombre de vols affectés
    - Nombre de BE affectés
    """
    if df_plan is None and df_dispo_src is None:
        return pd.DataFrame()

    # Disponibilités par bénévole (filtrées sur la semaine)
    dispo_counts = {}
    try:
        df_tmp = df_dispo_src.copy()
        if "Date_dt" in df_tmp.columns:
            dt_parsed = coerce_datetime(df_tmp["Date_dt"], errors="coerce")
        else:
            dt_parsed = parse_date_series(df_tmp.get("Date", pd.Series(dtype=object)))
        df_tmp["_Date_dt"] = dt_parsed

        # Déterminer la fenêtre si absente
        if start_dt is None or end_dt is None:
            dates_non_na = df_tmp["_Date_dt"].dropna()
            if not dates_non_na.empty:
                start_dt = dates_non_na.min() if start_dt is None else start_dt
                end_dt = dates_non_na.max() if end_dt is None else end_dt

        mask_week = df_tmp["_Date_dt"].notna()
        if start_dt is not None and end_dt is not None:
            mask_week &= (df_tmp["_Date_dt"] >= start_dt) & (df_tmp["_Date_dt"] <= end_dt)

        df_tmp = df_tmp[mask_week]
        # Garder uniquement les lignes avec plage horaire valide
        df_tmp["Benevole"] = (
            df_tmp.get("Benevole", pd.Series(dtype=object))
            .astype(str)
            .str.strip()
            .replace("", pd.NA)
        )
        arr_col = "Heure_Arrivee_time" if "Heure_Arrivee_time" in df_tmp.columns else "Heure_Arrivee"
        dep_col = "Heure_Depart_time" if "Heure_Depart_time" in df_tmp.columns else "Heure_Depart"
        arr_parsed = parse_time_series(
            df_tmp.get(arr_col, pd.Series(dtype=object)),
            allow_hour_only=True,
            allow_general_fallback=True,
            strip_spaces=True,
            lowercase=True,
        )
        dep_parsed = parse_time_series(
            df_tmp.get(dep_col, pd.Series(dtype=object)),
            allow_hour_only=True,
            allow_general_fallback=True,
            strip_spaces=True,
            lowercase=True,
        )
        df_tmp = df_tmp[df_tmp["Benevole"].notna() & arr_parsed.notna() & dep_parsed.notna()]
        df_tmp["_Date_only"] = df_tmp["_Date_dt"].dt.date
        dispo_counts = df_tmp.groupby("Benevole")["_Date_only"].nunique().to_dict()
    except (AttributeError, KeyError, TypeError, ValueError):
        dispo_counts = {}

    # Affectations
    rows = []
    df_plan_local = pd.DataFrame()
    if df_plan is not None and not df_plan.empty:
        df_plan_local = df_plan.copy()
        df_plan_local["_Date_dt"] = parse_date_series(df_plan_local.get("Date_Vol", ""))
        df_plan_local["Benevole"] = (
            df_plan_local.get("Benevole", pd.Series(dtype=object))
            .astype(str)
            .str.strip()
            .replace("", pd.NA)
        )
        df_plan_local["_Vol_Numero"] = (
            df_plan_local.get("Numero_Vol", pd.Series(dtype=object))
            .astype(str)
            .str.strip()
        )
        df_plan_local["_Vol_Heure"] = (
            parse_time_series(
                df_plan_local.get("Heure_Vol", pd.Series(dtype=object)),
                allow_hour_only=True,
                allow_general_fallback=True,
                strip_spaces=True,
                lowercase=True,
            )
            .dt.strftime("%H:%M")
            .fillna(df_plan_local.get("Heure_Vol", pd.Series(dtype=object)).astype(str).str.strip())
        )
        df_plan_local["_BE_Numero"] = (
            df_plan_local.get("BE_Numero", pd.Series(dtype=object))
            .astype(str)
            .str.strip()
        )

    benevole_set = set(dispo_counts.keys())
    benevole_set.update(df_plan_local.get("Benevole", []).dropna().unique() if not df_plan_local.empty else [])
    # Ajouter tous les bénévoles connus (même sans dispo)
    try:
        benevole_set.update(
            df_parambenev["Benevole"]
            .dropna()
            .astype(str)
            .str.strip()
            .replace("", pd.NA)
            .dropna()
            .unique()
        )
    except (AttributeError, KeyError, TypeError):
        pass

    for bene in benevole_set:
        if str(bene).strip() == "":
            continue
        nb_dispo = int(dispo_counts.get(bene, 0))
        if not df_plan_local.empty:
            grp = df_plan_local[df_plan_local["Benevole"] == str(bene).strip()]
            nb_jours = int(grp["_Date_dt"].dt.date.nunique())
            nb_vols = int(
                grp[["_Date_dt", "_Vol_Heure", "_Vol_Numero"]]
                .drop_duplicates()
                .shape[0]
            )
            nb_be = int(grp["_BE_Numero"].replace("", pd.NA).dropna().nunique())
            if "_MANUEL" in grp.columns:
                manual_flag = bool(grp["_MANUEL"].fillna(False).astype(bool).any())
            else:
                manual_flag = False
        else:
            nb_jours = 0
            nb_vols = 0
            nb_be = 0
            manual_flag = False
        rows.append(
            {
                "Benevole": bene,
                "Nb_Dispo": nb_dispo,
                "Nb_Jours_Affectes": nb_jours,
                "Nb_Vols_Affectes": nb_vols,
                "Nb_BE_Affectes": nb_be,
                "_MANUEL": manual_flag,
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values("Benevole", kind="mergesort").reset_index(drop=True)


def _compute_resume_numbers(
    df_plan: pd.DataFrame,
    *,
    df_be: pd.DataFrame,
    df_dispo: pd.DataFrame,
    start_dt,
    end_dt,
    stats: dict,
):
    nb_be_total = df_be["BE_Numero"].nunique() if df_be is not None and not df_be.empty else 0
    nb_be_envoyes = df_plan["BE_Numero"].nunique() if df_plan is not None and not df_plan.empty else 0
    nb_vols = 0
    if df_plan is not None and not df_plan.empty:
        nb_vols = len(df_plan[["Date_Vol", "Numero_Vol"]].drop_duplicates())

    # Recalcule le dénominateur des bénévoles disponibles uniquement sur la semaine courante
    def _recalc_benev_dispo():
        s_dt = start_dt
        e_dt = end_dt
        if df_plan is not None and not df_plan.empty:
            dates_plan = coerce_datetime(df_plan["Date_Vol"], errors="coerce")
            dates_plan = dates_plan.dropna()
            if not dates_plan.empty:
                s_dt = dates_plan.min()
                e_dt = dates_plan.max()
        return count_benevoles_with_dispo(df_dispo, s_dt, e_dt)[0]

    def _col_sum(df_src):
        if df_src is None or df_src.empty:
            return 0
        vals = []
        for _, r in df_src.iterrows():
            for key in ["BE_Nb_Colis", "BE_Nb_Colis_MAG", "Nb_Colis"]:
                v = r.get(key, 0)
                if pd.notna(v):
                    vals.append(float(v))
                    break
                vals.append(0)
        return round(sum(vals))

    nb_colis_total = _col_sum(df_be)
    nb_colis_expedies = _col_sum(df_plan)

    benev_used = 0
    if df_plan is not None and not df_plan.empty and "Benevole" in df_plan.columns:
        benev_used = df_plan["Benevole"].dropna().astype(str).str.strip().replace("", pd.NA).dropna().nunique()

    benev_dispo = _recalc_benev_dispo()
    taux_colis = round(nb_colis_expedies / nb_colis_total * 100, 1) if nb_colis_total else 0

    status_label = stats.get("status", "N/A")
    if df_plan is not None and not df_plan.empty and df_plan.get("_MANUEL", pd.Series(dtype=bool)).any():
        status_label = f"{status_label} (ajusté)"

    return {
        "status": status_label,
        "nb_be_envoyes": nb_be_envoyes,
        "nb_be_total": nb_be_total,
        "nb_vols": nb_vols,
        "nb_colis_expedies": nb_colis_expedies,
        "nb_colis_total": nb_colis_total,
        "taux_colis": taux_colis,
        "benev_used": benev_used,
        "benev_dispo": benev_dispo,
    }


def _recompute_all_tables(
    df_plan: pd.DataFrame,
    *,
    df_be: pd.DataFrame,
    df_vols: pd.DataFrame,
    df_paramdest: pd.DataFrame,
    df_dispo: pd.DataFrame,
    df_parambenev: pd.DataFrame,
    start_dt,
    end_dt,
):
    return (
        _recompute_bilan(
            df_plan,
            df_be_src=df_be,
            df_vols_src=df_vols,
            df_dispo_src=df_dispo,
            start_dt=start_dt,
            end_dt=end_dt,
        ),
        _recompute_vols(df_plan),
        _recompute_benev(df_plan),
        _recompute_dest_stats(
            df_plan,
            df_vols_src=df_vols,
            df_paramdest=df_paramdest,
            start_dt=start_dt,
            end_dt=end_dt,
        ),
        _recompute_be_non_planifies(df_plan, df_be),
        _recompute_bilan_benevoles(
            df_plan,
            df_dispo,
            df_parambenev=df_parambenev,
            start_dt=start_dt,
            end_dt=end_dt,
        ),
    )


def _compute_week_year(df_plan: pd.DataFrame, *, current_week, current_year):
    if current_week and current_year:
        return current_week, current_year
    if df_plan is not None and not df_plan.empty:
        first_date = coerce_datetime(df_plan["Date_Vol"], errors="coerce", dayfirst=True).dropna()
        if not first_date.empty:
            iso = first_date.iloc[0].isocalendar()
            return int(iso.week), int(iso.year)
    # Fallback : semaine courante
    today_iso = pd.Timestamp.today().isocalendar()
    return int(today_iso.week), int(today_iso.year)


def _clean_for_excel(df: pd.DataFrame | None) -> pd.DataFrame | None:
    if df is None or getattr(df, "empty", True):
        return df
    clean = df.copy()
    clean = clean.astype(object)
    clean = clean.where(pd.notna(clean), None)
    return clean


def _open_file(path_obj):
    import os
    import platform
    import subprocess

    if path_obj is None:
        return
    try:
        if platform.system() == "Darwin":
            subprocess.Popen(["open", str(path_obj)])
        elif platform.system() == "Windows":
            startfile = getattr(os, "startfile", None)
            if callable(startfile):
                startfile(str(path_obj))
        else:
            subprocess.Popen(["xdg-open", str(path_obj)])
    except (OSError, ValueError):
        pass


def _ensure_simulation_session_state() -> None:
    if "sim_results" not in st.session_state:
        st.session_state.sim_results = None
    if "sim_active_mode" not in st.session_state:
        st.session_state.sim_active_mode = "colis"


def _build_mode_selector_data(modes: dict[str, dict[str, Any]]) -> tuple[list[str], list[str]]:
    mode_labels: list[str] = []
    mode_values: list[str] = []
    for key, res in modes.items():
        stats_mode = res.get("statistiques", {})
        label = "Priorité Colis" if key == "colis" else "Priorité Bénévole"
        extra = f" — {stats_mode.get('nb_colis_expedies', 0)} colis / {stats_mode.get('nb_benevoles_mobilises', 0)} bénév"
        mode_labels.append(f"{label}{extra}")
        mode_values.append(key)
    return mode_labels, mode_values


def _filter_vols_for_export(
    df_vols_all: pd.DataFrame,
    *,
    state: Any,
    df_export: pd.DataFrame,
) -> pd.DataFrame:
    vols_filtered = df_vols_all.copy()
    try:
        start_dt = coerce_datetime(state.api_start_date) if state.api_start_date else None
        end_dt = coerce_datetime(state.api_end_date) if state.api_end_date else None
        if start_dt is None or end_dt is None:
            if df_export is not None and not df_export.empty:
                dates_plan = coerce_datetime(
                    df_export["Date_Vol"],
                    errors="coerce",
                    dayfirst=True,
                ).dropna()
                if not dates_plan.empty:
                    start_dt = dates_plan.min()
                    end_dt = dates_plan.max()
        if start_dt is not None and end_dt is not None and "Date_Vol" in vols_filtered.columns:
            vols_filtered["Date_dt"] = parse_date_series(vols_filtered["Date_Vol"])
            vols_filtered = vols_filtered[
                (vols_filtered["Date_dt"] >= start_dt) & (vols_filtered["Date_dt"] <= end_dt)
            ]
            vols_filtered = vols_filtered.drop(columns=["Date_dt"], errors="ignore")
    except (KeyError, TypeError, ValueError):
        pass
    return vols_filtered


def _resolve_tdb_write_path(*, state: Any, write_source_excel: bool) -> Path:
    paths = get_excel_source_paths(state)
    tdb_write_path = paths.tableau_de_bord
    if write_source_excel and not is_graph_onedrive():
        tdb_src = get_tableau_de_bord_src()
        if tdb_src.exists():
            tdb_write_path = tdb_src
    return tdb_write_path


def _export_simulation_excel(
    *,
    current_plan: pd.DataFrame,
    state: Any,
    df_paramdest: pd.DataFrame,
    df_vols_all: pd.DataFrame,
    df_dispo: pd.DataFrame,
    df_parambenev: pd.DataFrame,
    write_source_excel: bool,
    increment_version: bool,
):
    from asf_app.services.export_service import export_planning_excel

    df_with_status = sort_planning_df(current_plan)
    week, year = _compute_week_year(
        current_plan,
        current_week=state.current_week,
        current_year=state.current_year,
    )
    df_export = pd.DataFrame(df_with_status).copy()
    df_export = df_export.drop(columns=["_MANUEL", "_STATUS"], errors="ignore")
    df_export = build_export_view(
        df_export,
        df_paramdest=df_paramdest,
        df_vols=df_vols_all,
    )
    df_export["Ville"] = df_export.get("Dest_Ville", "")

    try:
        df_export = df_export.sort_values(
            by=["Date_Vol", "Heure_Vol"],
            kind="mergesort",
        ).reset_index(drop=True)
    except (KeyError, TypeError, ValueError):
        pass

    df_export = _clean_for_excel(df_export)
    vols_filtered = _filter_vols_for_export(df_vols_all, state=state, df_export=df_export)
    vols_clean = _clean_for_excel(vols_filtered)
    dispo_clean = _clean_for_excel(df_dispo)
    paths = get_excel_source_paths(state)
    tdb_write_path = _resolve_tdb_write_path(state=state, write_source_excel=write_source_excel)
    return export_planning_excel(
        df_export,
        week,
        year,
        df_vols=vols_clean,
        df_parambenev=df_parambenev,
        df_dispos=dispo_clean,
        df_paramdest=df_paramdest,
        create_tables=False,  # éviter les tables qui peuvent corrompre l'export en V2
        write_source_excel=write_source_excel,
        increment_version=increment_version,
        benev_path=paths.planning_benevoles,
        tdb_source_path=tdb_write_path,
    )


def _compute_week_bounds(*, api_start_date, api_end_date, planning_df: pd.DataFrame | None):
    if api_start_date and api_end_date:
        return coerce_datetime(api_start_date), coerce_datetime(api_end_date)
    if planning_df is not None and not planning_df.empty:
        dates = parse_date_series(planning_df["Date_Vol"]).dropna()
        if not dates.empty:
            return dates.min(), dates.max()
    return None, None


def _time_from_str(val):
    import datetime as dt

    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    if str(val).strip() == "":
        return None
    if isinstance(val, dt.time):
        return val
    try:
        sval = str(val).replace("h", ":")
        return coerce_datetime(sval, errors="coerce").time()
    except (AttributeError, TypeError, ValueError):
        return None


def _build_be_option_label(row: pd.Series, planned_set: set[str]) -> str:
    dest = str(row.get("Destination", "")).upper()
    be_num = str(row.get("BE_Numero", ""))
    nb_colis = row.get("BE_Nb_Colis", row.get("BE_Nb_Colis_MAG", ""))
    nb_colis = int(nb_colis) if pd.notna(nb_colis) else ""
    type_colis = str(row.get("BE_Type", "")).upper()
    status = "déjà au planning" if be_num in planned_set else "non planifié"
    date_str = str(row.get("Date_Vol", "") or "")
    return format_be_label(dest, be_num, nb_colis, type_colis, status, date_str)


def _build_be_options(df_be: pd.DataFrame, planned_set: set[str]) -> list[tuple[str, str, str, pd.Series]]:
    options = []
    for _, row in df_be.iterrows():
        options.append(
            (
                str(row.get("Destination", "")).upper(),
                str(row.get("BE_Numero", "")),
                _build_be_option_label(row, planned_set),
                row,
            )
        )
    return sorted(options, key=lambda x: (x[0], x[1]))


def _filter_vols_for_selection(
    df_vols_all: pd.DataFrame,
    *,
    code_iata_be: str,
    api_start_date,
    api_end_date,
) -> pd.DataFrame:
    df_vols = df_vols_all.copy()
    try:
        if api_start_date and api_end_date:
            start_dt = coerce_datetime(api_start_date)
            end_dt = coerce_datetime(api_end_date)
            df_vols["Date_dt"] = parse_date_series(df_vols["Date_Vol"])
            df_vols = df_vols[(df_vols["Date_dt"] >= start_dt) & (df_vols["Date_dt"] <= end_dt)]
    except (KeyError, TypeError, ValueError):
        pass
    df_vols["Dest_UP"] = df_vols.get("IATA", "").astype(str).str.upper()
    df_vols["Destination_UP"] = df_vols.get("Destination", "").astype(str).str.upper()
    df_vols["Routing_UP"] = df_vols.get("Routing", df_vols.get("Routing_Str", "")).astype(str).str.upper()
    mask_dest = (
        df_vols["Dest_UP"].str.contains(code_iata_be, na=False)
        | df_vols["Destination_UP"].str.contains(code_iata_be, na=False)
        | df_vols["Routing_UP"].str.contains(code_iata_be, na=False)
    )
    return df_vols[mask_dest] if mask_dest.any() else df_vols


def _build_vol_selector_data(
    df_vols_filt: pd.DataFrame,
    plan_df: pd.DataFrame,
    *,
    code_iata_be: str,
    planned_row: pd.Series | None,
) -> tuple[list[str], list[tuple[str, str, str]], int]:
    plan_numero = (
        plan_df["Numero_Vol"].astype(str)
        if "Numero_Vol" in plan_df.columns
        else pd.Series("", index=plan_df.index, dtype=str)
    )
    plan_date = (
        plan_df["Date_Vol"].astype(str)
        if "Date_Vol" in plan_df.columns
        else pd.Series("", index=plan_df.index, dtype=str)
    )

    selected_rows_by_flight: dict[tuple[str, str, str], tuple[int, pd.Series]] = {}
    flight_order: list[tuple[str, str, str]] = []
    for _, row in df_vols_filt.iterrows():
        vol_num = str(row.get("Numero_Vol", "")).strip()
        date_raw = str(row.get("Date_Vol", "")).strip()
        heure_raw = str(row.get("Heure_Vol", "")).strip()
        flight_key = (date_raw, vol_num, heure_raw)

        code_iata_up = str(code_iata_be or "").strip().upper()
        iata_up = str(row.get("IATA", "")).strip().upper()
        dest_up = str(row.get("Destination", "")).strip().upper()
        is_direct_match = bool(code_iata_up) and (iata_up == code_iata_up or dest_up == code_iata_up)
        match_score = 0 if is_direct_match else 1

        current_choice = selected_rows_by_flight.get(flight_key)
        if current_choice is None:
            selected_rows_by_flight[flight_key] = (match_score, row)
            flight_order.append(flight_key)
        elif match_score < current_choice[0]:
            selected_rows_by_flight[flight_key] = (match_score, row)

    vol_options = []
    for flight_key in flight_order:
        _, row = selected_rows_by_flight[flight_key]
        vol_num = row.get("Numero_Vol", "")
        date_raw = row.get("Date_Vol", "")
        heure_raw = row.get("Heure_Vol", "")
        already = ((plan_numero == str(vol_num)) & (plan_date == str(date_raw))).any()
        status = "déjà utilisé" if already else "disponible"
        date_dt = None
        try:
            date_dt = parse_date_series(pd.Series([date_raw])).iloc[0]
        except (IndexError, TypeError, ValueError):
            pass
        routing_lbl = str(row.get("Routing", "")) or ""
        routing_up = routing_lbl.upper()
        dest_up = str(row.get("Destination", "")).upper()
        iata_raw = str(row.get("IATA", "")).upper()
        if code_iata_be and (
            code_iata_be in routing_up
            or code_iata_be in dest_up
            or code_iata_be in iata_raw
        ):
            iata_label = code_iata_be
        else:
            iata_label = iata_raw or dest_up
        label = format_vol_label(
            date_dt if date_dt is not None else date_raw,
            iata_label,
            vol_num,
            heure_raw,
            routing_lbl,
            status,
        )
        vol_options.append((label, (date_raw, vol_num, heure_raw)))

    if not vol_options:
        vol_options = [("Aucun vol pour cette destination", ("", "", ""))]
    vol_labels = [v[0] for v in vol_options]
    vol_values = [v[1] for v in vol_options]

    sel_vol_idx = 0
    if planned_row is not None:
        planned_date = str(planned_row.get("Date_Vol", ""))
        planned_vol = str(planned_row.get("Numero_Vol", ""))
        for idx, (d_raw, vnum, _) in enumerate(vol_values):
            if str(d_raw) == planned_date and str(vnum) == planned_vol:
                sel_vol_idx = idx
                break
    else:
        message = "BE absent du planning, pour l'ajouter choisissez un vol et un bénévole"
        vol_labels = [message] + vol_labels
        vol_values = [("", "", "")] + vol_values
        sel_vol_idx = 0
    return vol_labels, vol_values, sel_vol_idx


def _compute_bene_status(
    *,
    name: str,
    benev_existing: pd.DataFrame,
    df_dispo: pd.DataFrame,
    vol_choice_val,
    date_choice,
    heure_choice,
) -> str:
    already = (
        (benev_existing.get("Benevole", "").astype(str) == name)
        & (benev_existing.get("Numero_Vol", "").astype(str) == str(vol_choice_val))
        & (benev_existing.get("Date_Vol", "").astype(str) == str(date_choice))
    ).any()
    if already:
        return "Occupé"

    try:
        d = coerce_datetime(date_choice, dayfirst=True, errors="coerce").date()
        t = _time_from_str(heure_choice)
    except (AttributeError, TypeError, ValueError):
        return "Inconnu"
    rows = df_dispo
    if "Date_dt" in df_dispo.columns:
        try:
            dates_dt = parse_date_series(df_dispo["Date_dt"])
            rows = df_dispo[dates_dt.dt.date == d]
        except (KeyError, TypeError, ValueError):
            rows = df_dispo
    rows = rows[rows["Benevole"].astype(str) == name]
    if rows.empty:
        return "Inconnu"
    ok = False
    for _, row in rows.iterrows():
        arr = row.get("Heure_Arrivee_time") or row.get("Heure_Arrivee_time")
        dep = row.get("Heure_Depart_time") or row.get("Heure_Depart_time")
        arr = arr if isinstance(arr, type(t)) else _time_from_str(arr)
        dep = dep if isinstance(dep, type(t)) else _time_from_str(dep)
        if arr and dep and t:
            if arr <= t <= dep:
                ok = True
                break
    return "Disponible" if ok else "Occupé"


def _build_bene_selector_data(
    *,
    df_parambenev: pd.DataFrame,
    df_dispo: pd.DataFrame,
    benev_existing: pd.DataFrame,
    vol_choice_val,
    date_choice,
    heure_choice,
    planned_row: pd.Series | None,
) -> tuple[list[str], list[str], int]:
    bene_options = []
    for _, row in df_parambenev.iterrows():
        name = str(row.get("Benevole", "")).strip()
        bene_options.append(name)
    bene_options = sorted(set(bene_options))

    bene_labels = []
    for name in bene_options:
        status = _compute_bene_status(
            name=name,
            benev_existing=benev_existing,
            df_dispo=df_dispo,
            vol_choice_val=vol_choice_val,
            date_choice=date_choice,
            heure_choice=heure_choice,
        )
        bene_labels.append(f"{name} — {status}")
    bene_values = bene_options

    if planned_row is None:
        message = "BE absent du planning, pour l'ajouter choisissez un vol et un bénévole"
        bene_labels = [message] + bene_labels
        bene_values = [""] + bene_values

    sel_bene_idx = 0
    if planned_row is not None:
        planned_bene = str(planned_row.get("Benevole", "")).strip()
        for idx, name in enumerate(bene_values):
            if str(name).strip() == planned_bene:
                sel_bene_idx = idx
                break
    return bene_labels, bene_values, sel_bene_idx


def _build_manual_row_data(
    *,
    be_num: str,
    code_iata_be: str,
    date_choice,
    heure_choice,
    vol_choice_val,
    be_row: pd.Series,
    benev_val: str,
    df_parambenev: pd.DataFrame,
) -> dict[str, object]:
    bene_row = df_parambenev[df_parambenev["Benevole"].astype(str) == str(benev_val)]
    bene_id = bene_row["ID"].iloc[0] if not bene_row.empty else ""
    bene_tel = bene_row["Telephone"].iloc[0] if not bene_row.empty else ""
    return {
        "BE_Numero": be_num,
        "Destination": code_iata_be,
        "Date_Vol": date_choice,
        "Heure_Vol": heure_choice,
        "Numero_Vol": vol_choice_val,
        "BE_Nb_Colis": be_row.get("BE_Nb_Colis", ""),
        "BE_Nb_Equiv": be_row.get("Equiv_Colis", be_row.get("BE_Nb_Equiv", "")),
        "BE_Expediteur": be_row.get("BE_Expediteur", ""),
        "BE_Destinataire": be_row.get("BE_Destinataire", ""),
        "BE_Type": be_row.get("BE_Type", ""),
        "Benevole": benev_val,
        "ID": bene_id,
        "Telephone": bene_tel,
        "_MANUEL": True,
    }


def _apply_manual_assignment(
    plan_df: pd.DataFrame,
    *,
    be_num: str,
    row_data: dict[str, object],
) -> pd.DataFrame:
    df_new = plan_df.copy()
    mask = df_new["BE_Numero"].astype(str) == str(be_num)
    if mask.any():
        df_new.loc[mask, row_data.keys()] = list(row_data.values())
    else:
        df_new = pd.concat([df_new, pd.DataFrame([row_data])], ignore_index=True)
    return normalize_planning_df(df_new)


def _delete_manual_assignment(plan_df: pd.DataFrame, *, be_num: str) -> pd.DataFrame:
    df_new = plan_df[plan_df["BE_Numero"].astype(str) != str(be_num)].copy()
    return normalize_planning_df(df_new)


def _normalize_sort_plan(plan_df: pd.DataFrame) -> pd.DataFrame:
    return _sort_planning(normalize_planning_df(plan_df))


def render_tab_simulation():
    # État global (dates de la semaine sélectionnée, chemins TMP, etc.)
    state = get_state()

    st.title("🧪 Création automatisée du planning")
    selected_version = get_solver_version(st.session_state.get("solver_version"))
    st.markdown("Choissiez la version du moteur dans l'onglet Paramètres > Paramoteur > Version solver OR-Tools")
    st.markdown(f"Version sélectionnée : {selected_version}")

    st.markdown("### Paramètres")
    col_timeout, col_verbose = st.columns([2, 1])
    with col_timeout:
        timeout = st.number_input("Temps maximum (secondes)", min_value=30, max_value=900, value=180, step=30)
    with col_verbose:
        verbose = st.checkbox("Log console détaillé", value=True)

    _ensure_simulation_session_state()

    if st.button("Générer le planning", type="primary"):
        with st.spinner("Optimisation OR-Tools en cours…"):
            paths = get_excel_source_paths(state)
            data_source = ExcelDataSource(paths=paths)
            dual_res = run_ortools_simulation_dual(
                timeout_seconds=int(timeout),
                planifiables_only=True,
                verbose=verbose,
                data_source=data_source,
                solver_version=st.session_state.get("solver_version"),
            )
            st.session_state.sim_results = dual_res.get("modes")
            st.session_state.sim_active_mode = dual_res.get("selected", "colis")
            st.session_state["sim_original_df"] = {}

    modes = st.session_state.sim_results
    if not modes:
        st.info("Aucune simulation lancée pour l'instant.")
        return

    # Choix du mode affiché
    mode_labels, mode_values = _build_mode_selector_data(modes)
    current_mode = st.radio(
        "Sélectionner le planning affiché",
        options=mode_values,
        format_func=lambda m: mode_labels[mode_values.index(m)],
        index=mode_values.index(st.session_state.sim_active_mode)
        if st.session_state.sim_active_mode in mode_values
        else 0,
        horizontal=True,
    )
    st.session_state.sim_active_mode = current_mode

    result = modes.get(current_mode, {})
    stats = result.get("statistiques", {})
    st.markdown("### Résumé")
    resume_container = st.container()

    # Disponibilités bénévoles sur la semaine
    start_dt, end_dt = _compute_week_bounds(
        api_start_date=state.api_start_date,
        api_end_date=state.api_end_date,
        planning_df=result.get("planning_df"),
    )

    plan_df = normalize_planning_df(result.get("planning_df"))
    if plan_df is None or plan_df.empty:
        st.info("Aucun planning simulé à modifier.")
        return

    # Chargements nécessaires pour les statuts
    from loaders.load_benevoles import load_benevoles
    from loaders.load_params import get_param_benev, get_param_dest
    from loaders.load_shipments import load_shipments_df
    from loaders.load_vols import load_vols_df

    paths = get_excel_source_paths(state)
    df_be = load_shipments_df(planifiables_only=True, tdb_path=paths.tableau_de_bord)
    df_vols_all = load_vols_df(vols_path=paths.vols, param_dest_df=state.df_param_dest)
    df_dispo = load_benevoles(planning_path=paths.planning_benevoles)
    df_paramdest = get_param_dest()
    df_parambenev = get_param_benev()

    # Disponibilités bénévoles uniques sur la semaine
    benev_dispo_total, start_dt, end_dt = count_benevoles_with_dispo(df_dispo, start_dt, end_dt)

    # Carte IATA -> Ville (pour afficher Destination en clair)
    dest_city_map, city_to_iata_map = build_iata_city_maps(df_paramdest)

    if "_MANUEL" not in plan_df.columns:
        plan_df["_MANUEL"] = False
    # Garder une copie du planning initial pour les diffs export (par mode)
    if "sim_original_df" not in st.session_state:
        st.session_state["sim_original_df"] = {}
    if current_mode not in st.session_state["sim_original_df"]:
        st.session_state["sim_original_df"][current_mode] = plan_df.copy()
    # Trie initial pour affichage cohérent
    plan_df = sort_planning_df(plan_df)
    # On conserve le tri dans le state pour l'affichage final
    st.session_state.sim_results[current_mode]["planning_df"] = plan_df

    # ------------------------------------------------------------------
    # Edition manuelle du planning de simulation (sélecteurs alignés onglet Planning)
    # ------------------------------------------------------------------
    st.markdown("### ✏️ Ajuster le planning simulé")

    # BE options
    planned_set = set(plan_df["BE_Numero"].astype(str))
    be_options = _build_be_options(df_be, planned_set)
    if not be_options:
        st.warning("Aucun BE statut D chargé.")
        return
    be_labels = [b[2] for b in be_options]
    be_values = [b[1] for b in be_options]
    selected_idx = 0
    selected_be_label = st.selectbox("Sélectionner un BE", options=be_labels, index=selected_idx)
    idx_sel = be_labels.index(selected_be_label)
    be_num = be_values[idx_sel]
    be_row = be_options[idx_sel][3]
    # Ligne planifiée existante si déjà au planning
    planned_row = plan_df[plan_df["BE_Numero"].astype(str) == str(be_num)]
    planned_row = planned_row.iloc[0] if not planned_row.empty else None

    # Vols filtrés par destination du BE
    code_iata_be = str(be_row.get("Destination", "")).strip().upper()
    df_vols_filt = _filter_vols_for_selection(
        df_vols_all,
        code_iata_be=code_iata_be,
        api_start_date=state.api_start_date,
        api_end_date=state.api_end_date,
    )

    vol_labels, vol_values, sel_vol_idx = _build_vol_selector_data(
        df_vols_filt,
        plan_df,
        code_iata_be=code_iata_be,
        planned_row=planned_row,
    )
    chosen_vol_label = st.selectbox("Sélectionner un vol", options=vol_labels, index=sel_vol_idx)
    date_choice, vol_choice_val, heure_choice = vol_values[vol_labels.index(chosen_vol_label)]

    # Bénévoles : statut dispo/occupé/inconnu
    benev_existing = plan_df.copy()
    bene_labels, bene_values, sel_bene_idx = _build_bene_selector_data(
        df_parambenev=df_parambenev,
        df_dispo=df_dispo,
        benev_existing=benev_existing,
        vol_choice_val=vol_choice_val,
        date_choice=date_choice,
        heure_choice=heure_choice,
        planned_row=planned_row,
    )
    chosen_bene_label = st.selectbox("Affecter un bénévole", options=bene_labels or [""], index=sel_bene_idx)
    benev_val = bene_values[bene_labels.index(chosen_bene_label)] if bene_labels else ""

    # Actions
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        if st.button("Ajouter / Mettre à jour", type="primary"):
            row_data = _build_manual_row_data(
                be_num=be_num,
                code_iata_be=code_iata_be,
                date_choice=date_choice,
                heure_choice=heure_choice,
                vol_choice_val=vol_choice_val,
                be_row=be_row,
                benev_val=benev_val,
                df_parambenev=df_parambenev,
            )
            df_new = _apply_manual_assignment(plan_df, be_num=be_num, row_data=row_data)
            st.session_state.sim_results[current_mode]["planning_df"] = _sort_planning(df_new)
            st.success("Planning simulation mis à jour.")
    with col_d2:
        if st.button("Supprimer l'expédition sélectionnée", type="secondary"):
            df_new = _delete_manual_assignment(plan_df, be_num=be_num)
            st.session_state.sim_results[current_mode]["planning_df"] = _sort_planning(df_new)
            st.success("Expédition supprimée du planning simulé.")

    # Re-trier et recalculer tous les tableaux dès cette passe pour éviter le décalage d'une interaction
    plan_df = _normalize_sort_plan(st.session_state.sim_results[current_mode]["planning_df"])
    st.session_state.sim_results[current_mode]["planning_df"] = plan_df

    (
        bilan_df,
        vols_df,
        benev_df,
        dest_stats,
        be_non_planifies,
        bilan_benevoles,
    ) = _recompute_all_tables(
        plan_df,
        df_be=df_be,
        df_vols=df_vols_all,
        df_paramdest=df_paramdest,
        df_dispo=df_dispo,
        df_parambenev=df_parambenev,
        start_dt=start_dt,
        end_dt=end_dt,
    )

    # Mettre à jour le bloc résumé avec les données recalculées
    resume_vals = _compute_resume_numbers(
        plan_df,
        df_be=df_be,
        df_dispo=df_dispo,
        start_dt=start_dt,
        end_dt=end_dt,
        stats=stats,
    )
    with resume_container:
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Statut", resume_vals["status"])
        c2.metric("BE planifiés", f"{resume_vals['nb_be_envoyes']} / {resume_vals['nb_be_total']}")
        c3.metric("Vols utilisés", resume_vals["nb_vols"])
        c4.metric("Bénévoles mobilisés", f"{resume_vals['benev_used']} / {resume_vals['benev_dispo']}")
        c5.metric(
            "Colis expédiés",
            f"{resume_vals['nb_colis_expedies']} / {resume_vals['nb_colis_total']}",
            f"{resume_vals['taux_colis']}%",
        )

    # Export Excel (bouton sous le tableau de planning)

    col_export, col_write, col_version = st.columns([1, 2, 2])
    with col_write:
        write_source_excel = st.toggle(
            "Activer / Désactiver l'écriture sur le excel source",
            value=True,
            key="sim_write_source_excel",
        )
    with col_version:
        increment_version = st.toggle(
            "Incrémenter le numéro de version",
            value=True,
            key="sim_increment_planning_version",
        )
    with col_export:
        if st.button("📤 Exporter le planning simulé (Excel)", type="primary"):
            try:
                current_plan = st.session_state.sim_results.get(current_mode, {}).get("planning_df", plan_df)
                export_result = _export_simulation_excel(
                    current_plan=current_plan,
                    state=state,
                    df_paramdest=df_paramdest,
                    df_vols_all=df_vols_all,
                    df_dispo=df_dispo,
                    df_parambenev=df_parambenev,
                    write_source_excel=write_source_excel,
                    increment_version=increment_version,
                )
                if write_source_excel:
                    st.session_state["mag_central_write_method"] = export_result.mag_write_method
                else:
                    st.session_state.pop("mag_central_write_method", None)
                for msg in export_result.warnings:
                    st.warning(msg)

                out_path = Path(export_result.output_path)
                st.success(f"Planning simulé exporté : {out_path}")
                from asf_app.ui.ui_planning.utils import show_mag_central_status
                show_mag_central_status()
                _open_file(out_path)
                # Export PDF 1ère feuille + ouvrir le PDF
                try:
                    from utils.export_pdf import export_first_sheet_to_pdf
                    pdf_path = export_first_sheet_to_pdf(out_path)
                    st.success(f"PDF généré : {pdf_path}")
                    _open_file(pdf_path)
                except (ImportError, OSError, RuntimeError, TypeError, ValueError) as e_pdf:
                    st.warning(f"PDF non généré automatiquement : {e_pdf}")
            except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError) as e:
                st.error(f"Erreur lors de l'export : {e}")

    st.dataframe(_style_manual_df(plan_df), height=400, width="stretch", hide_index=True)

    with st.expander("Bilans détaillés (simulation)", expanded=False):
        st.markdown("**Bilan des bénévoles**")
        st.dataframe(_style_manual_df(bilan_benevoles), width="stretch", hide_index=True)

        st.markdown("**Bilan des expéditions**")
        st.dataframe(_style_manual_df(bilan_df), width="stretch", hide_index=True)

        st.markdown("**Bilan des vols**")
        st.dataframe(_style_manual_df(vols_df), width="stretch", hide_index=True)

        st.markdown("**Bilan par destination**")
        st.dataframe(_style_manual_df(dest_stats), width="stretch", hide_index=True)

        st.markdown("**Planning Bénévoles**")
        st.dataframe(_style_manual_df(benev_df), width="stretch", hide_index=True)
