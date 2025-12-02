# scheduler/volunteer_manager.py
# -*- coding: utf-8 -*-

from __future__ import annotations

from datetime import datetime, date, time, timedelta
from typing import Dict, List, Optional
import random
import math
import pandas as pd
from collections import defaultdict

from scheduler.models import Volunteer, Flight
from scheduler.config import (
    MAX_BENEV_PER_VOL,
    DUREE_MISSION_HEURES,
    MAX_EQUIV_PER_VOLUNTEER,
    MAX_CAPACITE_PAR_VOL,
    DEFAULT_FLIGHT_TIME,
    MIN_HOURS_BETWEEN_FLIGHTS,
)
from scheduler.config_paths import SHEET_PARAM_BENEV
from loaders.universal_loader import load_and_normalize
from scheduler.column_map import column_map_param_benev


# =====================================================================
# HELPERS DATE / HEURE
# =====================================================================

def _to_datetime(v):
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, date):
        return datetime(v.year, v.month, v.day)
    try:
        dt = pd.to_datetime(v, dayfirst=True, errors="coerce")
        if pd.isna(dt):
            return None
        return dt.to_pydatetime()
    except Exception:
        return None


def _to_date(v):
    dt = _to_datetime(v)
    return dt.date() if dt else None


def _to_time(v):
    if v is None or str(v).strip() == "":
        return None
    s = str(v).strip()

    # formats type "10h30" ou "10H30"
    if "h" in s.lower():
        try:
            h, m = s.lower().replace("h", " ").split()
            return time(int(h), int(m))
        except Exception:
            try:
                h = int(s.lower().replace("h", "").strip())
                return time(h, 0)
            except Exception:
                pass

    # formats décimaux "10,5" ou "10.5" => heures fractionnaires
    try:
        val = float(s.replace(",", "."))
        if 0 <= val < 24:
            minutes = int(round((val - int(val)) * 60))
            return time(int(val), minutes)
    except Exception:
        pass

    # formats directs
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).time()
        except Exception:
            pass

    # fallback pandas
    try:
        dt = pd.to_datetime(v, errors="coerce")
        if pd.isna(dt):
            return None
        return dt.to_pydatetime().time()
    except Exception:
        return None


def _find_col(df, names):
    low = {c.lower(): c for c in df.columns}
    for n in names:
        if n in df.columns:
            return n
        if n.lower() in low:
            return low[n.lower()]
    return None


# =====================================================================
# CHARGEMENT PARAMBENEVOLES
# =====================================================================

def load_param_benev(path_benev) -> Dict[str, Dict]:
    """
    Charge ParamBenev (normalisé via universal_loader).
    """
    df = load_and_normalize(
        path=path_benev,
        sheet_name=SHEET_PARAM_BENEV,
        mapping=column_map_param_benev,
        header=0,
    ).fillna("")

    print("\n=== PARAM_BENEV : Chargement ===")
    print(f"Colonnes détectées : {list(df.columns)}")
    try:
        print(df.head(5))
    except Exception:
        pass
    print("================================\n")

    params: Dict[str, Dict] = {}

    for _, r in df.iterrows():
        id_ = str(r.get("ID", "")).strip()
        if not id_:
            continue

        def norm_int(x):
            try:
                return int(float(x))
            except Exception:
                return None

        params[id_] = {
            "Benevole": str(r.get("Benevole", "")).strip(),
            "Nom": str(r.get("Nom", "")).strip(),
            "Prenom": str(r.get("Prenom", "")).strip(),
            "Prenom_Court": str(r.get("Prenom_Court", "")).strip(),
            "Max_Jours_Semaine": norm_int(r.get("Max_Jours_Semaine")),
            "Max_Exp_Semaine": norm_int(r.get("Max_Exp_Semaine")),
            "Max_Exp_Jour": norm_int(r.get("Max_Exp_Jour")),
            "Attente_Max_Heures": norm_int(r.get("Attente_Max_Heures")),
            "Telephone": str(r.get("Telephone", "")).strip(),
        }

    print(f"➡ ParamBenev chargés pour {len(params)} IDs.\n")
    return params


