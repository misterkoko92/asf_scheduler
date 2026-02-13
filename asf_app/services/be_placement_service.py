# asf_app/services/be_placement_service.py
# -*- coding: utf-8 -*-

import datetime
from typing import Optional

import pandas as pd

from scheduler import config
from scheduler.planning_schema import normalize_planning_df
from utils.datetime_utils import (
    format_time_value,
    parse_date_value_as_date,
    parse_time_value_as_time,
)


class BEPlacementError(Exception):
    """Exception métier pour un ajout de BE impossible ou incohérent."""
    pass


# =====================================================================
# NORMALISATION INTERNE
# =====================================================================

def _to_date(x):
    """Conversion robuste en date."""
    return parse_date_value_as_date(x)


def _to_time(x):
    """Conversion robuste en time (HH:MM)."""
    return parse_time_value_as_time(x)


def _norm_str(x):
    """Nettoie et retourne une string uniforme."""
    if x is None:
        return ""
    try:
        return str(x).strip()
    except (TypeError, ValueError, RuntimeError):
        return ""


# =====================================================================
# EXTRACTION DES VOLs
# =====================================================================

def _extract_flights_from_planning(planning_df: pd.DataFrame) -> pd.DataFrame:
    """
    Regroupe le planning par vol :
      - Date_Vol (datetime.date)
      - Heure_Vol (string HH:MM)
      - Numero_Vol (string)
      - Destination (string)
      - nb_be : count
      - total_equiv : somme BE_Nb_Equiv
      - benevoles : set
    """
    if planning_df is None or planning_df.empty:
        return pd.DataFrame(
            columns=[
                "Date_Vol", "Heure_Vol", "Numero_Vol", "Destination",
                "nb_be", "total_equiv", "benevoles"
            ]
        )

    df = planning_df.copy()

    # Normalisation des colonnes
    df["Date_Vol"] = df["Date_Vol"].apply(_to_date)
    df["Heure_Vol"] = df["Heure_Vol"].apply(_norm_str)
    df["BE_Numero"] = df["BE_Numero"].apply(_norm_str)
    df["Benevole"] = df["Benevole"].apply(_norm_str)
    df["Numero_Vol"] = df.get("Numero_Vol", "").apply(_norm_str)

    # Poids équivalent
    if "BE_Nb_Equiv" in df.columns:
        df["__EQUIV__"] = df["BE_Nb_Equiv"].fillna(df["BE_Nb_Colis"])
    else:
        df["__EQUIV__"] = df["BE_Nb_Colis"]

    # Agrégation
    grouped = df.groupby(
        ["Date_Vol", "Heure_Vol", "Numero_Vol", "Destination"],
        dropna=False
    ).agg(
        nb_be=("BE_Numero", lambda s: s.apply(_norm_str).ne("").sum()),
        total_equiv=("__EQUIV__", "sum"),
        benevoles=("Benevole", lambda s: {b for b in s.dropna().unique() if _norm_str(b)}),
    ).reset_index()

    return grouped


# =====================================================================
# CAPACITÉ DE VOL
# =====================================================================

def _flight_capacity_ok(row: pd.Series, nb_colis: int) -> bool:
    """
    Vérifie qu'on ne dépasse pas :
      - MAX_BE_PER_FLIGHT
      - MAX_EQUIV_PER_VOLUNTEER
      - MAX_CAPACITE_PAR_VOL (optionnel)
    """
    max_be = int(config.MAX_BE_PER_FLIGHT)
    max_equiv_vol = int(config.MAX_EQUIV_PER_VOLUNTEER)
    max_cap_global = (
        None
        if config.MAX_CAPACITE_PAR_VOL in (None, "")
        else int(config.MAX_CAPACITE_PAR_VOL)
    )

    # 1) Trop de BE
    if row["nb_be"] >= max_be:
        return False

    # 2) Capacité globale (optionnelle)
    if max_cap_global is not None and row["total_equiv"] + nb_colis > max_cap_global:
        return False

    # 3) Capacité bénévole × équivalents
    benevoles = row["benevoles"] or set()
    if benevoles:
        capa = len(benevoles) * max_equiv_vol
        if row["total_equiv"] + nb_colis > capa:
            return False

    return True


# =====================================================================
# CHOIX DU VOL
# =====================================================================

def _choose_best_flight(candidates: pd.DataFrame, nb_colis: int) -> Optional[pd.Series]:
    """Choix du vol le moins chargé."""
    if candidates.empty:
        return None

    df = candidates.copy()
    df["score"] = df["total_equiv"] + df["nb_be"] * 10
    df = df.sort_values(["score", "Date_Vol", "Heure_Vol", "Numero_Vol"])
    return df.iloc[0]


