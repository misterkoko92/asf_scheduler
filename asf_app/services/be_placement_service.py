# asf_app/services/be_placement_service.py
# -*- coding: utf-8 -*-
import datetime
from typing import Optional, Tuple, Dict

import pandas as pd

from scheduler import config


class BEPlacementError(Exception):
    """Exception métier pour un ajout de BE impossible ou incohérent."""
    pass


# =====================================================================
# FONCTION PRINCIPALE
# =====================================================================

def place_be(
    planning_df: pd.DataFrame,
    be_num: Optional[str],
    nb_colis: int,
    dest: Optional[str],
    date_vol: Optional[datetime.date],
    heure_vol: Optional[datetime.time],
    benevole: Optional[str],
) -> pd.DataFrame:
    """
    Place intelligemment un BE dans le planning existant.

    Gère les cas :
    - BE seul                         -> AUTO (vol + bénévole choisis)
    - BE + Vol (date)                 -> SEMI-AUTO (vol fixé, bénévole choisi)
    - BE + Bénévole                   -> bénévole imposé, vol auto
    - BE + Vol + Bénévole             -> MANUEL (pas de recalcul moteur)

    Les cas sans BE sont rejetés.
    """
    be_num = (be_num or "").strip()
    benevole = (benevole or "").strip()
    dest = (dest or "").strip()

    has_be = bool(be_num)
    has_date = isinstance(date_vol, datetime.date)
    has_benev = bool(benevole)

    # ---------- Cas invalides : pas de BE ----------
    if not has_be:
        raise BEPlacementError("Impossible d'ajouter un BE : aucun numéro de BE renseigné.")

    # ---------- Dispatch selon la combinaison ----------
    if has_be and (not has_date) and (not has_benev):
        # BE seul -> AUTO (vol + bénévole choisis)
        return _place_be_auto(planning_df, be_num, nb_colis, dest)

    if has_be and has_date and (not has_benev):
        # BE + Vol (date) -> SEMI-AUTO (vol fixé, bénévole choisi)
        return _place_be_semi_auto(planning_df, be_num, nb_colis, dest, date_vol, heure_vol)

    if has_be and (not has_date) and has_benev:
        # BE + Bénévole -> bénévole imposé, vol auto
        return _place_be_with_forced_benevole(planning_df, be_num, nb_colis, dest, benevole)

    if has_be and has_date and has_benev:
        # BE + Vol + Bénévole -> manuel : ajout direct
        return _place_be_manual(planning_df, be_num, nb_colis, dest, date_vol, heure_vol, benevole)

    # Si on arrive ici : combinaison inattendue (pour sécurité)
    raise BEPlacementError("Combinaison de paramètres incohérente pour l'ajout du BE.")


# =====================================================================
# OUTILS COMMUNS
# =====================================================================

def _extract_flights_from_planning(planning_df: pd.DataFrame) -> pd.DataFrame:
    """
    Regroupe le planning par vol (Date_Vol, Heure_Vol, Vol, Destination)
    et calcule des métriques :
      - nb_be : nombre de lignes BE
      - total_equiv : somme BE_Nb_Equiv (ou BE_Nb_Colis à défaut)
      - benevoles : ensemble des bénévoles non vides
    """
    if planning_df is None or planning_df.empty:
        return pd.DataFrame(columns=["Date_Vol", "Heure_Vol", "Vol", "Destination",
                                     "nb_be", "total_equiv", "benevoles"])

    df = planning_df.copy()

    if "BE_Nb_Equiv" in df.columns:
        df["__EQUIV__"] = df["BE_Nb_Equiv"].fillna(df["BE_Nb_Colis"])
    else:
        df["__EQUIV__"] = df["BE_Nb_Colis"]

    def agg_benevoles(series):
        return {b for b in series.dropna().unique() if str(b).strip()}

    grouped = df.groupby(["Date_Vol", "Heure_Vol", "Vol", "Destination"], dropna=False).agg(
        nb_be=("BE_Numero", "count"),
        total_equiv=(".__EQUIV__", "sum"),
        benevoles=("Benevole", agg_benevoles),
    ).reset_index()

    return grouped


