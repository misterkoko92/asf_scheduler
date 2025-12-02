# scheduler/engine.py
# -*- coding: utf-8 -*-
"""
Moteur unifié de planification ASF :
  - Pré-match vols ↔ bénévoles (capacité bénévole par vol)
  - Packing BE → vols (avec ParamDest, jours OK, fréquence, capacité)
  - Affectation réelle bénévoles → vols (moteur intelligent existant)
  - Ajustement final des BE selon capacité bénévole réelle
  - Construction Planning & Bilan
"""

from __future__ import annotations

from typing import List, Dict, Tuple, Any, Optional
from collections import defaultdict, Counter
from datetime import date, time

import pandas as pd

from scheduler.models import Shipment, Flight, Volunteer
from scheduler import config
from scheduler.flight_manager import (
    DestinationRule,
    load_dest_rules,
    get_week_key,
    is_flight_allowed_for_dest,
)
from scheduler import volunteer_manager


# =====================================================================
# HELPERS BÉNÉVOLES / CAPACITÉ PAR VOL
# =====================================================================

def _flight_key(f: Flight) -> Tuple[str, date]:
    """Clé unique pour un vol."""
    return f.flight_number, f.date


def precompute_flight_volunteer_candidates(
    flights: List[Flight],
    volunteers: List[Volunteer],
) -> None:
    """
    Pour chaque vol, calcule la liste des bénévoles qui ont une
    fenêtre horaire compatible (sans utiliser encore les limites
    hebdomadaires / journalières).

    Ajoute sur chaque Flight :
      - .candidate_volunteers : List[Volunteer]
      - .predicted_equiv_capacity : int (équivalent colis maximum estimé)
    """

    print("\n=== PRECOMPUTE VOL ↔ BÉNÉVOLES ===")

    cand_by_fkey: Dict[Tuple[str, date], List[Volunteer]] = defaultdict(list)

    for v in volunteers:
        for f in flights:
            if volunteer_manager._vol_fits_in_dispo(f, v):
                cand_by_fkey[_flight_key(f)].append(v)

    for f in flights:
        fk = _flight_key(f)
        candidates = cand_by_fkey.get(fk, [])
        f.candidate_volunteers = candidates

        nb_cand = len(candidates)
        predicted = 0
        if nb_cand > 0 and config.MAX_EQUIV_PER_VOLUNTEER is not None:
            # Limite max bénévoles par vol (si renseignée)
            max_benev = config.MAX_BENEV_PER_VOL or nb_cand
            effective_benev = min(nb_cand, max_benev)
            predicted = effective_benev * config.MAX_EQUIV_PER_VOLUNTEER

        # Capacité physique du vol (ParamDest)
        if f.max_colis_base is not None and f.max_colis_base > 0:
            predicted = min(predicted, f.max_colis_base)

        f.predicted_equiv_capacity = predicted

    # DEBUG
    for f in flights[:15]:
        print(
            f" - Vol {f.flight_number} {f.date} {f.departure_time} | "
            f"cand_benev={len(getattr(f, 'candidate_volunteers', []))} | "
            f"cap_predite={getattr(f, 'predicted_equiv_capacity', 0)} | "
            f"cap_physique={f.max_colis_base}"
        )
    print("====================================\n")


# =====================================================================
# PACKING BE → VOLS (intègre ParamDest + capacité bénévole prédite)
# =====================================================================

