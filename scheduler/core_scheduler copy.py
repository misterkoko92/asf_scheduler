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
# LOGGING
# ------------------------------------------------------------

logging.basicConfig(
    filename="asf_scheduler.log",
    filemode="a",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("ASF-SCHEDULER")


# ------------------------------------------------------------
# SCHEDULER PRINCIPAL
# ------------------------------------------------------------

class Scheduler:

    def __init__(self):
        """
        Plus besoin d'objet Paths.
        Les chemins sont déjà centralisés dans config_paths.py
        """
        self.shipments: List[Shipment] = []
        self.flights: List[Flight] = []
        self.volunteers: List[Volunteer] = []

        logger.info("Initialisation du Scheduler (shipments/flights/volunteers vides).")

    # ------------------------------------------------------------
    # CHARGEMENT
    # ------------------------------------------------------------

    def load_shipments(self) -> None:
        """
        Charge les BE via loader + applique filtres & tri.
        """
        logger.info("Début chargement des BE...")
        be_list = load_shipments()
        logger.info("BE chargés depuis Excel : %d lignes brutes.", len(be_list))

        be_list = be_manager.filter_shipments(be_list)
        logger.info("BE après filtrage (statut, règles métier, etc.) : %d", len(be_list))

        be_list = be_manager.sort_shipments(be_list)
        logger.info("BE triés (ordre de priorité appliqué).")

        self.shipments = be_list
        print(f"➡ BE chargés et triés : {len(self.shipments)}")
        logger.info("BE chargés et triés : %d", len(self.shipments))

    def load_flights(self) -> None:
        logger.info("Début chargement des vols...")
        vols_list = load_vols()
        logger.info("Vols chargés depuis Excel : %d lignes brutes.", len(vols_list))

        flights = []
        for r in vols_list:
            flights.append(Flight(
                flight_number=str(r.get("flight_number", "")).zfill(4),
                date=r.get("date"),
                departure_time=r.get("departure_time"),
                routing=r.get("routing", []),
                max_colis_base=r.get("max_colis_base"),
            ))

        self.flights = flights
        print(f"➡ Vols chargés : {len(self.flights)}")
        logger.info("Vols construits (objets Flight) : %d", len(self.flights))

    def load_volunteers(self) -> None:
        """
        Charge les disponibilités + paramètres bénévoles.
        """
        logger.info("Début chargement des bénévoles...")
        df = load_benevoles()
        logger.info("Données brutes bénévoles : %d lignes.", len(df))

        param = volunteer_manager.load_param_benev()
        logger.info("Paramètres bénévoles chargés (%d lignes).", len(param) if hasattr(param, "__len__") else -1)

        volunteers = volunteer_manager.build_volunteers(df, param)
        self.volunteers = volunteers

        print(f"➡ Bénévoles utilisables : {len(self.volunteers)}")
        logger.info("Bénévoles construits (objets Volunteer) : %d", len(self.volunteers))

    # ------------------------------------------------------------
    # PLANNING BE
    # ------------------------------------------------------------

    def plan_shipments_on_flights(self) -> List[Shipment]:
        """
        Planifie les BE sur les vols disponibles.
        """
        logger.info("Début planification BE -> vols...")
        rules = flight_manager.load_dest_rules()
        logger.info("Règles destinations chargées : %d entrées.", len(rules) if rules is not None else -1)

        flights_planned, unplanned = flight_manager.pack_all_destinations(
            shipments=self.shipments,
            flights=self.flights,
            dest_rules=rules,
            max_be_per_flight=config.MAX_BE_PER_FLIGHT,
        )

        self.flights = flights_planned
        logger.info(
            "Planification BE terminée. Vols planifiés : %d, BE non planifiés : %d",
            len(self.flights),
            len(unplanned),
        )
        return unplanned

    # ------------------------------------------------------------
    # PLANNING BÉNÉVOLES
    # ------------------------------------------------------------

    def assign_volunteers(self) -> None:
        """ Affecte les bénévoles aux vols. """
        logger.info("Début affectation bénévoles -> vols...")
        volunteer_manager.assign_volunteers_to_flights(
            flights=self.flights,
            volunteers=self.volunteers,
        )
        logger.info("Affectation bénévoles -> vols terminée.")

    # ------------------------------------------------------------
    # EXPORT : PLANNING (BE + bénévoles)
    # ------------------------------------------------------------

    def build_planning_df(self) -> pd.DataFrame:
        """
        1 ligne = 1 BE = 1 bénévole (équilibrage optimal).
        """
        logger.info("Construction du DataFrame de planning...")
        rows = []

        for f in self.flights:
            shipments = list(f.shipments)
            if not shipments:
                continue

            volunteers = getattr(f, "assigned_volunteers", [])

            # Aucun bénévole sur ce vol
            if not volunteers:
                for s in shipments:
                    equiv = getattr(s, "equiv_colis", s.nb_colis_physiques)
                    rows.append({
                        "Date_Vol": f.date,
                        "Heure_Vol": f.departure_time.strftime("%H:%M") if f.departure_time else "",
                        "Vol": f.flight_number,
                        "Destination": f.chosen_destination or s.dest,
                        "BE_Numero": s.be_numero,
                        "BE_Nb_Colis": s.nb_colis_physiques,
                        "BE_Nb_Equiv": equiv,
                        "Benevole": "",
                    })
                continue

            # Équilibrage optimal
            shipments_sorted = sorted(
                shipments,
                key=lambda s: getattr(s, "equiv_colis", s.nb_colis_physiques),
                reverse=True
            )

            load = {v.id: 0 for v in volunteers}
            assignments = []
            MAXLOAD = config.MAX_EQUIV_PER_VOLUNTEER

            for s in shipments_sorted:
                equiv = getattr(s, "equiv_colis", s.nb_colis_physiques)
                possible = sorted(volunteers, key=lambda v: (load[v.id], v.benevole))

                chosen = None
                for v in possible:
                    if load[v.id] + equiv <= MAXLOAD:
                        chosen = v
                        break

                if chosen is None:
                    chosen = min(volunteers, key=lambda v: load[v.id])

                assignments.append((s, chosen))
                load[chosen.id] += equiv

            for s, v in assignments:
                equiv = getattr(s, "equiv_colis", s.nb_colis_physiques)
                setattr(s, "assigned_volunteer", v)

                rows.append({
                    "Date_Vol": f.date,
                    "Heure_Vol": f.departure_time.strftime("%H:%M") if f.departure_time else "",
                    "Vol": f.flight_number,
                    "Destination": f.chosen_destination or s.dest,
                    "BE_Numero": s.be_numero,
                    "BE_Nb_Colis": s.nb_colis_physiques,
                    "BE_Nb_Equiv": equiv,
                    "Benevole": v.benevole,
                })

        if not rows:
            logger.warning("Aucune ligne dans le planning généré (rows vide).")
            return pd.DataFrame(columns=[
                "Date_Vol", "Heure_Vol", "Vol", "Destination",
                "BE_Numero", "BE_Nb_Colis", "BE_Nb_Equiv", "Benevole"
            ])

        df = pd.DataFrame(rows)
        df_sorted = df.sort_values(by=["Date_Vol", "Heure_Vol", "Vol", "Destination", "BE_Numero"])
        logger.info("Planning construit : %d lignes.", len(df_sorted))
        return df_sorted

    # ------------------------------------------------------------
    # BILAN
    # ------------------------------------------------------------

    def build_bilan_df(self, unplanned: List[Shipment]) -> pd.DataFrame:
        logger.info("Construction du DataFrame de bilan...")
        rows = []

        # BE partants
        for s in self.shipments:
            if s.assigned_flight and s not in unplanned:
                f = s.assigned_flight
                v = getattr(s, "assigned_volunteer", None)
                equiv = getattr(s, "equiv_colis", s.nb_colis_physiques)

                rows.append({
                    "Date_Vol": f.date,
                    "Vol": f.flight_number,
                    "Destination": f.chosen_destination or s.dest,
                    "BE_Numero": s.be_numero,
                    "Nb_Colis": s.nb_colis_physiques,
                    "Nb_Equiv": equiv,
                    "Partant": "OUI",
                    "Raison": "OK",
                    "Benevole": v.benevole if v else "",
                })

        # BE non partants
        for s in unplanned:
            equiv = getattr(s, "equiv_colis", s.nb_colis_physiques)
            rows.append({
                "Date_Vol": "",
                "Vol": "",
                "Destination": s.dest,
                "BE_Numero": s.be_numero,
                "Nb_Colis": s.nb_colis_physiques,
                "Nb_Equiv": equiv,
                "Partant": "NON",
                "Raison": s.reason_not_planned or "Pas de vol adapté",
                "Benevole": "",
            })

        df = pd.DataFrame(rows)

        if df.empty:
            logger.warning("Bilan vide (aucun BE partant ou non partant).")
            return df

        df_sorted = df.sort_values(
            by=["Partant", "Date_Vol", "Vol", "Destination", "BE_Numero"],
            ascending=[False, True, True, True, True]
        )
        logger.info("Bilan construit : %d lignes (dont %d BE non planifiés).",
                    len(df_sorted), len(unplanned))
        return df_sorted

    # ------------------------------------------------------------
    # RUN
    # ------------------------------------------------------------

    def run(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        print("=== PLANNING AUTOMATISÉ ===")
        logger.info("=== DÉBUT D'UNE NOUVELLE EXÉCUTION DU PLANNING AUTOMATISÉ ===")

        try:
            print("➡ Chargement BE…")
            logger.info("Chargement des BE...")
            self.load_shipments()

            print("➡ Chargement vols…")
            logger.info("Chargement des vols...")
            self.load_flights()

            print("➡ Chargement bénévoles…")
            logger.info("Chargement des bénévoles...")
            self.load_volunteers()

            print("➡ Affectation BE -> vols…")
            logger.info("Affectation BE -> vols...")
            unplanned = self.plan_shipments_on_flights()
            print(f"   BE non planifiés : {len(unplanned)}")
            logger.info("Nombre de BE non planifiés : %d", len(unplanned))

            print("➡ Affectation bénévoles…")
            logger.info("Affectation bénévoles...")
            self.assign_volunteers()

            print("➡ Génération Planning & Bilan…")
            logger.info("Génération des DataFrames planning et bilan...")
            planning = self.build_planning_df()
            bilan = self.build_bilan_df(unplanned)

            print(f"   Planning : {len(planning)} lignes")
            print(f"   Bilan    : {len(bilan)} lignes")
            logger.info("Planning généré avec %d lignes, Bilan avec %d lignes.", len(planning), len(bilan))
            logger.info("=== FIN EXÉCUTION PLANNING ===")

            return planning, bilan

        except Exception as e:
            logger.exception("Erreur critique lors de l'exécution du planning : %s", e)
            raise
