# scheduler/flight_manager.py
# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from typing import Dict, List, Optional, Tuple, Any

from scheduler.models import Shipment, Flight
from scheduler import config
from scheduler.config_paths import TABLEAU_DE_BORD, SHEET_PARAM_DEST
from loaders.universal_loader import load_and_normalize
from scheduler.column_map import column_map_param_dest


# =====================================================================
# DESTINATION RULES
# =====================================================================

@dataclass
class DestinationRule:
    dest: str
    freq_semaine: int
    allowed_weekdays: List[int]


def load_dest_rules() -> Dict[str, DestinationRule]:
    """
    Charge ParamDest et crée les règles de chaque destination :
       - freq_semaine
       - allowed_weekdays = [0,1,3] etc.
    """
    print("\n=== DEST_RULES ===")

    df = load_and_normalize(
        path=TABLEAU_DE_BORD,
        sheet_name=SHEET_PARAM_DEST,
        mapping=column_map_param_dest,
        header=0,
    ).fillna("")

    rules: Dict[str, DestinationRule] = {}

    mapping_jour = {
        "Freq_Lundi": 0,
        "Freq_Mardi": 1,
        "Freq_Mercredi": 2,
        "Freq_Jeudi": 3,
        "Freq_Vendredi": 4,
        "Freq_Samedi": 5,
        "Freq_Dimanche": 6,
    }

    for _, r in df.iterrows():
        dest = str(r.get("Dest_IATA", "")).strip().upper()
        if not dest:
            continue

        # fréquence hebdo
        try:
            freq = int(str(r.get("Freq_Semaine", "0")).strip())
        except Exception:
            freq = 0

        allowed = [
            wd for col, wd in mapping_jour.items()
            if str(r.get(col, "")).strip().lower() == "ok"
        ]

        rules[dest] = DestinationRule(
            dest=dest,
            freq_semaine=freq,
            allowed_weekdays=allowed,
        )

    print(f"➡ Destinations ParamDest : {len(rules)}")
    print("====================================\n")

    return rules


# =====================================================================
# HELPERS
# =====================================================================

def get_week_key(d: date) -> Tuple[int, int]:
    """Retourne (année_iso, semaine_iso)."""
    return d.isocalendar()[0], d.isocalendar()[1]


def is_flight_allowed_for_dest(
    flight: Flight,
    dest: str,
    rule: Optional[DestinationRule],
) -> bool:
    """
    Vérifie les jours autorisés pour une destination.
    """
    if rule is None:
        return False
    return flight.date.weekday() in rule.allowed_weekdays


# =====================================================================
# PACKING D’UNE DESTINATION
# =====================================================================

def pack_shipments_for_destination(
    dest: str,
    shipments: List[Shipment],
    flights: List[Flight],
    dest_rules: Dict[str, DestinationRule],
    max_be: int,
    dest_usage: Dict,
    day_usage: Dict,
    chosen_dest: Dict,
) -> List[Shipment]:
    """
    Affecte les shipments d'une destination donnée sur les vols compatibles.

    *** VERSION PATCHÉE ***
    → Utilise la capacité réelle bénévole : f.benev_capacity_equiv
    → Maximisation du remplissage
    """

    dest_u = dest.upper()
    print(f"\n--- PACK DEST {dest_u} ---")

    remaining = [s for s in shipments if s.dest.upper() == dest_u]

    # Tri : priorité croissante, puis gros colis d'abord
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

        # Tri PRIORISÉ :
        #  1) semaine
        #  2) charge actuelle (min d'abord → on remplit)
        #  3) date
        #  4) heure
        candidate_flights = sorted(
            flights,
            key=lambda f: (
                get_week_key(f.date),
                f.total_colis,   # charge actuelle
                f.date,
                f.departure_time or config.DEFAULT_FLIGHT_TIME,
            )
        )

        for f in candidate_flights:

            fk = (f.flight_number, f.date)
            wk = get_week_key(f.date)

            # 1) Routing compatible
            if dest_u not in [x.upper() for x in (f.routing or [])]:
                continue

            # 2) Exclusivité destination sur multi-escales
            current_chosen = chosen_dest.get(fk)
            if current_chosen is not None and current_chosen != dest_u:
                continue

            # 3) Jours autorisés ParamDest
            if not is_flight_allowed_for_dest(f, dest_u, rule):
                continue

            # 4) Fréquence hebdomadaire
            freq_used = dest_usage.get((dest_u, wk), 0)
            if rule and rule.freq_semaine > 0 and freq_used >= rule.freq_semaine:
                continue

            # 5) Capacité réelle bénévole (PRIORITAIRE)
            real_cap = getattr(f, "benev_capacity_equiv", None)
            if real_cap is None:
                # fallback ancienne logique
                real_cap = getattr(f, "max_colis_base", None)

            if real_cap is not None:
                remaining_capacity = real_cap - f.total_colis
                if units > max(remaining_capacity, 0):
                    continue

            # 6) Max BE distincts par vol
            if len(f.shipments) >= max_be:
                continue

            # ---- AFFECTATION EFFECTIVE ----
            f.add_shipment(s)

            # Verrouillage de la destination
            if current_chosen is None:
                chosen_dest[fk] = dest_u
                dest_usage[(dest_u, wk)] = freq_used + 1
            else:
                dest_usage[(dest_u, wk)] = freq_used

            dk = (dest_u, wk, f.date.weekday())
            day_usage[dk] = day_usage.get(dk, 0) + 1

            placed = True
            placed_count += 1
            break

        if not placed:
            s.reason_not_planned = "Aucune combinaison possible"
            unplanned.append(s)

    print(
        f"   ➜ {dest_u} : "
        f"{placed_count} BE placés, {len(unplanned)} BE non planifiés."
    )

    return unplanned


# =====================================================================
# PACKING GLOBAL
# =====================================================================

def pack_all_destinations(
    shipments: List[Shipment],
    flights: List[Flight],
    dest_rules: Dict[str, DestinationRule],
    max_be_per_flight: Optional[int] = None,
) -> Tuple[List[Flight], List[Shipment]]:
    """
    Affectation globale de tous les shipments sur les vols
    en utilisant la capacité réelle calculée par capacity_manager.
    """

    print("\n=== PACK_ALL_DESTINATIONS ===")

    max_be = max_be_per_flight or config.MAX_BE_PER_FLIGHT

    dest_usage: Dict[Any, int] = {}
    day_usage: Dict[Any, int] = {}
    chosen_dest: Dict[Tuple[str, date], Optional[str]] = {
        (f.flight_number, f.date): getattr(f, "chosen_destination", None)
        for f in flights
    }

    all_unplanned: List[Shipment] = []

    ordered_dests = sorted({s.dest.upper() for s in shipments})
    print(f"Destinations à traiter : {ordered_dests}")

    for dest in ordered_dests:
        unp = pack_shipments_for_destination(
            dest=dest,
            shipments=shipments,
            flights=flights,
            dest_rules=dest_rules,
            max_be=max_be,
            dest_usage=dest_usage,
            day_usage=day_usage,
            chosen_dest=chosen_dest,
        )
        all_unplanned.extend(unp)

    # Mise à jour finale de chosen_destination sur les vols
    for f in flights:
        fkey = (f.flight_number, f.date)
        f.chosen_destination = chosen_dest.get(fkey)

    print("\n=== RÉSUMÉ PACKING DESTINATIONS ===")
    print(f"➡ BE non planifiés (tous dest) : {len(all_unplanned)}")

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
