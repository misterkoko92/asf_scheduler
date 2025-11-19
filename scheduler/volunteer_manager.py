# scheduler/volunteer_manager.py
# -*- coding: utf-8 -*-

from __future__ import annotations

from datetime import datetime, date, time
from typing import Dict, List, Optional, Tuple
import math
import pandas as pd

from scheduler.models import Volunteer, Flight
from scheduler.config import MAX_EQUIV_PER_VOLUNTEER
from scheduler.config_paths import PLANNING_BENEVOLES, SHEET_PARAM_BENEV


# ==========================================================
#  Helpers
# ==========================================================

def _to_int_or_none(v) -> Optional[int]:
    """
    Convertit une valeur en int ou None (si vide / invalide).
    """
    if v is None:
        return None
    s = str(v).strip()
    if s == "":
        return None
    try:
        return int(float(s))
    except Exception:
        return None


# ==========================================================
#  Chargement ParamBenev depuis config_paths
# ==========================================================

def load_param_benev() -> Dict[str, Dict[str, Optional[int]]]:
    """
    Charge ParamBenev depuis :

        PLANNING_BENEVOLES.xlsx / SHEET_PARAM_BENEV

    Retour :
        { ID : {
            "BENEVOLE": ...,
            "NOM": ...,
            "PRENOM": ...,
            "PRENOM_COURT": ...,
            "MAX_JOURS_SEMAINE": int|None,
            "MAX_EXP_SEMAINE": int|None,
            "MAX_EXP_JOUR": int|None,
            "ATTENTE_MAX_H": int|None
        } }
    """

    df = pd.read_excel(
        PLANNING_BENEVOLES,
        sheet_name=SHEET_PARAM_BENEV,
        dtype=str
    ).fillna("")

    params: Dict[str, Dict[str, Optional[int]]] = {}

    for _, r in df.iterrows():
        id_ = str(r.get("ID", "")).strip()
        if not id_:
            continue

        params[id_] = {
            "BENEVOLE": str(r.get("BENEVOLE", "")).strip(),
            "NOM": str(r.get("NOM", "")).strip(),
            "PRENOM": str(r.get("PRENOM", "")).strip(),
            "PRENOM_COURT": str(r.get("PRENOM_COURT", "")).strip(),
            "MAX_JOURS_SEMAINE": _to_int_or_none(r.get("MAX_JOURS_SEMAINE", "")),
            "MAX_EXP_SEMAINE": _to_int_or_none(r.get("MAX_EXP_SEMAINE", "")),
            "MAX_EXP_JOUR": _to_int_or_none(r.get("MAX_EXP_JOUR", "")),
            "ATTENTE_MAX_H": _to_int_or_none(r.get("ATTENTE_MAX_H", "")),
        }

    return params


# ==========================================================
#  Parsing planning bénévoles (DISPONIBILITÉS)
# ==========================================================

def _find_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    """
    Cherche la première colonne présente parmi une liste de noms possibles
    (tolérant aux variations de casse / accents).
    """
    cols_lower = {c.lower(): c for c in df.columns}
    for c in candidates:
        if c in df.columns:
            return c
        if c.lower() in cols_lower:
            return cols_lower[c.lower()]
    return None


def _parse_date(v) -> Optional[date]:
    if pd.isna(v):
        return None
    try:
        return pd.to_datetime(v, dayfirst=True, errors="coerce").date()
    except Exception:
        return None


def _parse_time(v) -> Optional[time]:
    if pd.isna(v):
        return None
    s = str(v).strip()
    if s == "":
        return None

    # formats classiques
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).time()
        except Exception:
            pass

    # fallback via pandas (gère les sérialisations Excel)
    try:
        return pd.to_datetime(v).time()
    except Exception:
        return None


def build_volunteers(
    df_benev: pd.DataFrame,
    param_benev: Dict[str, Dict[str, Optional[int]]]
) -> List[Volunteer]:
    """
    Construit la liste des objets Volunteer à partir :
    - du planning des disponibilités (df_benev)
    - des paramètres ParamBenev (param_benev)
    """

    volunteers: List[Volunteer] = []

    col_date = _find_col(df_benev, ["DATE"])
    col_arrivee = _find_col(df_benev, ["HEURE_ARRIVEE", "HEURE ARRIVEE", "HEURE ARRIVÉE"])
    col_depart = _find_col(df_benev, ["HEURE_DEPART", "HEURE DEPART", "HEURE DÉPART"])

    if col_date is None:
        raise KeyError("Colonne DATE introuvable dans le planning bénévoles.")
    if col_arrivee is None or col_depart is None:
        raise KeyError("Colonnes HEURE_ARRIVEE / HEURE_DEPART introuvables.")

    for _, r in df_benev.iterrows():
        id_ = str(r.get("ID", "")).strip()
        if not id_:
            continue

        d = _parse_date(r.get(col_date))
        h_arr = _parse_time(r.get(col_arrivee))
        h_dep = _parse_time(r.get(col_depart))

        if d is None:
            continue  # pas de date ⇒ on ignore la ligne

        param = param_benev.get(id_, {})

        v = Volunteer(
            id=id_,
            benevole=param.get("BENEVOLE") or str(r.get("BENEVOLE", "")).strip(),
            nom=param.get("NOM") or str(r.get("NOM", "")).strip(),
            prenom=param.get("PRENOM") or str(r.get("PRENOM", "")).strip(),
            prenom_court=param.get("PRENOM_COURT") or str(r.get("PRENOM_COURT", "")).strip(),
            date=d,
            heure_arrivee=h_arr,
            heure_depart=h_dep,
            max_exped_jour=param.get("MAX_EXP_JOUR"),
            max_exped_semaine=param.get("MAX_EXP_SEMAINE"),
            max_jours_semaine=param.get("MAX_JOURS_SEMAINE"),
        )

        # Attente max entre 2 vols dans la journée
        attente_max = param.get("ATTENTE_MAX_H")
        if attente_max is not None:
            v.attente_max_h = attente_max  # attribut dynamique

        if v.is_time_window_valid():
            volunteers.append(v)

    print(f"➡ Bénévoles utilisables (après filtrage heures): {len(volunteers)}")
    return volunteers


