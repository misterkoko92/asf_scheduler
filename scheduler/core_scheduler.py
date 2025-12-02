# scheduler/core_scheduler.py
# -*- coding: utf-8 -*-

from __future__ import annotations
from typing import List, Tuple, Dict, Any, Optional
import logging
from pathlib import Path
from collections import Counter, defaultdict
import json
import pandas as pd

from scheduler.models import Shipment, Flight, Volunteer
from scheduler import config
from scheduler import be_manager
from scheduler import volunteer_manager

from loaders.load_shipments import load_shipments
from loaders.load_benevoles import load_benevoles
from loaders.load_vols import load_vols

from scheduler.config_paths import PLANNING_BENEVOLES
from scheduler.engine import run_engine


# =====================================================================
# LOGFILE CONFIG
# =====================================================================

LOGFILE = Path("asf_scheduler.log")

logging.basicConfig(
    filename=str(LOGFILE),
    filemode="a",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("ASF-SCHEDULER")


def log_full_config() -> None:
    logger.info("=== CONFIGURATION ACTUELLE ===")
    logger.info("MAX_BE_PER_FLIGHT = %s", config.MAX_BE_PER_FLIGHT)
    logger.info("MAX_EQUIV_PER_VOLUNTEER = %s", config.MAX_EQUIV_PER_VOLUNTEER)
    logger.info("MAX_BENEV_PER_VOL = %s", config.MAX_BENEV_PER_VOL)
    logger.info("DUREE_MISSION_HEURES = %s", config.DUREE_MISSION_HEURES)
    logger.info("DEFAULT_FLIGHT_TIME = %s", config.DEFAULT_FLIGHT_TIME)
    logger.info("MAX_CAPACITE_PAR_VOL = %s", config.MAX_CAPACITE_PAR_VOL)
    logger.info("USE_REAL_CAPACITY_ESTIMATE = %s", config.USE_REAL_CAPACITY_ESTIMATE)
    logger.info("=============================================")


# =====================================================================
# SCHEDULER PRINCIPAL (wrapper autour du moteur unifié)
# =====================================================================

class Scheduler:
    """
    Orchestrateur global :
      - charge BE, vols, bénévoles
      - délègue la logique métier au moteur unifié (engine.run_engine)
      - retourne Planning & Bilan prêts à l’export
    """

    def __init__(
        self,
        *,
        mode: str = "real",
        rarity_mode: int = 1,
        simulation_id: Optional[str] = None,
    ) -> None:
        # Données principales
        self.shipments: List[Shipment] = []
        self.flights: List[Flight] = []
        self.volunteers: List[Volunteer] = []
        self.param_be: Dict[str, Dict[str, int]] | None = None

        # Contexte / options
        self.mode: str = mode
        self.rarity_mode: int = rarity_mode
        self.simulation_id: Optional[str] = simulation_id

        # Stats résumées (remplies par run)
        self.run_stats: Dict[str, Any] = {}

    # ------------------------------------------------------------
    # LOAD SHIPMENTS
    # ------------------------------------------------------------
    def load_shipments(self) -> None:
        print("➡ Chargement BE…")

        if self.param_be is None:
            self.param_be = be_manager.load_param_be()

        be_list = load_shipments(self.param_be)
        print(f"➡ BE planifiables : {len(be_list)}")

        # Debug statuts
        status_counts = Counter(getattr(s, "status", "") for s in be_list)
        print("\n=== STATUTS BE ===")
        for st, n in sorted(status_counts.items()):
            print(f" - {st}: {n}")
        print("=====================\n")

        # Tri final (priorité, etc.)
        be_list = be_manager.sort_shipments(be_list)

        print("\n=== DEBUG EQUIV_COLIS PAR TYPE ===")
        stats = defaultdict(lambda: {"nb": 0, "colis": 0, "equiv": 0})
        for s in be_list:
            t = s.type_colis
            stats[t]["nb"] += 1
            stats[t]["colis"] += s.nb_colis_physiques
            stats[t]["equiv"] += s.equiv_colis
        for t, v in stats.items():
            ratio = v["equiv"] / v["colis"] if v["colis"] else 0
            print(
                f"{t}: BE={v['nb']} | Colis={v['colis']} | "
                f"Equiv={v['equiv']} | Ratio={ratio:.2f}"
            )
        print("==============================\n")

        self.shipments = be_list

    # ------------------------------------------------------------
    # LOAD FLIGHTS
    # ------------------------------------------------------------
    def load_flights(self) -> None:
        print("➡ Chargement vols…")

        vols_raw = load_vols()
        if vols_raw is None:
            vols_raw = []  # sécurité absolue (ne devrait plus arriver)

        flights: List[Flight] = []

        for r in vols_raw:
            routing = r.get("routing") or []
            if not isinstance(routing, list):
                routing = []

            # Normalisation routing en majuscules
            routing = [str(x).upper().strip() for x in routing]

            flights.append(
                Flight(
                    flight_number=str(r.get("flight_number", "")),
                    date=r.get("date"),
                    departure_time=r.get("departure_time"),
                    routing=routing,
                    max_colis_base=r.get("max_colis_base"),
                )
            )

        self.flights = flights

        print(f"➡ Vols chargés : {len(flights)}")
        print("\n=== DEBUG VOLS (aperçu) ===")
        for f in flights[:10]:
            print(
                f" - Vol {f.flight_number} | {f.date} | "
                f"{f.departure_time} | Routing={f.routing}"
            )
        print("===============================\n")

    # ------------------------------------------------------------
    # LOAD VOLUNTEERS
    # ------------------------------------------------------------
    def load_volunteers(self) -> None:
        print("➡ Chargement bénévoles…")

        df_dispo = load_benevoles()
        param_benev = volunteer_manager.load_param_benev(PLANNING_BENEVOLES)

        self.volunteers = volunteer_manager.build_volunteers(df_dispo, param_benev)

        print(f"➡ Bénévoles utilisables : {len(self.volunteers)}")
        print("\n=== DEBUG BÉNÉVOLES ===")
        for v in self.volunteers[:10]:
            print(f" - {v.id} : {v.benevole}")
        print("=========================\n")

    # ------------------------------------------------------------
    # RUN GLOBAL
    # ------------------------------------------------------------
    def run(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        print("=== PLANNING AUTOMATISÉ (ENGINE) ===")
        print(
            f"Mode exécution : {self.mode} | "
            f"rarity_mode={self.rarity_mode} | "
            f"simulation_id={self.simulation_id}"
        )
        logger.info("=== DÉBUT D’UNE EXÉCUTION (ENGINE) ===")
        logger.info(
            "Mode=%s rarity_mode=%s simulation_id=%s",
            self.mode, self.rarity_mode, self.simulation_id
        )

        log_full_config()

        # 1) Chargements
        self.load_shipments()
        self.load_flights()
        self.load_volunteers()

        # 2) Moteur unifié
        planning, bilan, run_stats = run_engine(
            shipments=self.shipments,
            flights=self.flights,
            volunteers=self.volunteers,
            rarity_mode=self.rarity_mode,
            mode=self.mode,
            simulation_id=self.simulation_id,
        )

        self.run_stats = run_stats

        logger.info(
            "RUN SUMMARY (ENGINE) mode=%s sim_id=%s total_be=%s "
            "planned=%s unplanned=%s vols_used=%s benev_used=%s",
            run_stats.get("mode"),
            run_stats.get("simulation_id"),
            run_stats.get("total_be"),
            run_stats.get("be_planned"),
            run_stats.get("be_unplanned"),
            run_stats.get("vols_with_be"),
            run_stats.get("benevoles_used"),
        )
        logger.info("=== FIN EXÉCUTION (ENGINE) ===")

        print(f"➡ Planning : {len(planning)} lignes")
        print(f"➡ Bilan    : {len(bilan)} lignes")

        # Petit JSON debug optionnel si tu veux garder un historique
        try:
            with open("engine_run_stats.json", "w", encoding="utf-8") as fp:
                json.dump(run_stats, fp, indent=2, ensure_ascii=False)
        except Exception:
            pass

        return planning, bilan