def pack_shipments_for_destination_engine(
    dest: str,
    shipments: List[Shipment],
    flights: List[Flight],
    dest_rules: Dict[str, DestinationRule],
    dest_usage: Dict[Any, int],
    day_usage: Dict[Any, int],
    chosen_dest: Dict[Tuple[str, date], Optional[str]],
) -> List[Shipment]:
    """
    Affecte les shipments d'une destination donnée sur les vols compatibles.

    Différences / améliorations :
      - n'utilise que les vols qui ont au moins 1 bénévole candidat
      - respecte .predicted_equiv_capacity (capacité bénévole + ParamDest)
      - corrige la logique Freq_Semaine :
            * on NE bloque que l'ouverture de nouveaux vols
            * on peut continuer à charger les vols déjà utilisés par la dest
      - routing, jours autorisés, MAX_BE_PER_FLIGHT inchangés
    """

    dest_u = dest.upper()
    print(f"\n--- PACK DEST (ENGINE) {dest_u} ---")

    remaining = [s for s in shipments if s.dest.upper() == dest_u]
    remaining.sort(key=lambda s: (s.priority, -s.nb_colis_physiques))

    rule = dest_rules.get(dest_u, None)

    if not remaining:
        print(f"   Aucun BE pour {dest_u}.")
        return []

    print(f"   BE à traiter pour {dest_u} : {len(remaining)}")

    unplanned: List[Shipment] = []
    placed_count = 0

    for s in remaining:

        units = s.equiv_colis if s.equiv_colis > 0 else s.nb_colis_physiques
        placed = False

        exp_u = (s.expediteur or "").strip().upper()

        def _has_same_expediteur(f: Flight) -> bool:
            if not exp_u:
                return False
            return any((getattr(sh, "expediteur", "") or "").strip().upper() == exp_u for sh in f.shipments)

        candidate_flights = sorted(
            flights,
            key=lambda f: (
                # 1) Priorité aux vols déjà utilisés par cette destination
                0 if chosen_dest.get(_flight_key(f)) == dest_u else 1,
                # 2) Ensuite préférer un vol où cet expéditeur est déjà présent
                0 if _has_same_expediteur(f) else 1,
                # 3) Puis critères temporels/classiques
                get_week_key(f.date),
                f.total_colis,
                f.date,
                f.departure_time or config.DEFAULT_FLIGHT_TIME,
            ),
        )

        for f in candidate_flights:

            fk = _flight_key(f)
            wk = get_week_key(f.date)
            current_chosen = chosen_dest.get(fk)

            # 0) Vol sans bénévole ou sans capacité prédite → on ignore
            cand_benev = getattr(f, "candidate_volunteers", [])
            cap_pred = getattr(f, "predicted_equiv_capacity", 0)

            if not cand_benev or cap_pred <= 0:
                continue

            # 1) Routing compatible ?
            if dest_u not in [x.upper() for x in (f.routing or [])]:
                continue

            # 2) Jours autorisés ParamDest
            if not is_flight_allowed_for_dest(f, dest_u, rule):
                continue

            # 3) Freq_semaine corrigée :
            #    - si on a atteint la fréquence max,
            #      on n'ouvre PAS de nouveau vol,
            #      mais on peut continuer à utiliser les vols déjà choisis.
            freq_used = dest_usage.get((dest_u, wk), 0)
            if rule and rule.freq_semaine > 0:
                if current_chosen is None and freq_used >= rule.freq_semaine:
                    # Vol encore vierge pour cette destination, et on a déjà
                    # atteint le nb max de vols cette semaine → on saute.
                    continue

            # 4) Capacité équivalente (bénévole + ParamDest)
            # total_colis est géré en "équivalent"
            cap_equiv = cap_pred
            if cap_equiv is not None and cap_equiv > 0:
                remaining_capacity = cap_equiv - f.total_colis
                if units > max(remaining_capacity, 0):
                    continue

            # 5) Max BE distincts par vol
            if config.MAX_BE_PER_FLIGHT and len(f.shipments) >= config.MAX_BE_PER_FLIGHT:
                continue

            # ---- Affectation ---
            f.add_shipment(s)
            placed = True
            placed_count += 1

            # Verrouillage de la destination pour ce vol
            if current_chosen is None:
                chosen_dest[fk] = dest_u
                dest_usage[(dest_u, wk)] = freq_used + 1
            else:
                # déjà compté dans la fréquence, on ne modifie pas
                dest_usage[(dest_u, wk)] = freq_used

            # Stat jour
            dk = (dest_u, wk, f.date.weekday())
            day_usage[dk] = day_usage.get(dk, 0) + 1

            break

        if not placed:
            s.reason_not_planned = "Aucune combinaison possible"
            unplanned.append(s)

    print(
        f"   ➜ {dest_u} : "
        f"{placed_count} BE placés, {len(unplanned)} BE non planifiés (ENGINE)."
    )

    return unplanned


