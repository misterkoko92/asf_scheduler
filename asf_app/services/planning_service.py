# asf_app/services/planning_service.py
# -*- coding: utf-8 -*-
import datetime
from typing import Tuple, Dict

import pandas as pd

from scheduler.core_scheduler import Scheduler
from asf_app.config.paths import AppPaths


def run_planning(paths: AppPaths) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Synchronise les chemins avec le moteur, lance le scheduler et renvoie
    (planning_df, bilan_df).
    """
    # Important : on pousse les chemins vers scheduler.config_paths
    paths.sync_to_engine()

    scheduler = Scheduler()
    planning_df, bilan_df = scheduler.run()
    return planning_df, bilan_df


def add_manual_be(planning_df: pd.DataFrame, form_data: Dict) -> pd.DataFrame:
    new_row = {
        "Date_Vol": form_data["date_vol"],
        "Heure_Vol": form_data["heure_vol"].strftime("%H:%M"),
        "Vol": form_data["vol_num"],
        "Destination": form_data["dest"],
        "BE_Numero": form_data["be_num"],
        "BE_Nb_Colis": form_data["nb_colis"],
        "BE_Nb_Equiv": form_data["nb_colis"],
        "Benevole": form_data["benevole"],
    }
    return pd.concat([planning_df, pd.DataFrame([new_row])], ignore_index=True)