# =====================================================================
# CONSTRUCTION DES OBJETS VOLUNTEER
# =====================================================================

def build_volunteers(df_benev: pd.DataFrame,
                     param_benev: Dict[str, Dict]) -> List[Volunteer]:
    """
    Construit la liste des objets Volunteer à partir :
      - df_benev (Disponibilités normalisées)
      - param_benev (ParamBenev, limites perso, noms...)
    """

    print("\n=== DEBUG DISPONIBILITÉS (BRUT) ===")
    print(f"Nb lignes : {len(df_benev)}")
    print(f"Colonnes : {list(df_benev.columns)}")
    try:
        print(df_benev.head(5))
    except Exception:
        pass
    print("====================================\n")

    df = df_benev.fillna("")

    col_date = _find_col(df, ["Date"])
    col_arr = _find_col(df, ["Heure_Arrivee", "Heure Arrivee"])
    col_dep = _find_col(df, ["Heure_Depart", "Heure Depart"])

    if col_date is None:
        raise KeyError("Colonne DATE introuvable dans disponibilités.")
    if col_arr is None or col_dep is None:
        raise KeyError("Colonnes HEURE_ARRIVEE / HEURE_DEPART introuvables.")

    volunteers: List[Volunteer] = []
    nb_valid_date = 0
    nb_valid_time = 0

    for _, r in df.iterrows():
        id_ = str(r.get("ID", "")).strip()
        if not id_:
            continue

        dt = _to_date(r.get(col_date))
        if dt is None:
            continue
        nb_valid_date += 1

        ha = _to_time(r.get(col_arr))
        hd = _to_time(r.get(col_dep))
        if ha is None or hd is None or ha >= hd:
            continue
        nb_valid_time += 1

        p = param_benev.get(id_, {})

        v = Volunteer(
            id=id_,
            benevole=p.get("Benevole") or str(r.get("Benevole", "")),
            nom=p.get("Nom") or str(r.get("Nom", "")),
            prenom=p.get("Prenom") or str(r.get("Prenom", "")),
            prenom_court=p.get("Prenom_Court") or str(r.get("Prenom_Court", "")),
            date=dt,
            heure_arrivee=ha,
            heure_depart=hd,
            max_exped_jour=p.get("Max_Exp_Jour", 99),
            max_exped_semaine=p.get("Max_Exp_Semaine", 99),
            max_jours_semaine=p.get("Max_Jours_Semaine", 7),
        )

        v.attente_max_h = p.get("Attente_Max_Heures", 5)
        v.assigned_flights = []
        v.telephone = p.get("Telephone", "")

        volunteers.append(v)

    print("\n=== DEBUG BUILD VOLUNTEERS ===")
    print(f"Lignes avec date valide : {nb_valid_date}")
    print(f"Lignes fenêtre horaire OK : {nb_valid_time}")
    print(f"Bénévoles utilisables : {len(volunteers)}")
    for v in volunteers[:10]:
        print(
            f" - ID={v.id} | {v.benevole} | {v.date} "
            f"{v.heure_arrivee}→{v.heure_depart}"
        )
    print("================================\n")

    return volunteers


# =====================================================================
# HELPERS : MATCHING / SCORING
# =====================================================================

def _vol_fits_in_dispo(f: Flight, v: Volunteer) -> bool:
    """
    Un bénévole peut prendre un vol si :
      - même date
      - disponible au moins jusqu’à l’heure du vol
      - peut arriver au plus tard à (heure_vol - DUREE_MISSION_HEURES)
    """
    if v.date != f.date:
        return False

    t_dep = f.departure_time or DEFAULT_FLIGHT_TIME
    mission_start = (
        datetime.combine(f.date, t_dep) - timedelta(hours=DUREE_MISSION_HEURES)
    ).time()

    return v.heure_arrivee <= mission_start and v.heure_depart >= t_dep