def pack_all_destinations_engine(
    shipments: List[Shipment],
    flights: List[Flight],
    dest_rules: Dict[str, DestinationRule],
) -> Tuple[List[Flight], List[Shipment]]:
    """
    Packing global BE → vols basé sur la capacité bénévole prédite.

    - utilise pack_shipments_for_destination_engine() pour chaque dest
    - gère :
        * Freq_Semaine corrigée
        * jours autorisés
        * capacité ParamDest + capacité bénévole
        * MAX_BE_PER_FLIGHT
        * exclusivité "une destination ASF par vol"
    """

    print("\n=== PACK_ALL_DESTINATIONS (ENGINE) ===")

    dest_usage: Dict[Any, int] = {}
    day_usage: Dict[Any, int] = {}

    chosen_dest: Dict[Tuple[str, date], Optional[str]] = {
        _flight_key(f): getattr(f, "chosen_destination", None)
        for f in flights
    }

    all_unplanned: List[Shipment] = []

    ordered_dests = sorted({s.dest.upper() for s in shipments})

    print(f"Destinations à traiter (ENGINE) : {ordered_dests}")

    for dest in ordered_dests:
        unp = pack_shipments_for_destination_engine(
            dest=dest,
            shipments=shipments,
            flights=flights,
            dest_rules=dest_rules,
            dest_usage=dest_usage,
            day_usage=day_usage,
            chosen_dest=chosen_dest,
        )
        all_unplanned.extend(unp)

    # Injection destination choisie dans chaque vol
    for f in flights:
        f.chosen_destination = chosen_dest.get(_flight_key(f))

    print("\n=== RÉSUMÉ PACKING (ENGINE) ===")
    print(f"➡ BE non planifiés (toutes dest) : {len(all_unplanned)}")
    if all_unplanned:
        for s in all_unplanned[:10]:
            print(
                f" - BE {s.be_numero} | Dest={s.dest} | "
                f"Equiv={s.equiv_colis} | Raison={s.reason_not_planned}"
            )
        if len(all_unplanned) > 10:
            print(f"   ... (+{len(all_unplanned) - 10} autres)")
    print("====================================\n")

    return flights, all_unplanned


# =====================================================================
# AJUSTEMENT FINAL PAR CAPACITÉ BÉNÉVOLE RÉELLE
# =====================================================================

def apply_real_volunteer_capacity(
    flights: List[Flight],
    shipments_unplanned: List[Shipment],
) -> Tuple[List[Flight], List[Shipment]]:
    """
    Après affectation réelle des bénévoles, ajuste les BE sur chaque vol
    selon la capacité bénévole réelle :

      - si aucun bénévole sur un vol ⇒ tous les BE basculent en non-planifiés
      - sinon on garde les BE (triés par priorité + gros colis d'abord)
        tant que Σ equiv ≤ nb_benev * MAX_EQUIV_PER_VOLUNTEER
      - le reste est passé en "Capacité bénévole insuffisante"
    """

    print("\n=== AJUSTEMENT CAPACITÉ BÉNÉVOLES (ENGINE) ===")

    overflow: List[Shipment] = []

    for f in flights:

        shipments = list(getattr(f, "shipments", []) or [])
        if not shipments:
            continue

        volunteers = list(getattr(f, "assigned_volunteers", []) or [])

        if not volunteers:
            # Aucun bénévole pour ce vol ⇒ tout déborde
            for s in shipments:
                s.reason_not_planned = "Aucun bénévole disponible"
                overflow.append(s)
            f.shipments = []
            f.total_colis = 0
            continue

        if config.MAX_EQUIV_PER_VOLUNTEER is None:
            # pas de limite ⇒ on garde tout
            continue

        cap_equiv = len(volunteers) * config.MAX_EQUIV_PER_VOLUNTEER

        equiv_map: Dict[str, int] = {
            s.uid: int(getattr(s, "equiv_colis", s.nb_colis_physiques))
            for s in shipments
        }

        kept: List[Shipment] = []
        used_equiv = 0

        # priorité croissante, puis gros colis d'abord
        for s in sorted(shipments, key=lambda x: (x.priority, -equiv_map[x.uid])):
            need = equiv_map[s.uid]
            if used_equiv + need <= cap_equiv:
                kept.append(s)
                used_equiv += need
            else:
                s.reason_not_planned = "Capacité bénévole insuffisante"
                overflow.append(s)

        f.shipments = kept
        f.total_colis = used_equiv

        print(
            f"[ENGINE CAPACITÉ] Vol {f.flight_number} {f.date} | "
            f"Nb_bénévoles={len(volunteers)} | Cap_equiv={cap_equiv} | "
            f"Equiv_utilisé={used_equiv} | BE_retenus={len(kept)} | "
            f"BE_rejetés={len(shipments) - len(kept)}"
        )

    shipments_unplanned.extend(overflow)
    print(f"➡ BE non planifiés après capacité bénévole réelle : {len(overflow)}\n")

    return flights, shipments_unplanned