def _flight_capacity_ok(row: pd.Series, nb_colis: int) -> bool:
    """
    Vérifie qu'il reste de la place sur ce vol pour nb_colis.
    - Nb BE max par vol : config.MAX_BE_PER_FLIGHT
    - Équivalents max par bénévole : config.MAX_EQUIV_PER_VOLUNTEER
      (capacité approx = nb_bénévoles * MAX_EQUIV)
    """
    max_be = int(config.MAX_BE_PER_FLIGHT)
    max_equiv = int(config.MAX_EQUIV_PER_VOLUNTEER)

    if row["nb_be"] >= max_be:
        return False

    benevoles = row["benevoles"] or set()
    if not benevoles:
        # Aucun bénévole pour l'instant -> on autorise l'ajout,
        # le bénévole pourra être assigné plus tard.
        return True

    capa_equiv = len(benevoles) * max_equiv
    if row["total_equiv"] + nb_colis > capa_equiv:
        # On dépasse la capacité équivalente approximative
        return False

    return True


def _choose_best_flight(candidates: pd.DataFrame, nb_colis: int) -> Optional[pd.Series]:
    """
    Choisit le "meilleur" vol parmi les candidats.
    Stratégie : celui avec le plus de capacité restante / le moins chargé.
    """
    if candidates is None or candidates.empty:
        return None

    # Score simple : total_equiv + nb_be (minimiser)
    candidates = candidates.copy()
    candidates["score_load"] = candidates["total_equiv"] + candidates["nb_be"] * nb_colis

    candidates = candidates.sort_values(
        by=["score_load", "Date_Vol", "Heure_Vol", "Vol"]
    )

    return candidates.iloc[0]


def _choose_best_benevole_on_flight(planning_df: pd.DataFrame,
                                    date_vol: datetime.date,
                                    heure_str: str,
                                    vol: str,
                                    nb_colis: int) -> str:
    """
    Choisit le bénévole le plus adapté sur le vol (date/heure/numéro) en
    fonction de la charge actuelle, en respectant config.MAX_EQUIV_PER_VOLUNTEER.
    Si aucun bénévole présent sur ce vol, retourne "" (à affecter plus tard).
    """
    df = planning_df.copy()
    mask = (
        (df["Date_Vol"] == date_vol) &
        (df["Heure_Vol"] == heure_str) &
        (df["Vol"] == vol)
    )
    vol_df = df.loc[mask]

    vol_df = vol_df[vol_df["Benevole"].notna() & (df["Benevole"].str.strip() != "")]
    if vol_df.empty:
        return ""

    if "BE_Nb_Equiv" in vol_df.columns:
        vol_df["__EQUIV__"] = vol_df["BE_Nb_Equiv"].fillna(vol_df["BE_Nb_Colis"])
    else:
        vol_df["__EQUIV__"] = vol_df["BE_Nb_Colis"]

    load_by_benev = vol_df.groupby("Benevole")["__EQUIV__"].sum().to_dict()
    max_equiv = int(config.MAX_EQUIV_PER_VOLUNTEER)

    # On trie par (surcharge autorisée ou non, charge actuelle)
    best = None
    best_key = None
    for b, load in load_by_benev.items():
        will_overflow = load + nb_colis > max_equiv
        key = (will_overflow, load)  # privilégie ceux qui ne dépassent pas
        if best_key is None or key < best_key:
            best_key = key
            best = b

    return best or ""