def _estimate_flight_load(f: Flight) -> float:
    """
    Estime la charge du vol (0..1+), utilisée pour trier les vols.
    """
    equiv = (
        getattr(f, "total_colis", None)
        or getattr(f, "equiv_total", None)
        or getattr(f, "nb_colis_physiques", None)
    )

    if equiv is None or equiv <= 0:
        return 0.0

    cap = getattr(f, "max_colis_base", None) or MAX_CAPACITE_PAR_VOL
    if cap is None or cap <= 0:
        return 1.0

    return float(equiv) / float(cap)


def _estimate_target_volunteers(f: Flight) -> int:
    """
    Estime le nombre cible de bénévoles pour ce vol.
    Si aucun colis → 0 bénévoles.
    Sinon en fonction de MAX_EQUIV_PER_VOLUNTEER et de la capacité.
    """
    equiv = (
        getattr(f, "total_colis", None)
        or getattr(f, "equiv_total", None)
        or getattr(f, "nb_colis_physiques", None)
    )

    if equiv is None or equiv <= 0:
        return 0

    cap = getattr(f, "max_colis_base", None) or MAX_CAPACITE_PAR_VOL
    if cap is not None and cap > 0:
        equiv_effectif = min(equiv, cap)
    else:
        equiv_effectif = equiv

    if MAX_EQUIV_PER_VOLUNTEER and MAX_EQUIV_PER_VOLUNTEER > 0:
        need = max(1, math.ceil(equiv_effectif / MAX_EQUIV_PER_VOLUNTEER))
    else:
        need = 1

    if MAX_BENEV_PER_VOL is not None:
        need = min(need, MAX_BENEV_PER_VOL)

    return max(0, need)


def _precompute_nb_options(
    flights: List[Flight],
    volunteers: List[Volunteer],
) -> Dict[int, int]:
    """
    Pour chaque Volunteer, calcule le nombre de vols compatibles.
    Clé = id(v), valeur = nb de vols possibles.
    """
    nb_options: Dict[int, int] = {}
    for v in volunteers:
        c = 0
        for f in flights:
            if _vol_fits_in_dispo(f, v):
                c += 1
        nb_options[id(v)] = c
    return nb_options


def _init_stats_by_id(volunteers: List[Volunteer]):
    """
    Initialise les stats hebdo par ID bénévole.
    """
    stats = {}
    for v in volunteers:
        stats[v.id] = {
            "assigned_week": 0,
            "assigned_per_day": defaultdict(int),   # date -> nb vols ce jour
            "days": set(),                          # set(date)
            "flights_by_day": defaultdict(list),    # date -> List[Flight]
        }
    return stats


def _violates_limits_for_candidate(
    v: Volunteer,
    f: Flight,
    st: Dict,
) -> (bool, str):
    """
    Vérifie les limites Max_Exp_Semaine, Max_Exp_Jour, Max_Jours_Semaine,
    MIN_HOURS_BETWEEN_FLIGHTS et Attente_Max_Heures.
    Renvoie (violates: bool, reason: str)
    """
    # Hebdo
    if st["assigned_week"] >= v.max_exped_semaine:
        return True, "Max_Exp_Semaine atteint"

    # Jour
    if st["assigned_per_day"][v.date] >= v.max_exped_jour:
        return True, "Max_Exp_Jour atteint"

    # Nb de jours distincts
    if len(st["days"]) >= v.max_jours_semaine and v.date not in st["days"]:
        return True, "Max_Jours_Semaine atteint"

    # Écart minimal entre vols le même jour
    t_dep = f.departure_time or DEFAULT_FLIGHT_TIME
    for f_other in st["flights_by_day"][v.date]:
        t_other = f_other.departure_time or DEFAULT_FLIGHT_TIME
        dh = abs(
            (datetime.combine(v.date, t_dep) - datetime.combine(v.date, t_other))
            .total_seconds()
        ) / 3600.0
        if dh < MIN_HOURS_BETWEEN_FLIGHTS:
            return True, f"Ecart < {MIN_HOURS_BETWEEN_FLIGHTS}h"

    # Attente max (mission globale sur la journée)
    if v.attente_max_h is not None:
        times = [
            (f_other.departure_time or DEFAULT_FLIGHT_TIME)
            for f_other in st["flights_by_day"][v.date]
        ]
        times.append(t_dep)

        earliest_start = min(
            datetime.combine(v.date, t) - timedelta(hours=DUREE_MISSION_HEURES)
            for t in times
        )
        latest_end = max(
            datetime.combine(v.date, t)
            for t in times
        )

        total_hours = (latest_end - earliest_start).total_seconds() / 3600.0
        if total_hours > float(v.attente_max_h):
            return True, f"Attente max > {v.attente_max_h}h"

    return False, "OK"


