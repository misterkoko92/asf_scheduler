# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import pandas as pd

from asf_app.services.shipments_update_service import (
    load_be_status,
    load_be_status_d_for_week,
    apply_planning_update,
    apply_planning_updates_batch,
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
    import datetime as dt
    from utils.datetime_utils import coerce_datetime
    import scheduler.config_paths as cp

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
    # Align with export_planning_excel versioning logic based on template A1
    wk, yr = 1, 2025
    try:
        template = cp.PLANNING_TEMPLATE
        if template.exists():
            wb_tpl = load_workbook(template)
            val = wb_tpl.worksheets[0]["A1"].value
            if isinstance(val, dt.datetime):
                wk = val.isocalendar()[1]
                yr = val.isocalendar()[0]
            else:
                dt_val = coerce_datetime(val, errors="coerce", dayfirst=True)
                if pd.notna(dt_val):
                    wk = dt_val.isocalendar()[1]
                    yr = dt_val.isocalendar()[0]
    except Exception:
        pass

    # Fake existing version to force increment to v02
    existing = tmp_path / f"ASFmm - PLANNING SEMAINE {yr}-{wk:02d}-01.xlsx"
    existing.touch()

    out_path = apply_planning_update(
        path=path,
        action="Replanification",
        be_num="250001",
        dest_iata="DLA",
        date_new="02/01/2025",
        vol_new="AF123",
        heure_new="11:00",
        bene_choice="DUPONT",
        be_info=be_info,
        week=wk,
        year=yr,
    )

    out_path = Path(out_path)
    assert out_path.exists()
    wb2 = load_workbook(out_path)
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
    assert any(str(name).startswith("Planning") for name in wb2.sheetnames)


def test_apply_planning_updates_batch(tmp_path):
    from openpyxl import Workbook, load_workbook
    import datetime as dt
    from utils.datetime_utils import coerce_datetime
    import scheduler.config_paths as cp

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

    wk, yr = 1, 2025
    try:
        template = cp.PLANNING_TEMPLATE
        if template.exists():
            wb_tpl = load_workbook(template)
            val = wb_tpl.worksheets[0]["A1"].value
            if isinstance(val, dt.datetime):
                wk = val.isocalendar()[1]
                yr = val.isocalendar()[0]
            else:
                dt_val = coerce_datetime(val, errors="coerce", dayfirst=True)
                if pd.notna(dt_val):
                    wk = dt_val.isocalendar()[1]
                    yr = dt_val.isocalendar()[0]
    except Exception:
        pass

    existing = tmp_path / f"ASFmm - PLANNING SEMAINE {yr}-{wk:02d}-01.xlsx"
    existing.touch()

    updates = [
        {
            "action": "Changement de date ou bénévole",
            "be_num": "250001",
            "dest_iata": "DLA",
            "date_new": "02/01/2025",
            "vol_new": "AF123",
            "heure_new": "11:00",
            "bene_choice": "DUPONT",
            "be_info": {"BE_Nb_Colis": 3, "BE_Type": "MM"},
            "plan_row_full": {},
            "bene_meta": {},
            "bene_changed": False,
        },
        {
            "action": "Ajouter au planning",
            "be_num": "250002",
            "dest_iata": "DLA",
            "date_new": "03/01/2025",
            "vol_new": "AF456",
            "heure_new": "12:00",
            "bene_choice": "MARTIN",
            "be_info": {"BE_Nb_Colis": 1, "BE_Type": "MM"},
            "plan_row_full": {},
            "bene_meta": {},
            "bene_changed": False,
        },
    ]

    out_path = apply_planning_updates_batch(
        path,
        updates,
        week=wk,
        year=yr,
        increment_version=True,
        write_mag_central=False,
    )

    out_path = Path(out_path)
    assert out_path.exists()
    wb2 = load_workbook(out_path)
    assert wb2.worksheets[0]["Q1"].value == 2

    ws_exp2 = wb2["Export planning"]
    rows = list(ws_exp2.iter_rows(values_only=True))
    header = list(rows[0])
    status_idx = header.index("_STATUS")
    be_idx = header.index("BE_Numero")

    statuses = [r[status_idx] for r in rows[1:]]
    bes = [str(r[be_idx]) for r in rows[1:]]

    assert "250001" in bes
    assert "250002" in bes
    assert "old" in statuses
    assert "new" in statuses