def _build_new_row(
    be_num: str,
    nb_colis: int,
    dest: Optional[str],
    date_vol: datetime.date,
    heure_vol: Optional[datetime.time],
    vol: str,
    benevole: str,
) -> Dict:
    """
    Construit la nouvelle ligne de planning à ajouter.
    """
    heure_str = ""
    if isinstance(heure_vol, datetime.time):
        heure_str = heure_vol.strftime("%H:%M")

    return {
        "Date_Vol": date_vol,
        "Heure_Vol": heure_str,
        "Vol": vol,
        "Destination": dest or "",
        "BE_Numero": be_num,
        "BE_Nb_Colis": nb_colis,
        "BE_Nb_Equiv": nb_colis,  # approx = nb_colis
        "Benevole": benevole,
    }


# =====================================================================
# 1️⃣ MODE MANUEL : BE + Date + Bénévole
# =====================================================================

def _place_be_manual(
    planning_df: pd.DataFrame,
    be_num: str,
    nb_colis: int,
    dest: Optional[str],
    date_vol: datetime.date,
    heure_vol: Optional[datetime.time],
    benevole: str,
) -> pd.DataFrame:
    """
    Mode manuel : l'utilisateur impose à la fois la date et le bénévole.
    On ne recalcule rien, on ajoute juste la ligne.
    Le numéro de vol est mis à "MANUEL" s'il n'existe pas dans le planning.
    """
    flights = _extract_flights_from_planning(planning_df)

    # On cherche s'il existe déjà un vol à cette date (et même destination si fournie)
    mask = (flights["Date_Vol"] == date_vol)
    if dest:
        mask &= (flights["Destination"] == dest)

    subset = flights.loc[mask]
    if subset.empty:
        vol_number = "MANUEL"
    else:
        # choix du vol le moins chargé ce jour-là
        row = subset.sort_values(by=["total_equiv", "nb_be"]).iloc[0]
        vol_number = row["Vol"]

    new_row = _build_new_row(be_num, nb_colis, dest, date_vol, heure_vol, vol_number, benevole)
    return pd.concat([planning_df, pd.DataFrame([new_row])], ignore_index=True)


# =====================================================================
# 2️⃣ MODE AUTO : BE seul -> moteur choisit vol + bénévole
# =====================================================================

def _place_be_auto(
    planning_df: pd.DataFrame,
    be_num: str,
    nb_colis: int,
    dest: Optional[str],
) -> pd.DataFrame:
    flights = _extract_flights_from_planning(planning_df)
    if flights.empty:
        raise BEPlacementError("Aucun vol existant dans le planning : impossible de placer ce BE automatiquement.")

    # Filtre par destination si fournie
    if dest:
        flights = flights[flights["Destination"] == dest]

    # Filtre capacité
    flights = flights[flights.apply(lambda r: _flight_capacity_ok(r, nb_colis), axis=1)]

    best = _choose_best_flight(flights, nb_colis)
    if best is None:
        raise BEPlacementError("Aucun vol compatible trouvé pour ce BE (capacité ou destination).")

    date_vol = best["Date_Vol"]
    heure_str = best["Heure_Vol"]
    vol = best["Vol"]
    benevole = _choose_best_benevole_on_flight(planning_df, date_vol, heure_str, vol, nb_colis)

    # On convertit l'heure string en time si possible
    heure_vol = None
    try:
        if isinstance(heure_str, str) and heure_str:
            h, m = heure_str.split(":")
            heure_vol = datetime.time(int(h), int(m))
    except Exception:
        heure_vol = None

    new_row = _build_new_row(be_num, nb_colis, dest or best["Destination"], date_vol, heure_vol, vol, benevole)
    return pd.concat([planning_df, pd.DataFrame([new_row])], ignore_index=True)


# =====================================================================
# 3️⃣ MODE SEMI-AUTO : BE + Vol (date) -> bénévole choisi
# =====================================================================