# =====================================================================
# CONSTRUCTION PLANNING / BILAN
# =====================================================================

def build_planning_df_engine(flights: List[Flight]) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []

    for f in flights:
        shipments = list(getattr(f, "shipments", []) or [])
        if not shipments:
            continue

        volunteers = list(getattr(f, "assigned_volunteers", []) or [])
        if not volunteers:
            # Normalement filtré avant, mais on sécurise
            continue

        # Répartition interne BE → bénévoles (équilibrage charge)
        load_map: Dict[str, int] = {v.id: 0 for v in volunteers}

        equiv_map: Dict[str, int] = {
            s.uid: int(getattr(s, "equiv_colis", s.nb_colis_physiques))
            for s in shipments
        }

        selected_ordered = sorted(
            shipments,
            key=lambda x: equiv_map[x.uid],
            reverse=True,
        )

        for s in selected_ordered:
            candidates_sorted = sorted(
                volunteers,
                key=lambda v: load_map[v.id],
            )

            chosen = candidates_sorted[0]
            load_map[chosen.id] += equiv_map[s.uid]

            rows.append({
                "UID": s.uid,
                "Date_Vol": f.date,
                "Heure_Vol": f.departure_time.strftime("%H:%M")
                if f.departure_time else "",
                "Vol": f.flight_number,
                "Destination": getattr(f, "chosen_destination", None) or s.dest,
                "BE_Numero": s.be_numero,
                "BE_Nb_Colis": s.nb_colis_physiques,
                "BE_Nb_Equiv": equiv_map[s.uid],
                "Benevole": chosen.benevole,
                "ID": getattr(chosen, "id", ""),
                "BE_Expediteur": getattr(s, "expediteur", "") or getattr(s, "expediteur_mag", ""),
                "BE_Type": getattr(s, "type_colis", ""),
                "Telephone": getattr(chosen, "telephone", ""),
            })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(
            ["Date_Vol", "Heure_Vol", "Vol", "Destination", "BE_Numero"]
        )

    print(f"➡ Lignes planning (ENGINE) : {len(df)}")
    return df


def build_bilan_df_engine(
    shipments_all: List[Shipment],
    unplanned: List[Shipment],
) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    unplanned_set = {s.uid for s in unplanned}

    for s in shipments_all:
        if s.uid not in unplanned_set and s.assigned_flight:
            f = s.assigned_flight
            rows.append({
                "UID": s.uid,
                "Date_Vol": f.date,
                "Vol": f.flight_number,
                "Destination": getattr(f, "chosen_destination", None) or s.dest,
                "BE_Numero": s.be_numero,
                "Nb_Colis": s.nb_colis_physiques,
                "Nb_Equiv": getattr(s, "equiv_colis", s.nb_colis_physiques),
                "Partant": "OUI",
                "Raison": "OK",
            })

    for s in unplanned:
        rows.append({
            "UID": s.uid,
            "Date_Vol": "",
            "Vol": "",
            "Destination": s.dest,
            "BE_Numero": s.be_numero,
            "Nb_Colis": s.nb_colis_physiques,
            "Nb_Equiv": getattr(s, "equiv_colis", s.nb_colis_physiques),
            "Partant": "NON",
            "Raison": s.reason_not_planned or "Pas de vol adapté",
        })

    df = pd.DataFrame(rows)
    print(f"➡ Lignes bilan (ENGINE) : {len(df)}")
    return df


