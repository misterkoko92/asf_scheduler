# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import pandas as pd

from asf_app.services.shipments_update_service import (
    load_be_status,
    load_be_status_d_for_week,
    apply_planning_update,
)


def _build_mag_central(path: Path):
    df_mag = pd.DataFrame(
        [
            {
                "N° BE": "250001",
                "NB": 2,
                "DEST": "DLA",
                "TYPE": "MM",
                "EXP": "ASF",
                "DESTINATAIRE": "Hopital",
                "DATE DE DEPART VOL": "2025-01-06",
                "Statut BE": "D",
            },
            {
                "N° BE": "250002",
                "NB": 1,
                "DEST": "DLA",
                "TYPE": "MM",
                "EXP": "ASF",
                "DESTINATAIRE": "Hopital",
                "DATE DE DEPART VOL": "2025-01-20",
                "Statut BE": "X",
            },
        ]
    )
    with pd.ExcelWriter(path) as writer:
        df_mag.to_excel(writer, sheet_name="MAG CENTRAL 2025", index=False, startrow=5)


def test_load_be_status_filters_and_weeks(tmp_path):
    path = tmp_path / "tdb.xlsx"
    _build_mag_central(path)

    df = load_be_status("D", tdb_path=path)
    assert len(df) == 1
    assert df.iloc[0]["BE_Numero_Str"] == "250001"
    assert int(df.iloc[0]["Year"]) == 2025
    assert int(df.iloc[0]["Week"]) == pd.Timestamp("2025-01-06").isocalendar().week


def test_load_be_status_d_for_week(tmp_path):
    path = tmp_path / "tdb.xlsx"
    _build_mag_central(path)

    week = pd.Timestamp("2025-01-06").isocalendar().week
    df = load_be_status_d_for_week(week, 2025, tdb_path=path)
    assert len(df) == 1
    assert df.iloc[0]["BE_Numero_Str"] == "250001"


def test_apply_planning_update(tmp_path):
    from openpyxl import Workbook, load_workbook

    path = tmp_path / "planning.xlsx"
    wb = Workbook()
    ws_plan = wb.active
    ws_plan.title = "Planning"
    ws_plan["Q1"] = 1

    ws_exp = wb.create_sheet("Export planning")
    headers = [
        "BE_Numero",
        "Date_Vol",
        "Heure_Vol",
        "BE_Nb_Colis",
        "BE_Type",
        "BE_Expediteur",
        "BE_Destinataire",
    ]
    ws_exp.append(headers)
    ws_exp.append(["250001", "01/01/2025", "10:00", 2, "MM", "ASF", "Hopital"])
    wb.save(path)

    be_info = pd.Series({"BE_Nb_Colis": 3, "BE_Type": "MM"})
    apply_planning_update(
        path=path,
        action="Replanification",
        be_num="250001",
        dest_iata="DLA",
        date_new="02/01/2025",
        vol_new="AF123",
        heure_new="11:00",
        bene_choice="DUPONT",
        be_info=be_info,
    )

    wb2 = load_workbook(path)
    assert wb2.worksheets[0]["Q1"].value == 2

    ws_exp2 = wb2["Export planning"]
    rows = list(ws_exp2.iter_rows(values_only=True))
    header = list(rows[0])
    status_idx = header.index("_STATUS")
    be_idx = header.index("BE_Numero")

    statuses = [r[status_idx] for r in rows[1:]]
    bes = [str(r[be_idx]) for r in rows[1:]]

    assert "250001" in bes
    assert "old" in statuses
    assert "new" in statuses
    assert "Planning" in wb2.sheetnames
