# loaders/load_benevoles.py
# -*- coding: utf-8 -*-

import pandas as pd
from scheduler.config_paths import PLANNING_BENEVOLES, SHEET_BENEV_DISPO


def load_benevoles() -> pd.DataFrame:
    """
    Charge le planning des disponibilités bénévoles :
        PLANNING_BENEVOLES.xlsx / SHEET_BENEV_DISPO

    Retourne un DataFrame propre :
        - toutes les valeurs converties en str
        - valeurs NaN remplacées par ""
    """

    df = pd.read_excel(
        PLANNING_BENEVOLES,
        sheet_name=SHEET_BENEV_DISPO,
        dtype=str
    )

    df = df.fillna("").astype(str)

    return df