def _place_be_semi_auto(
    planning_df: pd.DataFrame,
    be_num: str,
    nb_colis: int,
    dest: Optional[str],
    date_vol: datetime.date,
    heure_vol: Optional[datetime.time],
) -> pd.DataFrame:
    flights = _extract_flights_from_planning(planning_df)

    # Filtrer vols à cette date (+ destination si fournie)
    mask = (flights["Date_Vol"] == date_vol)
    if dest:
        mask &= (flights["Destination"] == dest)
    subset = flights.loc[mask]

    if subset.empty:
        # Aucun vol existant ce jour-là : on crée un vol "MANUEL"
        vol_number = "MANUEL"
        benevole = ""
        new_row = _build_new_row(be_num, nb_colis, dest, date_vol, heure_vol, vol_number, benevole)
        return pd.concat([planning_df, pd.DataFrame([new_row])], ignore_index=True)

    # On choisit le meilleur vol selon la charge
    subset = subset[subset.apply(lambda r: _flight_capacity_ok(r, nb_colis), axis=1)]
    best = _choose_best_flight(subset, nb_colis)
    if best is None:
        raise BEPlacementError("Aucun vol compatible (capacité) pour la date indiquée.")

    vol = best["Vol"]
    heure_str = best["Heure_Vol"]  # heure déjà planifiée
    benevole = _choose_best_benevole_on_flight(planning_df, date_vol, heure_str, vol, nb_colis)

    # Priorité à l'heure de formulaire si fournie, sinon celle du vol existant
    final_time = heure_vol
    if final_time is None and isinstance(heure_str, str) and heure_str:
        try:
            h, m = heure_str.split(":")
            final_time = datetime.time(int(h), int(m))
        except Exception:
            final_time = None

    new_row = _build_new_row(be_num, nb_colis, dest or best["Destination"], date_vol, final_time, vol, benevole)
    return pd.concat([planning_df, pd.DataFrame([new_row])], ignore_index=True)


# =====================================================================
# 4️⃣ MODE BÉNÉVOLE FORCÉ : BE + Bénévole
# =====================================================================

def _place_be_with_forced_benevole(
    planning_df: pd.DataFrame,
    be_num: str,
    nb_colis: int,
    dest: Optional[str],
    benevole: str,
) -> pd.DataFrame:
    flights = _extract_flights_from_planning(planning_df)

    # On ne garde que les vols où ce bénévole apparaît déjà (continuité logique)
    df = planning_df.copy()
    mask_b = df["Benevole"].fillna("").str.strip() == benevole
    vols_benev = df.loc[mask_b]

    if vols_benev.empty:
        raise BEPlacementError(f"Le bénévole '{benevole}' n'est affecté à aucun vol dans le planning actuel.")

    # On reconstruit la liste des vols de ce bénévole
    vols_benev = vols_benev[["Date_Vol", "Heure_Vol", "Vol", "Destination"]].drop_duplicates()

    # Jointure avec les métriques de capacité
    merged = vols_benev.merge(
        flights,
        on=["Date_Vol", "Heure_Vol", "Vol", "Destination"],
        how="left",
        suffixes=("", "_m"),
    )

    # Filtre destination si fournie
    if dest:
        merged = merged[merged["Destination"] == dest]

    if merged.empty:
        raise BEPlacementError(f"Aucun vol compatible trouvé pour le bénévole '{benevole}' (destination).")

    # Filtre capacité
    merged = merged[merged.apply(lambda r: _flight_capacity_ok(r, nb_colis), axis=1)]
    if merged.empty:
        raise BEPlacementError(f"Aucun vol avec capacité suffisante pour le bénévole '{benevole}'.")

    # Choix du meilleur vol
    best = _choose_best_flight(merged, nb_colis)
    date_vol = best["Date_Vol"]
    heure_str = best["Heure_Vol"]
    vol = best["Vol"]

    # Convertit l'heure string en time si possible
    heure_vol = None
    try:
        if isinstance(heure_str, str) and heure_str:
            h, m = heure_str.split(":")
            heure_vol = datetime.time(int(h), int(m))
    except Exception:
        heure_vol = None

    new_row = _build_new_row(be_num, nb_colis, dest or best["Destination"], date_vol, heure_vol, vol, benevole)
    return pd.concat([planning_df, pd.DataFrame([new_row])], ignore_index=True)
