# scheduler/core_scheduler.py
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pandas as pd

from scheduler import config
from scheduler.data_sources import DataSource
from scheduler.planning_schema import normalize_planning_df, validate_planning_df
from scheduler.solver_router import get_solver_version, solve_planning_ortools

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
    logger.info("SOLVER_VERSION = %s", get_solver_version())
    logger.info("MAX_BE_PER_FLIGHT = %s", config.MAX_BE_PER_FLIGHT)
    logger.info("MAX_EQUIV_PER_VOLUNTEER = %s", config.MAX_EQUIV_PER_VOLUNTEER)
    logger.info("MAX_BENEV_PER_VOL = %s", config.MAX_BENEV_PER_VOL)
    logger.info("DUREE_MISSION_HEURES = %s", config.DUREE_MISSION_HEURES)
    logger.info("DEFAULT_FLIGHT_TIME = %s", config.DEFAULT_FLIGHT_TIME)
    logger.info("MAX_CAPACITE_PAR_VOL = %s", config.MAX_CAPACITE_PAR_VOL)
    logger.info("USE_REAL_CAPACITY_ESTIMATE = %s", config.USE_REAL_CAPACITY_ESTIMATE)
    logger.info("=============================================")


# =====================================================================
# SCHEDULER PRINCIPAL (OR-Tools only)
# =====================================================================

class Scheduler:
    """
    Orchestrateur global :
      - lance le solveur OR-Tools
      - normalise et valide le planning
    """

    def __init__(
        self,
        *,
        mode: str = "real",
        rarity_mode: int = 1,
        simulation_id: Optional[str] = None,
        data_source_name: Optional[str] = None,
        data_source: DataSource | None = None,
    ) -> None:
        self.mode: str = mode
        self.rarity_mode: int = rarity_mode
        self.simulation_id: Optional[str] = simulation_id
        self.data_source_name: Optional[str] = data_source_name
        self.data_source: DataSource | None = data_source
        self.run_stats: Dict[str, Any] = {}

    # ------------------------------------------------------------
    # RUN GLOBAL
    # ------------------------------------------------------------
    def run(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        logger.info("=== PLANNING AUTOMATISE ===")
        logger.info(
            "Mode execution : %s | rarity_mode=%s | simulation_id=%s",
            self.mode,
            self.rarity_mode,
            self.simulation_id,
        )
        logger.info("=== DEBUT D'UNE EXECUTION ===")
        logger.info(
            "Mode=%s rarity_mode=%s simulation_id=%s",
            self.mode, self.rarity_mode, self.simulation_id,
        )

        log_full_config()

        priority_mode = "benevoles" if self.rarity_mode == 2 else "colis"
        planning, bilan, stats = solve_planning_ortools(
            priority_mode=priority_mode,
            data_source=self.data_source,
            data_source_name=self.data_source_name,
        )

        if stats.get("status") == "ORTOOLS_MISSING":
            msg = "OR-Tools non disponible: installez le module `ortools` avant execution."
            logger.error(msg)
            raise RuntimeError(msg)

        planning = normalize_planning_df(planning)
        schema_errors = validate_planning_df(planning)
        if schema_errors:
            msg = "Planning schema invalid: " + "; ".join(schema_errors)
            logger.warning(msg)
            if os.getenv("ASF_STRICT_SCHEMA") == "1":
                raise ValueError(msg)

        run_stats = {
            "mode": self.mode,
            "simulation_id": self.simulation_id,
            "priority_mode": priority_mode,
            "status": stats.get("status"),
            "total_be": stats.get("nb_be_total"),
            "be_planned": stats.get("nb_be_envoyes"),
            "be_unplanned": (
                stats.get("nb_be_total", 0) - stats.get("nb_be_envoyes", 0)
                if stats.get("nb_be_total") is not None
                else None
            ),
            "vols_with_be": (
                planning[["Date_Vol", "Numero_Vol", "Destination"]]
                .drop_duplicates()
                .shape[0]
                if not planning.empty
                else 0
            ),
            "benevoles_used": (
                planning["ID"].astype(str).str.strip().replace("", pd.NA).dropna().nunique()
                if not planning.empty
                else 0
            ),
        }

        self.run_stats = run_stats

        logger.info(
            "RUN SUMMARY mode=%s sim_id=%s total_be=%s "
            "planned=%s unplanned=%s vols_used=%s benev_used=%s",
            run_stats.get("mode"),
            run_stats.get("simulation_id"),
            run_stats.get("total_be"),
            run_stats.get("be_planned"),
            run_stats.get("be_unplanned"),
            run_stats.get("vols_with_be"),
            run_stats.get("benevoles_used"),
        )
        logger.info("=== FIN EXECUTION ===")

        logger.info("-> Planning : %s lignes", len(planning))
        logger.info("-> Bilan    : %s lignes", len(bilan))

        # Debug json optionnel
        try:
            with open("engine_run_stats.json", "w", encoding="utf-8") as fp:
                json.dump(run_stats, fp, indent=2, ensure_ascii=False)
        except (OSError, TypeError, ValueError):
            pass

        return planning, bilan
