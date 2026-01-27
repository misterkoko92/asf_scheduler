# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime as dt

import pandas as pd

from asf_app.services.params_service import add_benevole_dispo, add_vol


def test_add_benevole_dispo(tmp_path, monkeypatch):
    import utils.excel_automation as ea

    monkeypatch.setattr(ea, "write_sheet_table", lambda *args, **kwargs: False)

    path = tmp_path / "benev.xlsx"
    df = pd.DataFrame(
        [
            {
                "ID": "1",
                "BENEVOLE": "DUPONT",
                "NOM": "Dupont",
                "PRENOM": "Jean",
                "PRENOM_COURT": "Jean",
                "DATE": "01/01/2025",
                "HEURE_ARRIVEE": "06:00",
                "HEURE_DEPART": "12:00",
                "MAX_JOURS_SEMAINE": 5,
                "MAX_EXP_SEMAINE": 10,
                "MAX_EXP_JOUR": 5,
                "ATTENTE_MAX_H": 5,
            }
        ]
    )
    df.to_excel(path, sheet_name="ParamBenev", index=False)

    form_data = {
        "id_ben": "2",
        "benevole_label": "MARTIN",
        "nom": "Martin",
        "prenom": "Claire",
        "prenom_court": "Claire",
        "date_dispo": dt.date(2025, 1, 5),
        "h_arr": dt.time(9, 0),
        "h_dep": dt.time(12, 0),
        "max_jours_semaine": 3,
        "max_exp_semaine": 4,
        "max_exp_jour": 2,
        "attente_max_h": 6,
    }

    add_benevole_dispo(path, form_data)

    out = pd.read_excel(path, sheet_name="ParamBenev")
    last = out.iloc[-1]
    assert last["BENEVOLE"] == "MARTIN"
    assert last["DATE"] == "05/01/2025"
    # h_arrivee = h_arr - 3h
    assert str(last["HEURE_ARRIVEE"]).startswith("06")
    assert str(last["HEURE_DEPART"]).startswith("12")


def test_add_vol(tmp_path, monkeypatch):
    import utils.excel_automation as ea

    monkeypatch.setattr(ea, "write_sheet_table", lambda *args, **kwargs: False)

    path = tmp_path / "vols.xlsx"
    df = pd.DataFrame(
        [
            {
                "PVOL_NUMERO": "123",
                "PVOL_DATE": "01/01/2025",
                "PVOL_HEURE": "10:00",
                "PVOL_FK_DESTINATION": "DLA",
                "PVOL_ROUTE_API": "CDG, DLA",
            }
        ]
    )
    df.to_excel(path, sheet_name="Vols", index=False)

    form_data = {
        "pvol_num": "456",
        "pvol_date": dt.date(2025, 1, 2),
        "pvol_heure": dt.time(12, 30),
        "pvol_dest": "BZV",
        "pvol_route": "CDG, BZV",
    }

    add_vol(path, form_data)

    out = pd.read_excel(path, sheet_name="Vols")
    assert len(out) == 2
    assert str(out.iloc[-1]["PVOL_NUMERO"]) == "456"
    assert out.iloc[-1]["PVOL_FK_DESTINATION"] == "BZV"
