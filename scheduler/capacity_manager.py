# scheduler/capacity_manager.py
# -*- coding: utf-8 -*-
"""
capacity_manager.py — Calcul de la capacité réelle par vol en fonction
des bénévoles compatibles (fenêtre horaire uniquement, sans appliquer
les limites hebdo). À appeler AVANT le placement des BE.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List
import pandas as pd

from scheduler.models import Flight, Volunteer
from scheduler.config import (
    MAX_BENEV_PER_VOL,
    DUREE_MISSION_HEURES,
    MAX_EQUIV_PER_VOLUNTEER,
    MAX_CAPACITE_PAR_VOL,
    DEFAULT_FLIGHT_TIME,
)


# ================================================================
# Helper interne : fenêtre horaire
# ================================================================

def _vol_fits_in_dispo(f: Flight, v: Volunteer) -> bool:
    """
    Un bénévole peut assister un vol si :
      - même date
      - présent jusqu’à l'heure du vol
      - peut arriver au plus tard à (heure_vol - durée_mission)
    """
    if v.date != f.date:
        return False

    t_dep = f.departure_time or DEFAULT_FLIGHT_TIME

    mission_start = (
        datetime.combine(f.date, t_dep) - timedelta(hours=DUREE_MISSION_HEURES)
    ).time()

    # v.arrive <= mission_start <= v.depart >= vol
    return v.heure_arrivee <= mission_start and v.heure_depart >= t_dep


# ================================================================
# CALCUL PRINCIPAL — CAPACITÉ BÉNÉVOLES PAR VOL
# ================================================================

def compute_volunteer_capacity_for_flights(
    flights: List[Flight],
    volunteers: List[Volunteer],
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Pour chaque vol :
        1) Trouve les bénévoles compatibles (fenêtre horaire seulement)
        2) Applique MAX_BENEV_PER_VOL si défini
        3) Calcule :
              capacité bénévole = nb_effectifs * MAX_EQUIV_PER_VOLUNTEER
        4) Capacité finale = min(capacite_benevoles, f.max_colis_base)
        5) Ajoute les attributs sur l'objet Flight :
              - benev_candidates
              - benev_nb_candidates
              - benev_nb_effective
              - benev_capacity_equiv

    Renvoie un DataFrame pour debug.
    """

    rows = []

    if not flights:
        if verbose:
            print("\n=== CAPACITY MANAGER — AUCUN VOL ===\n")
        return pd.DataFrame()

    print("\n=== CAPACITY MANAGER — PRÉ-CALCUL CAPACITÉ BÉNÉVOLES PAR VOL ===")

    for f in flights:
        t_dep = f.departure_time or DEFAULT_FLIGHT_TIME

        # -------------------------------
        # 1) Bénévoles compatibles
        # -------------------------------
        candidates = [v for v in volunteers if _vol_fits_in_dispo(f, v)]
        nb_cand = len(candidates)

        # -------------------------------
        # 2) Limite du nombre de bénévoles
        # -------------------------------
        if MAX_BENEV_PER_VOL is not None:
            nb_effectifs = min(nb_cand, MAX_BENEV_PER_VOL)
        else:
            nb_effectifs = nb_cand

        # -------------------------------
        # 3) Capacité brute bénévole
        # -------------------------------
        cap_benev = nb_effectifs * MAX_EQUIV_PER_VOLUNTEER

        # -------------------------------
        # 4) Capacité ParamDest
        # -------------------------------
        cap_param = getattr(f, "max_colis_base", None)
        if cap_param is None:
            cap_param = MAX_CAPACITE_PAR_VOL

        # -------------------------------
        # 5) Capacité finale retenue
        # -------------------------------
        if cap_param is not None:
            cap_final = min(cap_benev, cap_param)
        else:
            cap_final = cap_benev

        # -------------------------------
        # Injection sur l'objet Flight
        # -------------------------------
        f.benev_candidates = candidates
        f.benev_nb_candidates = nb_cand
        f.benev_nb_effective = nb_effectifs
        f.benev_capacity_equiv = int(cap_final)

        rows.append({
            "Flight_Number": f.flight_number,
            "Destination": getattr(f, "destination", ""),
            "Date": f.date,
            "Heure": t_dep,
            "Nb_Benevoles_Compatibles": nb_cand,
            "Nb_Benevoles_Effectifs": nb_effectifs,
            "Cap_Benevoles_Est": cap_benev,
            "Cap_ParamDest": cap_param,
            "Cap_Equiv_Final": cap_final,
        })

    df = pd.DataFrame(rows)

    if verbose:
        try:
            df = df.sort_values(["Date", "Heure", "Flight_Number"])
        except Exception:
            pass

        print(df.to_string(index=False))

    print("=== FIN CAPACITY MANAGER ===\n")

    return df
