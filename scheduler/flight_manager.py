# scheduler/flight_manager.py
# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Dict, List, Optional, Tuple, Any

import pandas as pd

from scheduler.models import Shipment, Flight
from scheduler import config

from scheduler.config_paths import (
    TABLEAU_DE_BORD,
    SHEET_PARAM_DEST,
    VOLS,
)


# ======================================================
#  RÈGLES DESTINATION (ParamDest)
# ======================================================

@dataclass
class DestinationRule:
    dest: str
    freq_semaine: int
    allowed_weekdays: List[int]  # 0 lundi … 6 dimanche


def load_dest_rules() -> Dict[str, DestinationRule]:
    """Charge ParamDest depuis TABLEAU_DE_BORD.xlsx."""

    df = pd.read_excel(
        TABLEAU_DE_BORD,
        sheet_name=SHEET_PARAM_DEST,
        dtype=str
    ).fillna("")

    mapping_jour = {
        "Lundi": 0, "Mardi": 1, "Mercredi": 2,
        "Jeudi": 3, "Vendredi": 4, "Samedi": 5, "Dimanche": 6
    }

    rules: Dict[str, DestinationRule] = {}

    for _, r in df.iterrows():
        dest = str(r.get("Destination", "")).strip().upper()
        if not dest:
            continue

        try:
            freq = int(str(r.get("Freq_Semaine", "0")).strip() or "0")
        except:
            freq = 0

        allowed = [
            wd for col, wd in mapping_jour.items()
            if str(r.get(col, "")).strip().lower() == "ok"
        ]

        rules[dest] = DestinationRule(dest, freq, allowed)

    return rules


# ======================================================
#  HELPERS
# ======================================================

def get_week_key(d: date) -> Tuple[int, int]:
    iso = d.isocalendar()
    return iso[0], iso[1]


def is_flight_allowed_for_dest(flight: Flight, dest: str, rule: DestinationRule) -> bool:
    """Retourne True si le vol est autorisé selon ParamDest."""
    weekday = flight.date.weekday()

    if len(rule.allowed_weekdays) == 0:
        return False

    return weekday in rule.allowed_weekdays


# ======================================================
#  PARSE DATE / HEURE
# ======================================================

def parse_date(v) -> date | None:
    try:
        return pd.to_datetime(v, dayfirst=True).date()
    except:
        return None


def parse_excel_time(v) -> time | None:
    if v is None or v == "":
        return None

    if isinstance(v, time):
        return v

    if isinstance(v, datetime):
        return v.time()

    if isinstance(v, str):
        s = v.strip()
        for fmt in ("%H:%M", "%H:%M:%S"):
            try:
                return datetime.strptime(s, fmt).time()
            except:
                pass
        try:
            return pd.to_datetime(s).time()
        except:
            pass

    # Excel float
    try:
        vf = float(v)
        total_seconds = int(vf * 24 * 3600)
        hh = total_seconds // 3600
        mm = (total_seconds % 3600) // 60
        ss = total_seconds % 60
        return time(hh, mm, ss)
    except:
        return None


def parse_routing(s) -> List[str]:
    if not isinstance(s, str):
        return []
    s = s.strip().strip("[]")
    return [
        x.strip().strip("'").strip('"')
        for x in s.split(",")
        if x.strip()
    ]


# ======================================================
#  LOAD VOLS
# ======================================================

def load_vols() -> List[Dict[str, Any]]:
    """
    Charge Vols.xlsx et applique ParamDest (capacités, IATA).
    """

    df_param = pd.read_excel(
        TABLEAU_DE_BORD,
        sheet_name=SHEET_PARAM_DEST,
        dtype=str
    ).fillna("")

    ville_to_iata: Dict[str, str] = {}
    iata_to_capacity: Dict[str, Optional[int]] = {}

    for _, r in df_param.iterrows():

        ville = str(r.get("Ville", "")).upper().strip()
        iata = str(r.get("Destination", "")).upper().strip()

        raw_cap = str(r.get("Max_Colis_Par_Vol", "")).strip()
        try:
            cap = int(raw_cap) if raw_cap else None
        except:
            cap = None

        if ville:
            ville_clean = (
                ville.replace("(CAMEROUN)", "")
                     .replace("(COTE D'IVOIRE)", "")
                     .replace(",", "")
                     .replace("É", "E")
                     .replace("È", "E")
                     .strip()
            )
            ville_to_iata[ville_clean] = iata

        if iata:
            iata_to_capacity[iata] = cap

    # Vols.xlsx
    df_vols = pd.read_excel(VOLS, dtype=str).fillna("")
    vols_dict: Dict[str, Dict[str, Any]] = {}

    for _, r in df_vols.iterrows():

        num = str(r.get("PVOL_NUMERO", "")).strip()
        d = parse_date(r.get("PVOL_DATE"))
        t = parse_excel_time(r.get("PVOL_HEURE"))
        ville_raw = str(r.get("PVOL_FK_DESTINATION", "")).upper().strip()
        routing = parse_routing(r.get("PVOL_ROUTE_API", ""))

        if d is None:
            continue
        if t is None:
            t = time(0, 0)

        ville_clean = (
            ville_raw.replace("(CAMEROUN)", "")
                     .replace("(COTE D'IVOIRE)", "")
                     .replace(",", "")
                     .replace("É", "E")
                     .replace("È", "E")
                     .strip()
        )

        iata = ville_to_iata.get(ville_clean, ville_to_iata.get(ville_raw))
        cap = iata_to_capacity.get(iata)

        flight_id = f"{num}_{d}"

        if flight_id not in vols_dict:
            vols_dict[flight_id] = {
                "flight_number": num.zfill(4),
                "date": d,
                "departure_time": t,
                "routing": routing,
                "max_colis_base": cap,
            }

    return list(vols_dict.values())