def _score_candidate(
    v: Volunteer,
    f: Flight,
    nb_options_map: Dict[int, int],
    stats_by_id: Dict[str, Dict],
    rarity_mode: int,
) -> float:
    """
    Calcule un score pour un bénévole candidat sur un vol.
    Objectifs :
      - priorité forte aux bénévoles avec peu d'options (rareté)
      - priorité à ceux sans mission semaine
      - pénalité soft si déjà plusieurs vols
      - randomisation légère
    """
    st = stats_by_id.get(v.id, {})
    assigned_week = st.get("assigned_week", 0)
    nb_options = nb_options_map.get(id(v), 0)

    score = 0.0

    # Bonus selon priorité rareté
    # rarity_mode : 1 = fort, 2 = moyen, 3 = léger
    if rarity_mode == 1:
        base_rare = 1000.0
    elif rarity_mode == 2:
        base_rare = 100.0
    else:
        base_rare = 10.0

    if nb_options <= 0:
        rare_bonus = 0.0
    elif nb_options == 1:
        rare_bonus = base_rare
    elif nb_options <= 3:
        rare_bonus = base_rare * 0.5
    else:
        rare_bonus = base_rare / (nb_options + 1)

    score += rare_bonus

    # Priorité à ceux qui n'ont encore aucun vol semaine
    if assigned_week == 0:
        score += 200.0

    # Soft équité : petite pénalité par vol déjà affecté
    score -= 10.0 * assigned_week

    # Légère randomisation pour casser les égalités
    score += random.uniform(-5.0, 5.0)

    return score


# =====================================================================
# PRÉ-CALCUL CAPACITÉ PAR VOL (AVANT PLACEMENT DES BE)
# =====================================================================