# =====================================================================
# CHOIX BÉNÉVOLE
# =====================================================================

def _choose_best_benevole_on_flight(planning_df, date_vol, heure_str, vol, nb_colis):
    """
    Choix du bénévole le moins chargé parmi ceux déjà affectés au vol.
    Retourne "" si aucun bénévole n'est déjà présent.
    """
    df = planning_df.copy()
    df["Date_Vol"] = df["Date_Vol"].apply(_to_date)
    df["Heure_Vol"] = df["Heure_Vol"].apply(_norm_str)
    df["Benevole"] = df["Benevole"].apply(_norm_str)

    mask = (
        (df["Date_Vol"] == date_vol) &
        (df["Heure_Vol"] == heure_str) &
        (df["Numero_Vol"] == vol)
    )
    vol_df = df.loc[mask]

    # Bénévoles valides
    vol_df = vol_df[vol_df["Benevole"] != ""]
    if vol_df.empty:
        return ""

    # Poids
    if "BE_Nb_Equiv" in vol_df.columns:
        vol_df["__EQUIV__"] = vol_df["BE_Nb_Equiv"].fillna(vol_df["BE_Nb_Colis"])
    else:
        vol_df["__EQUIV__"] = vol_df["BE_Nb_Colis"]

    loads = vol_df.groupby("Benevole")["__EQUIV__"].sum()

    # Choix = bénévole qui ne dépasse pas → sinon plus léger malgré dépassement
    max_equiv = int(config.MAX_EQUIV_PER_VOLUNTEER)
    best = None
    best_key = None

    for benev, load in loads.items():
        overflow = (load + nb_colis) > max_equiv
        key = (overflow, load)
        if best_key is None or key < best_key:
            best_key = key
            best = benev

    return best or ""


# =====================================================================
# CONSTRUCTION DE LA LIGNE
# =====================================================================

def _build_new_row(be_num, nb_colis, dest, date_vol, heure_vol, vol, benevole):
    heure_str = format_time_value(heure_vol, fmt="%H:%M", default="")

    return {
        "Date_Vol": date_vol,
        "Heure_Vol": heure_str,
        "Numero_Vol": vol,
        "Destination": dest or "",
        "BE_Numero": be_num,
        "BE_Nb_Colis": nb_colis,
        "BE_Nb_Equiv": nb_colis,
        "Benevole": benevole,
    }


# =====================================================================
# MODES D’INSERTION
# =====================================================================

def place_be(planning_df, be_num, nb_colis, dest, date_vol, heure_vol, benevole):
    """
    Dispatch :
      1) BE seul              → AUTO
      2) BE + date            → SEMI-AUTO
      3) BE + bénévole        → FORCÉ
      4) BE + date + bénévole → MANUEL
    """
    be_num = _norm_str(be_num)
    dest = _norm_str(dest)
    benevole = _norm_str(benevole)

    has_be = be_num != ""
    has_date = isinstance(date_vol, datetime.date)
    has_benev = benevole != ""

    if not has_be:
        raise BEPlacementError("Impossible d'ajouter un BE sans numéro.")

    if has_be and not has_date and not has_benev:
        return normalize_planning_df(_place_be_auto(planning_df, be_num, nb_colis, dest))

    if has_be and has_date and not has_benev:
        return normalize_planning_df(_place_be_semi_auto(planning_df, be_num, nb_colis, dest, date_vol, heure_vol))

    if has_be and not has_date and has_benev:
        return normalize_planning_df(_place_be_with_forced_benevole(planning_df, be_num, nb_colis, dest, benevole))

    if has_be and has_date and has_benev:
        return normalize_planning_df(_place_be_manual(planning_df, be_num, nb_colis, dest, date_vol, heure_vol, benevole))

    raise BEPlacementError("Paramètres incohérents.")


# =====================================================================
# 1️⃣ MANUEL
# =====================================================================

def _place_be_manual(planning_df, be_num, nb_colis, dest, date_vol, heure_vol, benevole):
    flights = _extract_flights_from_planning(planning_df)

    # Vol existant à la date ?
    same_day = flights[flights["Date_Vol"] == date_vol]
    if dest:
        same_day = same_day[same_day["Destination"] == dest]

    if same_day.empty:
        vol_number = "MANUEL"
    else:
        row = same_day.sort_values(["total_equiv", "nb_be"]).iloc[0]
        vol_number = row["Numero_Vol"]

    new_row = _build_new_row(be_num, nb_colis, dest, date_vol, heure_vol, vol_number, benevole)
    return pd.concat([planning_df, pd.DataFrame([new_row])], ignore_index=True)