# ======================================================
#  PACKING SHIPMENTS → VOLS
# ======================================================

def pack_shipments_for_destination(
    dest: str,
    shipments: List[Shipment],
    flights: List[Flight],
    dest_rules: Dict[str, DestinationRule],
    max_be_per_flight: int,
    dest_usage_counter: Dict[Tuple[str, Tuple[int, int]], int],
    chosen_dest_by_flight: Dict[Tuple[str, date], Optional[str]],
) -> List[Shipment]:

    remaining = [s for s in shipments if s.dest.upper() == dest.upper()]
    remaining.sort(key=lambda s: (s.priority, -s.nb_colis_physiques))

    rule = dest_rules.get(dest.upper())
    unplanned: List[Shipment] = []

    for s in remaining:

        placed = False
        required_units = s.equiv_colis if s.equiv_colis > 0 else s.nb_colis_physiques

        any_candidate = False
        freq_blocked = False
        capacity_blocked = False
        maxbe_blocked = False

        for f in sorted(flights, key=lambda fl: (fl.date, fl.departure_time or config.DEFAULT_FLIGHT_TIME)):

            fkey = (f.flight_number, f.date)
            current_choice = chosen_dest_by_flight.get(fkey)

            # Routing
            if dest.upper() not in [x.upper() for x in (f.routing or [])]:
                continue

            # Verrou destination
            if current_choice is not None and current_choice.upper() != dest.upper():
                continue

            # Règle jour ParamDest
            if rule is None or not is_flight_allowed_for_dest(f, dest, rule):
                continue

            any_candidate = True

            # Fréquence hebdo
            week_key = get_week_key(f.date)
            counter_key = (dest.upper(), week_key)
            freq_used = dest_usage_counter.get(counter_key, 0)

            if freq_used >= rule.freq_semaine > 0:
                freq_blocked = True
                continue

            # Capacité équivalente
            if f.max_colis_base is not None:
                remain = max(f.max_colis_base - f.total_colis, 0)
                if required_units > remain:
                    capacity_blocked = True
                    continue

            # Max BE par vol
            if len(f.shipments) >= max_be_per_flight:
                maxbe_blocked = True
                continue

            # ================================
            #   PLACE LE BE → via f.add_shipment()
            # ================================
            f.add_shipment(s)

            if current_choice is None:
                chosen_dest_by_flight[fkey] = dest.upper()
                dest_usage_counter[counter_key] = freq_used + 1

            placed = True
            break

        if not placed:
            if not any_candidate:
                s.reason_not_planned = "Pas de vol compatible (routing/jour)"
            elif freq_blocked:
                s.reason_not_planned = "Fréquence hebdo atteinte"
            elif capacity_blocked:
                s.reason_not_planned = "Capacité insuffisante"
            elif maxbe_blocked:
                s.reason_not_planned = "Trop de BE sur ce vol"
            else:
                s.reason_not_planned = "Aucune combinaison possible"

            unplanned.append(s)

    return unplanned


def pack_all_destinations(
    shipments: List[Shipment],
    flights: List[Flight],
    dest_rules: Dict[str, DestinationRule],
    max_be_per_flight: Optional[int] = None,
):

    if max_be_per_flight is None:
        max_be_per_flight = config.MAX_BE_PER_FLIGHT

    dest_usage_counter: Dict[Tuple[str, Tuple[int, int]], int] = {}
    chosen_dest_by_flight = {(f.flight_number, f.date): f.chosen_destination for f in flights}

    all_unplanned: List[Shipment] = []

    ordered_dests = sorted({s.dest.upper() for s in shipments})

    for dest in ordered_dests:
        up = pack_shipments_for_destination(
            dest,
            shipments,
            flights,
            dest_rules,
            max_be_per_flight,
            dest_usage_counter,
            chosen_dest_by_flight,
        )
        all_unplanned.extend(up)

    # Mise à jour finale des destinations des vols
    for f in flights:
        fkey = (f.flight_number, f.date)
        f.chosen_destination = chosen_dest_by_flight.get(fkey)

    return flights, all_unplanned