def precompute_flight_capacity_from_volunteers(
    flights: List[Flight],
    volunteers: List[Volunteer],
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Pré-calcul "statique" : pour chaque vol, on regarde quels bénévoles
    sont compatibles (fenêtre horaire uniquement, sans appliquer les
    limites hebdomadaires), et on en déduit une capacité équivalente
    théorique :

        cap_benev_equiv = nb_candidats_effectifs * MAX_EQUIV_PER_VOLUNTEER

    Puis on la borne par la capacité ParamDest du vol :

        cap_final = min(cap_benev_equiv, f.max_colis_base or MAX_CAPACITE_PAR_VOL)

    Effets de bord utiles :
      - ajoute sur chaque Flight :
            f.benev_candidates      (List[Volunteer])
            f.benev_nb_candidates   (int)
            f.benev_capacity_equiv  (int)
    Retour :
      - un DataFrame récapitulatif (Flight, date, heure, nb_candidats, cap_equiv, max_colis_base)
    """

    rows = []

    if not flights:
        if verbose:
            print("\n=== PRE-CALCUL CAPACITÉ BÉNÉVOLES PAR VOL ===")
            print("Aucun vol fourni.")
            print("=============================================\n")
        return pd.DataFrame()

    for f in flights:
        t_dep = f.departure_time or DEFAULT_FLIGHT_TIME

        # Bénévoles compatibles uniquement sur la base de la fenêtre horaire
        candidates = [v for v in volunteers if _vol_fits_in_dispo(f, v)]
        nb_cand = len(candidates)

        # Limite éventuelle du nombre de bénévoles par vol
        if MAX_BENEV_PER_VOL is not None:
            nb_effectif = min(nb_cand, MAX_BENEV_PER_VOL)
        else:
            nb_effectif = nb_cand

        # Capacité purement bénévole
        cap_benev_equiv = nb_effectif * MAX_EQUIV_PER_VOLUNTEER

        # Capacité ParamDest / fallback globale
        cap_param = getattr(f, "max_colis_base", None)
        if cap_param is None:
            cap_param = MAX_CAPACITE_PAR_VOL

        if cap_param is not None:
            cap_final = min(cap_benev_equiv, cap_param)
        else:
            cap_final = cap_benev_equiv

        # Injection sur l'objet Flight (attributs dynamiques)
        f.benev_candidates = candidates
        f.benev_nb_candidates = nb_cand
        f.benev_capacity_equiv = int(cap_final) if cap_final is not None else 0

        rows.append({
            "Flight_Number": f.flight_number,
            "Date": f.date,
            "Heure": t_dep,
            "Nb_Benevoles_Compatibles": nb_cand,
            "Nb_Benevoles_Effectifs": nb_effectif,
            "Cap_Equiv_Benevoles": cap_benev_equiv,
            "Cap_ParamDest": cap_param,
            "Cap_Equiv_Final": f.benev_capacity_equiv,
        })

    df = pd.DataFrame(rows)

    if verbose:
        print("\n=== PRE-CALCUL CAPACITÉ BÉNÉVOLES PAR VOL ===")
        try:
            # Petit aperçu trié par date + heure
            df_sorted = df.sort_values(["Date", "Heure", "Flight_Number"])
            print(df_sorted.head(30))
        except Exception:
            print(df)
        print("=============================================\n")

    return df


# =====================================================================
# AFFECTATION BÉNÉVOLES → VOLS (APRÈS PLACEMENT DES BE)
# =====================================================================

def assign_volunteers_to_flights(
    flights: List[Flight],
    volunteers: List[Volunteer],
    rarity_mode: int = 1,
    seed_override: Optional[int] = None,
) -> pd.DataFrame:
    """
    Affecte des bénévoles aux vols (uniquement ceux qui transportent des BE),
    en respectant les contraintes horaires / limites individuelles et en
    appliquant un scoring intelligent.

    Retourne un DataFrame df_debug documentant chaque candidat :
      - flight_id, benev_id, score, nb_options, respects_limits, reason_rejected,
        selected, target_rank, target_needed, etc.
    """

    print("\n=== AFFECTATION BÉNÉVOLES (INTELLIGENT + DEBUG) ===")
    df_rows = []

    if not flights or not volunteers:
        print("Aucun vol ou aucun bénévole à traiter.")
        return pd.DataFrame()

    # 🔎 Filtre : ne garder que les vols qui transportent au moins 1 BE
    flights_with_be = [
        f for f in flights
        if getattr(f, "shipments", None) and len(f.shipments) > 0
    ]

    print(f"➡ Vols totaux reçus : {len(flights)}")
    print(f"➡ Vols avec BE (utilisés pour les bénévoles) : {len(flights_with_be)}")

    if not flights_with_be:
        print("❗ Aucun vol avec BE — aucune affectation bénévole effectuée.")
        return pd.DataFrame()

    # Seed stable par semaine (basé sur la première date de vol)
    first_date = min(f.date for f in flights_with_be if f.date is not None)
    if seed_override is not None:
        print(f"[SIMU] Override random seed = {seed_override}")
        random.seed(seed_override)
    else:
        base_seed = int(first_date.strftime("%Y%W"))
        print(f"[REAL] Weekly seed = {base_seed}")
        random.seed(base_seed)

    # Pré-calcul nb d'options par bénévole
    nbopt = _precompute_nb_options(flights_with_be, volunteers)
    stats_by_id = _init_stats_by_id(volunteers)

    # Tri des vols par charge décroissante, puis date + heure
    flights_sorted = sorted(
        flights_with_be,
        key=lambda f: (
            -_estimate_flight_load(f),
            f.date,
            f.departure_time or DEFAULT_FLIGHT_TIME,
        ),
    )

    for f in flights_sorted:
        t_dep = f.departure_time or DEFAULT_FLIGHT_TIME
        target = _estimate_target_volunteers(f)

        # Si aucun bénévole requis (ex : pas de charge réelle)
        if target <= 0:
            f.assigned_volunteers = []
            continue

        flight_id = f"{f.flight_number}_{f.date}"
        load_val = _estimate_flight_load(f)

        print(
            f"\n> VOL {f.flight_number} {f.date} {t_dep} "
            f"— charge={load_val:.2f} → besoin {target}"
        )

        # Candidats compatibles (fenêtre horaire + limites)
        raw_candidates = []

        for v in volunteers:
            # Fenêtre horaire
            if not _vol_fits_in_dispo(f, v):
                df_rows.append({
                    "flight_id": flight_id,
                    "flight_number": f.flight_number,
                    "flight_date": f.date,
                    "departure_time": t_dep,
                    "benev_id": v.id,
                    "benev_name": v.benevole,
                    "score": None,
                    "nb_options": nbopt.get(id(v), 0),
                    "assigned_week": stats_by_id[v.id]["assigned_week"],
                    "respects_limits": False,
                    "reason_rejected": "Fenêtre horaire incompatible",
                    "selected": False,
                    "target_rank": None,
                    "target_needed": target,
                })
                continue

            violates, reason = _violates_limits_for_candidate(v, f, stats_by_id[v.id])
            if violates:
                df_rows.append({
                    "flight_id": flight_id,
                    "flight_number": f.flight_number,
                    "flight_date": f.date,
                    "departure_time": t_dep,
                    "benev_id": v.id,
                    "benev_name": v.benevole,
                    "score": None,
                    "nb_options": nbopt.get(id(v), 0),
                    "assigned_week": stats_by_id[v.id]["assigned_week"],
                    "respects_limits": False,
                    "reason_rejected": reason,
                    "selected": False,
                    "target_rank": None,
                    "target_needed": target,
                })
                continue

            sc = _score_candidate(v, f, nbopt, stats_by_id, rarity_mode)
            raw_candidates.append((sc, v))

            df_rows.append({
                "flight_id": flight_id,
                "flight_number": f.flight_number,
                "flight_date": f.date,
                "departure_time": t_dep,
                "benev_id": v.id,
                "benev_name": v.benevole,
                "score": sc,
                "nb_options": nbopt.get(id(v), 0),
                "assigned_week": stats_by_id[v.id]["assigned_week"],
                "respects_limits": True,
                "reason_rejected": "OK",
                "selected": False,
                "target_rank": None,
                "target_needed": target,
            })

        if not raw_candidates:
            print("  Aucun bénévole compatible.")
            f.assigned_volunteers = []
            continue

        # Tri des candidats par score décroissant
        raw_candidates.sort(key=lambda x: x[0], reverse=True)

        selected: List[Volunteer] = []

        for rank, (sc, v) in enumerate(raw_candidates, start=1):
            if len(selected) >= target:
                break

            # Re-vérification des limites, car elles changent à chaque sélection
            violates, reason = _violates_limits_for_candidate(v, f, stats_by_id[v.id])
            if violates:
                # MAJ des lignes debug correspondantes
                for r in df_rows:
                    if r["flight_id"] == flight_id and r["benev_id"] == v.id:
                        r["respects_limits"] = False
                        r["reason_rejected"] = reason
                continue

            selected.append(v)

            # Mise à jour des stats
            st = stats_by_id[v.id]
            st["assigned_week"] += 1
            st["assigned_per_day"][v.date] += 1
            st["days"].add(v.date)
            st["flights_by_day"][v.date].append(f)

            # Mise à jour dans l'objet Volunteer
            if not hasattr(v, "assigned_flights"):
                v.assigned_flights = []
            v.assigned_flights.append(f)

            # MAJ debug
            for r in df_rows:
                if r["flight_id"] == flight_id and r["benev_id"] == v.id:
                    r["selected"] = True
                    r["target_rank"] = rank

        f.assigned_volunteers = selected
        noms = ", ".join(v.benevole for v in selected)
        print(f"  -> Sélection : {len(selected)} bénévole(s) : {noms}")

    # Construction du DataFrame DEBUG
    df_debug = pd.DataFrame(df_rows)

    print("\n=== TABLEAU DEBUG AFFECTATION ===")
    try:
        print(df_debug.head(20))
    except Exception:
        pass
    print("===================================\n")

    return df_debug