# =====================================================================
# 2️⃣ AUTO
# =====================================================================

def _place_be_auto(planning_df, be_num, nb_colis, dest):
    flights = _extract_flights_from_planning(planning_df)

    if flights.empty:
        raise BEPlacementError("Aucun vol existant dans le planning.")

    if dest:
        flights = flights[flights["Destination"] == dest]

    flights = flights[flights.apply(lambda r: _flight_capacity_ok(r, nb_colis), axis=1)]
    best = _choose_best_flight(flights, nb_colis)

    if best is None:
        raise BEPlacementError("Aucun vol compatible trouvé (destination ou capacité).")

    date_vol = best["Date_Vol"]
    heure_str = best["Heure_Vol"]
    vol = best["Numero_Vol"]

    benev = _choose_best_benevole_on_flight(planning_df, date_vol, heure_str, vol, nb_colis)

    heure_vol = _to_time(heure_str)
    new_row = _build_new_row(be_num, nb_colis, dest or best["Destination"], date_vol, heure_vol, vol, benev)

    return pd.concat([planning_df, pd.DataFrame([new_row])], ignore_index=True)


# =====================================================================
# 3️⃣ SEMI-AUTO
# =====================================================================

def _place_be_semi_auto(planning_df, be_num, nb_colis, dest, date_vol, heure_vol):
    flights = _extract_flights_from_planning(planning_df)

    subset = flights[flights["Date_Vol"] == date_vol]
    if dest:
        subset = subset[subset["Destination"] == dest]

    if subset.empty:
        new_row = _build_new_row(be_num, nb_colis, dest, date_vol, heure_vol, "MANUEL", "")
        return pd.concat([planning_df, pd.DataFrame([new_row])], ignore_index=True)

    subset = subset[subset.apply(lambda r: _flight_capacity_ok(r, nb_colis), axis=1)]
    best = _choose_best_flight(subset, nb_colis)

    if best is None:
        raise BEPlacementError("Pas de vol compatible en capacité ce jour-là.")

    vol = best["Numero_Vol"]
    heure_str = best["Heure_Vol"]
    benev = _choose_best_benevole_on_flight(planning_df, date_vol, heure_str, vol, nb_colis)

    final_time = heure_vol or _to_time(heure_str)

    new_row = _build_new_row(be_num, nb_colis, dest or best["Destination"], date_vol, final_time, vol, benev)
    return pd.concat([planning_df, pd.DataFrame([new_row])], ignore_index=True)


# =====================================================================
# 4️⃣ BÉNÉVOLE FORCÉ
# =====================================================================

def _place_be_with_forced_benevole(planning_df, be_num, nb_colis, dest, benevole):
    flights = _extract_flights_from_planning(planning_df)

    df = planning_df.copy()
    df["Benevole"] = df["Benevole"].apply(_norm_str)
    df["Date_Vol"] = df["Date_Vol"].apply(_to_date)
    df["Heure_Vol"] = df["Heure_Vol"].apply(_norm_str)

    vols_benev = df[df["Benevole"] == benevole]
    if vols_benev.empty:
        raise BEPlacementError(f"Le bénévole '{benevole}' n'est affecté à aucun vol.")

    vols_benev = vols_benev[["Date_Vol", "Heure_Vol", "Numero_Vol", "Destination"]].drop_duplicates()

    merged = vols_benev.merge(
        flights,
        on=["Date_Vol", "Heure_Vol", "Numero_Vol", "Destination"],
        how="left"
    )

    if dest:
        merged = merged[merged["Destination"] == dest]

    if merged.empty:
        raise BEPlacementError(f"Aucun vol compatible pour le bénévole '{benevole}'.")

    merged = merged[merged.apply(lambda r: _flight_capacity_ok(r, nb_colis), axis=1)]

    if merged.empty:
        raise BEPlacementError(f"Aucun vol du bénévole '{benevole}' n'a la capacité requise.")

    best = _choose_best_flight(merged, nb_colis)
    date_vol = best["Date_Vol"]
    heure_str = best["Heure_Vol"]
    vol = best["Numero_Vol"]

    heure_vol = _to_time(heure_str)

    new_row = _build_new_row(be_num, nb_colis, dest or best["Destination"], date_vol, heure_vol, vol, benevole)
    return pd.concat([planning_df, pd.DataFrame([new_row])], ignore_index=True)
