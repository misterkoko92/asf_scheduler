# -*- coding: utf-8 -*-
from __future__ import annotations

import pandas as pd

from utils.benevole_utils import count_benevoles_with_dispo


def test_count_benevoles_with_dispo_basic():
    df = pd.DataFrame(
        [
            {"Benevole": "A", "Date": "01/01/2025", "Heure_Arrivee": "08:00", "Heure_Depart": "12:00"},
            {"Benevole": "B", "Date": "02/01/2025", "Heure_Arrivee": "09:00", "Heure_Depart": "11:00"},
            {"Benevole": "A", "Date": "02/01/2025", "Heure_Arrivee": "10:00", "Heure_Depart": "12:00"},
        ]
    )

    count, start_dt, end_dt = count_benevoles_with_dispo(df)
    assert count == 2
    assert start_dt is not None
    assert end_dt is not None


def test_count_benevoles_with_dispo_with_date_dt():
    df = pd.DataFrame(
        [
            {
                "Benevole": "A",
                "Date_dt": pd.to_datetime("2025-01-01"),
                "Heure_Arrivee_time": pd.to_datetime("08:00").time(),
                "Heure_Depart_time": pd.to_datetime("12:00").time(),
            }
        ]
    )
    count, _, _ = count_benevoles_with_dispo(df)
    assert count == 1
