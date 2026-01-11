# -*- coding: utf-8 -*-
from __future__ import annotations

import pandas as pd

from asf_app.ui.ui_communication.clean_planning_df import build_df_comm


def test_build_df_comm_formats_be_and_vol():
    df_planning = pd.DataFrame(
        [
            {
                "Date_Vol": "01/01/2025",
                "Heure_Vol": "10:00",
                "Numero_Vol": "AF 0007",
                "Destination": "DLA",
                "BE_Numero": "1234",
                "BE_Nb_Colis": 1,
                "Benevole": "DUPONT",
                "ID": "1",
            }
        ]
    )
    df_paramdest = pd.DataFrame([{"Dest_IATA": "DLA", "Dest_Ville": "DOUALA"}])
    df_parambenev = pd.DataFrame(
        [
            {
                "ID": "1",
                "Benevole": "DUPONT",
                "Prenom": "Jean",
                "Prenom_Court": "J.",
                "Nom": "Dupont",
                "Telephone": "0600000000",
            }
        ]
    )

    df_comm = build_df_comm(df_planning, df_paramdest, df_parambenev)

    assert df_comm.loc[0, "Numero_BE_Aff"] == "001234"
    assert df_comm.loc[0, "Numero_Vol_Aff"] == "AF 7"