# =====================================================================
# RUN GLOBAL DU MOTEUR UNIFIÉ
# =====================================================================

def run_engine(
    *,
    shipments: List[Shipment],
    flights: List[Flight],
    volunteers: List[Volunteer],
    rarity_mode: int = 1,
    mode: str = "real",
    simulation_id: Optional[str] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """
    Exécution complète du moteur unifié à partir des objets déjà chargés.
    Retourne :
      - planning_df
      - bilan_df
      - run_stats (dict résumant l'exécution)
    """

    print("\n================ ENGINE ASF ================")
    print(f"Mode={mode} | rarity_mode={rarity_mode} | sim_id={simulation_id}")
    print(f"Shipments : {len(shipments)} | Vols : {len(flights)} | "
          f"Bénévoles : {len(volunteers)}")
    print("============================================\n")

    # 1) Règles destinations (jours OK, fréquences…)
    dest_rules = load_dest_rules()

    # 2) Pré-match vols ↔ bénévoles (capacité prédite par vol)
    precompute_flight_volunteer_candidates(flights, volunteers)

    # 3) Packing BE → vols, en tenant compte de la capacité prédite
    flights_packed, unplanned1 = pack_all_destinations_engine(
        shipments=shipments,
        flights=flights,
        dest_rules=dest_rules,
    )

    # 4) Affectation intelligente des bénévoles
    volunteer_manager.assign_volunteers_to_flights(
        flights=flights_packed,
        volunteers=volunteers,
        rarity_mode=rarity_mode,
    )

    # 5) Ajustement final selon capacité bénévole réelle
    flights_final, unplanned_all = apply_real_volunteer_capacity(
        flights=flights_packed,
        shipments_unplanned=unplanned1,
    )

    # 6) Construction planning + bilan
    planning_df = build_planning_df_engine(flights_final)
    bilan_df = build_bilan_df_engine(shipments, unplanned_all)

    # 7) Stats récap
    nb_planned = sum(
        1 for s in shipments
        if s.assigned_flight and s.uid not in {x.uid for x in unplanned_all}
    )
    nb_unplanned = len(unplanned_all)
    vols_with_be = [
        f for f in flights_final
        if getattr(f, "shipments", None) and len(f.shipments) > 0
    ]
    nb_vols_with_be = len(vols_with_be)
    benev_used = {
        v.id
        for f in flights_final
        for v in getattr(f, "assigned_volunteers", []) or []
    }
    nb_benev_used = len(benev_used)

    run_stats = {
        "mode": mode,
        "simulation_id": simulation_id,
        "rarity_mode": rarity_mode,
        "total_be": len(shipments),
        "be_planned": nb_planned,
        "be_unplanned": nb_unplanned,
        "vols_with_be": nb_vols_with_be,
        "benevoles_used": nb_benev_used,
    }

    print("\n=== RÉSUMÉ ENGINE ===")
    print(f"   BE totaux        : {len(shipments)}")
    print(f"   BE planifiés     : {nb_planned}")
    print(f"   BE non planifiés : {nb_unplanned}")
    print(f"   Vols utilisés    : {nb_vols_with_be}")
    print(f"   Bénévoles utilisés : {nb_benev_used}")
    print("=================================\n")

    print(f"➡ Planning (ENGINE) : {len(planning_df)} lignes")
    print(f"➡ Bilan    (ENGINE) : {len(bilan_df)} lignes")

    return planning_df, bilan_df, run_stats