# ==========================================================
#  Affectation bénévoles -> vols
# ==========================================================

def _week_key(d: date) -> Tuple[int, int]:
    iso = d.isocalendar()
    return iso[0], iso[1]


def assign_volunteers_to_flights(
    flights: List[Flight],
    volunteers: List[Volunteer]
) -> None:
    """
    Affecte les bénévoles aux vols en respectant :

    - Date du bénévole == date du vol
    - Heure départ vol ∈ [heure_arrivee, heure_depart]
    - MAX_EXP_JOUR / MAX_EXP_SEMAINE / MAX_JOURS_SEMAINE
    - ATTENTE_MAX_H
    - MAX_EQUIV_PER_VOLUNTEER (charge équivalente par bénévole et par vol)
    """

    # Compteurs
    exp_week: Dict[Tuple[str, Tuple[int, int]], int] = {}
    exp_day: Dict[Tuple[str, date], int] = {}
    days_week: Dict[Tuple[str, Tuple[int, int]], set] = {}
    last_time_day: Dict[Tuple[str, date], time] = {}

    # On ne traite que les vols ayant des BE
    flights_to_assign = [f for f in flights if f.shipments]
    flights_to_assign.sort(key=lambda f: (f.date, f.departure_time or time(0, 0)))

    for f in flights_to_assign:
        if f.date is None or f.departure_time is None:
            continue

        # Charge équivalente totale sur le vol
        total_equiv = sum(
            int(getattr(s, "equiv_colis", s.nb_colis_physiques))
            for s in f.shipments
        )

        if total_equiv <= 0:
            continue

        # Nombre de bénévoles requis pour cette charge
        nb_needed = max(1, math.ceil(total_equiv / MAX_EQUIV_PER_VOLUNTEER))

        # Réinitialise toujours la liste
        f.assigned_volunteers = []

        wk = _week_key(f.date)

        for _ in range(nb_needed):
            best_v: Optional[Volunteer] = None
            best_score: Optional[Tuple[int, int]] = None

            for v in volunteers:
                # déjà sur ce vol ?
                if v in f.assigned_volunteers:
                    continue

                # même jour
                if v.date != f.date:
                    continue

                if not v.is_time_window_valid():
                    continue

                # Heure de vol dans la plage de présence
                if not (v.heure_arrivee <= f.departure_time <= v.heure_depart):
                    continue

                wkey = (v.id, wk)
                dkey = (v.id, f.date)

                wexp = exp_week.get(wkey, 0)
                dexp = exp_day.get(dkey, 0)
                used_days = days_week.get(wkey, set())

                # Limites hebdo et journalières
                if v.max_exped_semaine is not None and wexp >= v.max_exped_semaine:
                    continue
                if v.max_jours_semaine is not None and len(used_days | {f.date}) > v.max_jours_semaine:
                    continue
                if v.max_exped_jour is not None and dexp >= v.max_exped_jour:
                    continue

                # ATTENTE_MAX_H (écart avec le dernier vol de la journée)
                wait = getattr(v, "attente_max_h", None)
                if wait is not None and dexp > 0:
                    last_t = last_time_day.get(dkey)
                    if last_t:
                        t1 = datetime.combine(date(2000, 1, 1), last_t)
                        t2 = datetime.combine(date(2000, 1, 1), f.departure_time)
                        delta_h = abs((t2 - t1).total_seconds()) / 3600.0
                        if delta_h > wait:
                            continue

                # Score de "charge" : on favorise ceux qui ont le moins de vols
                score = (wexp, dexp)
                if best_score is None or score < best_score:
                    best_score = score
                    best_v = v

            if best_v is None:
                # pas de bénévole supplémentaire dispo pour ce vol
                break

            # Ajout sur le vol
            f.assigned_volunteers.append(best_v)

            # Compatibilité avec anciens champs (un bénévole principal)
            if not hasattr(f, "assigned_volunteer") or f.assigned_volunteer is None:
                f.assigned_volunteer = best_v
                f.assigned_volunteer_id = best_v.id

            # Ajout sur le bénévole
            best_v.assigned_flights.append(f)

            # Mise à jour compteurs
            wkey = (best_v.id, wk)
            dkey = (best_v.id, f.date)

            exp_week[wkey] = exp_week.get(wkey, 0) + 1
            exp_day[dkey] = exp_day.get(dkey, 0) + 1

            days = days_week.get(wkey, set())
            days.add(f.date)
            days_week[wkey] = days

            last_time_day[dkey] = f.departure_time
