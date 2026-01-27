import pandas as pd
from typing import Optional, Tuple

from utils.datetime_utils import coerce_datetime, parse_date_series, parse_time_series


def count_benevoles_with_dispo(
    df_dispo: pd.DataFrame,
    start_dt: Optional[pd.Timestamp] = None,
    end_dt: Optional[pd.Timestamp] = None,
) -> Tuple[int, Optional[pd.Timestamp], Optional[pd.Timestamp]]:
    """
    Compte les bénévoles ayant au moins une disponibilité (arrivée + départ renseignés)
    entre start_dt et end_dt. Si l'intervalle n'est pas fourni, utilise min/max des dates dispo.
    Retourne (nb_benevoles, start_dt, end_dt) pour réutilisation.
    """
    if df_dispo is None or df_dispo.empty:
        return 0, start_dt, end_dt

    df_tmp = df_dispo.copy()
    if "Date_dt" in df_tmp.columns:
        df_tmp["_Date_dt"] = coerce_datetime(df_tmp["Date_dt"], errors="coerce")
    else:
        df_tmp["_Date_dt"] = parse_date_series(df_tmp.get("Date", pd.Series(dtype=object)))

    if not df_tmp["_Date_dt"].notna().any():
        return 0, start_dt, end_dt

    if start_dt is None or end_dt is None:
        dates_dispo = df_tmp["_Date_dt"].dropna()
        if not dates_dispo.empty:
            start_dt = dates_dispo.min() if start_dt is None else start_dt
            end_dt = dates_dispo.max() if end_dt is None else end_dt

    if start_dt is None or end_dt is None:
        return 0, start_dt, end_dt

    mask_week = (df_tmp["_Date_dt"] >= start_dt) & (df_tmp["_Date_dt"] <= end_dt)
    df_tmp = df_tmp.loc[mask_week]

    # Filtrer uniquement les lignes avec une plage horaire définie (arrivée & départ non vides)
    arr_col = "Heure_Arrivee_time" if "Heure_Arrivee_time" in df_tmp.columns else "Heure_Arrivee"
    dep_col = "Heure_Depart_time" if "Heure_Depart_time" in df_tmp.columns else "Heure_Depart"
    # Parse heures sans warning et support des time() déjà parsés
    arr_parsed = parse_time_series(df_tmp.get(arr_col, pd.Series(dtype=object)))
    dep_parsed = parse_time_series(df_tmp.get(dep_col, pd.Series(dtype=object)))
    df_tmp["_ARR_T"] = arr_parsed.dt.time
    df_tmp["_DEP_T"] = dep_parsed.dt.time
    df_tmp = df_tmp[df_tmp["_ARR_T"].notna() & df_tmp["_DEP_T"].notna()]

    benev_count = (
        df_tmp["Benevole"]
        .astype(str)
        .str.strip()
        .replace("", pd.NA)
        .dropna()
        .nunique()
    )

    return int(benev_count), start_dt, end_dt
