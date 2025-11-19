# scheduler/core_scheduler.py
# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple
import logging
import pandas as pd

from scheduler.models import Shipment, Flight, Volunteer
from scheduler import config
from scheduler import flight_manager, volunteer_manager, be_manager

from loaders.load_shipments import load_shipments
from loaders.load_benevoles import load_benevoles
from loaders.load_vols import load_vols

# ------------------------------------------------------------
# LOGGING CONFIGURATION
# ------------------------------------------------------------

logging.basicConfig(
    filename="asf_scheduler.log",
    filemode="a",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("ASF-SCHEDULER")

# ------------------------------------------------------------
# Helper : log full configuration
# ------------------------------------------------------------
def log_full_config():
    logger.info("=== CONFIGURATION ACTUELLE ===")
    logger.info(f"MAX_BE_PER_FLIGHT = {config.MAX_BE_PER_FLIGHT}")
    logger.info(f"MAX_EQUIV_PER_VOLUNTEER = {config.MAX_EQUIV_PER_VOLUNTEER}")
    logger.info(f"MAX_BENEV_PER_VOL = {config.MAX_BENEV_PER_VOL}")
    logger.info(f"DUREE_MISSION_HEURES = {config.DUREE_MISSION_HEURES}")
    logger.info(f"DEFAULT_FLIGHT_TIME = {config.DEFAULT_FLIGHT_TIME}")
    logger.info(f"MAX_CAPACITÉ_PAR_VOL = {config.MAX_CAPACITE_PAR_VOL}")
    logger.info("=============================================")


# ------------------------------------------------------------
#  SCHEDULER PRINCIPAL
# ------------------------------------------------------------

class Scheduler:

    def __init__(self):
        self.shipments: List[Shipment] = []
        self.flights: List[Flight] = []
        self.volunteers: List[Volunteer] = []

        logger.info("Initialisation du Scheduler (shipments/flights/volunteers vides).")

    # ------------------------------------------------------------
    # LOADING
    # ------------------------------------------------------------

    def load_shipments(self) -> None:
        logger.info("Début chargement des BE...")
        be_list = load_shipments()
        logger.info("BE bruts lus : %d", len(be_list))

        be_list = be_manager.filter_shipments(be_list)
        logger.info("BE après filtrage moteur : %d", len(be_list))

        be_list = be_manager.sort_shipments(be_list)
        logger.info("BE triés.")

        self.shipments = be_list
        print(f"➡ BE chargés : {len(self.shipments)}")
        logger.info("Chargement BE terminé.")

    def load_flights(self) -> None:
        logger.info("Début chargement des vols...")

        vols_list = load_vols()
        logger.info("Vols bruts : %d", len(vols_list))

        flights = []
        for r in vols_list:
            flights.append(
                Flight(
                    flight_number=str(r.get("flight_number", "")).zfill(4),
                    date=r.get("date"),
                    departure_time=r.get("departure_time"),
                    routing=r.get("routing", []),
                    max_colis_base=r.get("max_colis_base"),
                )
            )

        self.flights = flights
        print(f"➡ Vols chargés : {len(self.flights)}")
        logger.info("Vols construits : %d", len(self.flights))

    def load_volunteers(self) -> None:
        logger.info("Début chargement bénévoles...")

        df = load_benevoles()
        logger.info("Disponibilités bénévoles brutes : %d lignes", len(df))

        param = volunteer_manager.load_param_benev()
        logger.info(
            "Paramètres bénévoles chargés (%d lignes)",
            len(param) if hasattr(param, "__len__") else -1
        )

        volunteers = volunteer_manager.build_volunteers(df, param)
        self.volunteers = volunteers

        print(f"➡ Bénévoles utilisables : {len(self.volunteers)}")
        logger.info("Bénévoles construits : %d", len(self.volunteers))

    # ------------------------------------------------------------
    # PLANNING BE → VOLS
    # ------------------------------------------------------------

    def plan_shipments_on_flights(self) -> List[Shipment]:
        logger.info("Début planification BE -> vols...")

        rules = flight_manager.load_dest_rules()
        logger.info("Règles destination chargées : %d", len(rules) if rules else 0)

        flights_planned, unplanned = flight_manager.pack_all_destinations(
            shipments=self.shipments,
            flights=self.flights,
            dest_rules=rules,
            max_be_per_flight=config.MAX_BE_PER_FLIGHT,
        )

        # Log detailed BE assignment
        for f in flights_planned:
            for s in f.shipments:
                logger.info(
                    f"Affecté BE {s.be_numero} ({s.nb_colis_physiques} colis) -> Vol {f.flight_number} ({f.date})"
                )

        self.flights = flights_planned

        logger.info("Fin planification BE. Non planifiés : %d", len(unplanned))
        return unplanned

    # ------------------------------------------------------------
    # PLANNING VOLUNTEERS → FLIGHTS
    # ------------------------------------------------------------

    def assign_volunteers(self) -> None:
        logger.info("Début affectation bénévoles -> vols...")

        volunteer_manager.assign_volunteers_to_flights(
            flights=self.flights,
            volunteers=self.volunteers,
        )

        # Log detailed assignment
        for f in self.flights:
            for v in getattr(f, "assigned_volunteers", []):
                logger.info(
                    f"Bénévole {v.benevole} affecté au vol {f.flight_number} du {f.date}"
                )

        logger.info("Fin affectation bénévoles.")

    # ------------------------------------------------------------
    # EXPORT PLANNING
    # ------------------------------------------------------------

    def build_planning_df(self) -> pd.DataFrame:
        logger.info("Construction du DataFrame planning...")
        rows = []

        for f in self.flights:
            shipments = list(f.shipments)
            if not shipments:
                continue

            volunteers = getattr(f, "assigned_volunteers", [])

            # Pas de bénévole
            if not volunteers:
                for s in shipments:
                    rows.append({
                        "Date_Vol": f.date,
                        "Heure_Vol": f.departure_time.strftime("%H:%M"),
                        "Vol": f.flight_number,
                        "Destination": f.chosen_destination or s.dest,
                        "BE_Numero": s.be_numero,
                        "BE_Nb_Colis": s.nb_colis_physiques,
                        "BE_Nb_Equiv": s.nb_colis_physiques,
                        "Benevole": "",
                    })
                continue

            # Tri équiv-colis descending
            shipments_sorted = sorted(
                shipments,
                key=lambda s: getattr(s, "equiv_colis", s.nb_colis_physiques),
                reverse=True,
            )

            load = {v.id: 0 for v in volunteers}
            assignments = []

            for s in shipments_sorted:
                equiv = getattr(s, "equiv_colis", s.nb_colis_physiques)

                possible = sorted(
                    volunteers, key=lambda v: (load[v.id], v.benevole)
                )

                chosen = None
                for v in possible:
                    if load[v.id] + equiv <= config.MAX_EQUIV_PER_VOLUNTEER:
                        chosen = v
                        break

                if chosen is None:
                    chosen = min(volunteers, key=lambda v: load[v.id])

                assignments.append((s, chosen))
                load[chosen.id] += equiv

                logger.info(
                    f"Équilibrage : BE {s.be_numero} → bénévole {chosen.benevole}"
                )

            for s, v in assignments:
                rows.append({
                    "Date_Vol": f.date,
                    "Heure_Vol": f.departure_time.strftime("%H:%M"),
                    "Vol": f.flight_number,
                    "Destination": f.chosen_destination or s.dest,
                    "BE_Numero": s.be_numero,
                    "BE_Nb_Colis": s.nb_colis_physiques,
                    "BE_Nb_Equiv": getattr(s, "equiv_colis", s.nb_colis_physiques),
                    "Benevole": v.benevole,
                })

        df = pd.DataFrame(rows)
        logger.info("Planning final généré (%d lignes).", len(df))
        return df.sort_values(
            by=["Date_Vol", "Heure_Vol", "Vol", "Destination", "BE_Numero"]
        )

    # ------------------------------------------------------------
    # BILAN
    # ------------------------------------------------------------

    def build_bilan_df(self, unplanned: List[Shipment]) -> pd.DataFrame:
        logger.info("Construction du Bilan...")
        rows = []

        # Partants
        for s in self.shipments:
            if s.assigned_flight and s not in unplanned:
                f = s.assigned_flight
                rows.append({
                    "Date_Vol": f.date,
                    "Vol": f.flight_number,
                    "Destination": f.chosen_destination or s.dest,
                    "BE_Numero": s.be_numero,
                    "Nb_Colis": s.nb_colis_physiques,
                    "Nb_Equiv": getattr(s, "equiv_colis", s.nb_colis_physiques),
                    "Partant": "OUI",
                    "Raison": "OK",
                    "Benevole": getattr(s, "assigned_volunteer", None).benevole
                    if hasattr(s, "assigned_volunteer") else "",
                })

        # Non partants
        for s in unplanned:
            rows.append({
                "Date_Vol": "",
                "Vol": "",
                "Destination": s.dest,
                "BE_Numero": s.be_numero,
                "Nb_Colis": s.nb_colis_physiques,
                "Nb_Equiv": getattr(s, "equiv_colis", s.nb_colis_physiques),
                "Partant": "NON",
                "Raison": s.reason_not_planned or "Pas de vol adapté",
                "Benevole": "",
            })
            logger.warning(f"BE non planifié : {s.be_numero} ({s.dest})")

        df = pd.DataFrame(rows)
        logger.info("Bilan généré (%d lignes).", len(df))
        return df

    # ------------------------------------------------------------
    # RUN
    # ------------------------------------------------------------

    def run(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        print("=== PLANNING AUTOMATISÉ ===")
        logger.info("=== DÉBUT D’UNE NOUVELLE EXÉCUTION ===")

        try:
            # Log configuration first
            log_full_config()

            # Workflow
            print("➡ Chargement BE…")
            self.load_shipments()

            print("➡ Chargement vols…")
            self.load_flights()

            print("➡ Chargement bénévoles…")
            self.load_volunteers()

            print("➡ Affectation BE -> vols…")
            unplanned = self.plan_shipments_on_flights()

            print("➡ Affectation bénévoles…")
            self.assign_volunteers()

            print("➡ Génération Planning & Bilan…")
            planning = self.build_planning_df()
            bilan = self.build_bilan_df(unplanned)

            print(f"   Planning : {len(planning)} lignes")
            print(f"   Bilan    : {len(bilan)} lignes")

            logger.info("=== FIN EXÉCUTION ===")

            return planning, bilan

        except Exception as e:
            logger.exception("Erreur critique : %s", e)
            raise


# ------------------------------------------------------------
# LOG EXTERNE : ajout manuel BE
# ------------------------------------------------------------

def log_manual_be_action(be_num, dest, colis, type_colis, date, vol, benevole_list):
    """Log depuis l’UI lorsqu’un BE est ajouté manuellement."""
    logger.info(
        f"[AJOUT MANUEL] BE {be_num} / Dest {dest} / Colis {colis} / "
        f"Type {type_colis} / Date {date} / Vol {vol} / Bénévoles {benevole_list}"
    )
