# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import pandas as pd

import scheduler.config_paths as cp
from loaders.universal_loader import load_and_normalize
from scheduler.column_map import column_map_mag_central
from scheduler.config_paths import SHEET_MAG_CENTRAL, TABLEAU_DE_BORD
from utils.datetime_utils import (
    parse_date_series,
    parse_time_series,
    coerce_datetime,
    normalize_hour_str,
    hour_min_from_series,
)
from utils.identifiers import normalize_be_number
from utils.logging_utils import get_logger

logger = get_logger("shipments_update_service", console=False)


def load_be_status(status_code: str, *, tdb_path: Path | None = None) -> pd.DataFrame:
    tdb_use = Path(tdb_path) if tdb_path is not None else TABLEAU_DE_BORD
    try:
        xls = pd.ExcelFile(tdb_use)
        sheets = [
            name
            for name in xls.sheet_names
            if str(name).strip().upper().startswith("MAG CENTRAL")
        ]
    except Exception:
        sheets = []

    if not sheets:
        sheets = [SHEET_MAG_CENTRAL]

    def _rank(name: str) -> tuple[int, str]:
        match = re.search(r"(20\d{2})", name)
        year = int(match.group(1)) if match else -1
        return (year, name)

    sheets = [name for name in sheets if _rank(name)[0] >= 2025]
    sheets = sorted(sheets, key=_rank)
    frames = []
    for sheet in sheets:
        df_sheet = load_and_normalize(
            path=tdb_use,
            sheet_name=sheet,
            mapping=column_map_mag_central,
            header=5,
        )
        if df_sheet is None or df_sheet.empty:
            continue
        df_sheet["_MAG_CENTRAL_SHEET"] = sheet
        frames.append(df_sheet)

    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame(columns=["Week", "Year"])

    df = df.copy()
    if "BE_Statut" not in df.columns:
        df["BE_Statut"] = ""
    df["BE_Statut"] = df["BE_Statut"].astype(str).str.upper().str.strip()
    df = df[df["BE_Statut"] == status_code.upper()].copy()

    df["BE_Numero_Str"] = df.get("BE_Numero", "").astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    df["Date_Vol"] = coerce_datetime(df.get("BE_Date_Vol", pd.NaT), errors="coerce", dayfirst=False)
    iso = df["Date_Vol"].dt.isocalendar()
    df["Week"] = iso.week.astype("Int64")
    df["Year"] = iso.year.astype("Int64")
    return df


def load_be_status_d_for_week(week: int, year: int, *, tdb_path: Path | None = None) -> pd.DataFrame:
    df = load_be_status("D", tdb_path=tdb_path)
    if df.empty:
        return df
    mask_match = (df["Week"] == week) & (df["Year"] == year)
    mask_na = df["Week"].isna() | df["Year"].isna()
    df = df[mask_match | mask_na].copy()
    df["Source"] = "mag_central"
    return df


def apply_planning_update(
    path: Path,
    action: str,
    be_num: str,
    dest_iata: str,
    date_new: str,
    vol_new: str,
    heure_new: str,
    bene_choice: str,
    be_info: pd.Series,
    plan_row: Optional[pd.Series] = None,
    plan_row_full: Optional[pd.Series] = None,
    bene_meta: Optional[dict] = None,
    bene_changed: bool = False,
):
    """
    Construit un DF consolidé, applique l'action, puis regénère Export/Planning.
    """
    import openpyxl
    from openpyxl.styles import PatternFill

    def _norm_be(val: str) -> str:
        return normalize_be_number(val) or str(val)

    # Lecture Export planning en DF
    try:
        df_export = pd.read_excel(path, sheet_name="Export planning")
    except Exception:
        df_export = pd.DataFrame()
    # Fallback Planning si Export planning absent
    if df_export.empty:
        try:
            df_export = pd.read_excel(path, sheet_name=0)
        except Exception:
            df_export = pd.DataFrame()

    # Normalisation minimale
    df_export = df_export.copy()
    df_export.columns = [str(c) for c in df_export.columns]
    if "BE_Numero" not in df_export.columns:
        df_export["BE_Numero"] = df_export.get("BE_NUM", df_export.get("BE", ""))
    df_export["BE_Key"] = df_export["BE_Numero"].apply(_norm_be)
    if "Date_Vol" in df_export.columns:
        df_export["Date_Vol"] = parse_date_series(df_export["Date_Vol"]).dt.date
    if "Heure_Vol" in df_export.columns:
        df_export["Heure_Vol"] = parse_time_series(df_export["Heure_Vol"]).dt.time
        df_export["HEURE_MIN"] = hour_min_from_series(df_export["Heure_Vol"])
    if "_STATUS" not in df_export.columns:
        df_export["_STATUS"] = "normal"

    # Appliquer l'action sur le DF
    if action == "Annulation":
        df_export.loc[df_export["BE_Key"] == _norm_be(be_num), "_STATUS"] = "old"
    else:
        # marquer l'ancienne ligne en old
        df_export.loc[df_export["BE_Key"] == _norm_be(be_num), "_STATUS"] = "old"
        # construire la nouvelle ligne
        new_row = {
            "BE_Numero": be_num,
            "BE_Key": _norm_be(be_num),
            "Destination": dest_iata,
            "IATA": dest_iata,
            "Date_Vol": parse_date_series(pd.Series([date_new])).iloc[0].date() if date_new else None,
            "Heure_Vol": parse_time_series(pd.Series([heure_new])).iloc[0].time() if heure_new else None,
            "Heure": normalize_hour_str(pd.Series([heure_new])).iloc[0],
            "HEURE_MIN": hour_min_from_series(pd.Series([heure_new])).iloc[0],
            "Numero_Vol": vol_new,
            "Numero_Vol": vol_new,
            "Routing": "",
            "Benevole": bene_choice,
            "BE_Nb_Colis": be_info.get("BE_Nb_Colis", be_info.get("Nb_Colis", "")),
            "BE_Nb_Equiv": be_info.get("BE_Nb_Equiv", be_info.get("Equiv_Colis", "")),
            "BE_Type": be_info.get("BE_Type", ""),
            "BE_Expediteur": be_info.get("BE_Expediteur", ""),
            "BE_Destinataire": be_info.get("BE_Destinataire", ""),
            "_STATUS": "new",
        }
        df_export = pd.concat([df_export, pd.DataFrame([new_row])], ignore_index=True)

    # Tri
    df_export = df_export.sort_values(by=["Date_Vol", "Heure_Vol", "BE_Numero"], kind="mergesort").reset_index(drop=True)

    # Écriture Excel
    wb = openpyxl.load_workbook(path)
    # incrémenter Q1 (version) si existant
    q1_value = None
    try:
        ws_plan = wb.worksheets[0]
        q1_val = ws_plan["Q1"].value
        q1_value = (int(q1_val) if q1_val not in (None, "") else 0) + 1
        ws_plan["Q1"].value = q1_value
    except Exception:
        pass

    def _clear_values(ws, max_row: int, max_col: int):
        for row in ws.iter_rows(min_row=1, max_row=max_row, min_col=1, max_col=max_col):
            for cell in row:
                cell.value = None

    # Export planning
    ws_exp = (
        wb["Export planning"]
        if "Export planning" in wb.sheetnames
        else wb.create_sheet("Export planning", 1)
    )
    headers = list(df_export.columns)
    max_row = max(ws_exp.max_row, len(df_export) + 1)
    max_col = max(ws_exp.max_column, len(headers))
    _clear_values(ws_exp, max_row, max_col)
    for c_idx, h in enumerate(headers, start=1):
        ws_exp.cell(row=1, column=c_idx, value=h)
    for r_idx, (_, r) in enumerate(df_export.iterrows(), start=2):
        for c_idx, h in enumerate(headers, start=1):
            ws_exp.cell(row=r_idx, column=c_idx, value=r.get(h, ""))

    # Planning : reprendre uniquement les colonnes utiles et appliquer couleurs
    ws_plan_new = (
        wb["Planning"]
        if "Planning" in wb.sheetnames
        else wb.create_sheet("Planning", 0)
    )
    planning_cols = [
        "Benevole", "unusedE", "unusedF", "Destination", "IATA", "Routing",
        "Numero_Vol", "Heure_Vol", "BE_Numero", "BE_Nb_Colis", "BE_Type",
        "unusedN", "BE_Expediteur", "BE_Destinataire"
    ]
    # Squelettes colonnes D..Q (4..17)
    headers_plan = ["", "", "", "Benevole", "", "Destination", "IATA", "Routing", "Numero_Vol", "Heure_Vol", "BE_Numero", "BE_Nb_Colis", "BE_Type", "", "BE_Expediteur", "BE_Destinataire"]
    max_row = max(ws_plan_new.max_row, len(df_export) + 1)
    max_col = max(ws_plan_new.max_column, len(headers_plan))
    _clear_values(ws_plan_new, max_row, max_col)
    if q1_value is not None:
        ws_plan_new["Q1"].value = q1_value
    for row in ws_plan_new.iter_rows(min_row=2, max_row=max_row, min_col=4, max_col=17):
        for cell in row:
            cell.fill = PatternFill()
    for c_idx, val in enumerate(headers_plan, start=1):
        ws_plan_new.cell(row=1, column=c_idx, value=val)
    fill_red = PatternFill(fill_type="solid", fgColor="F8CBAD")
    fill_blue = PatternFill(fill_type="solid", fgColor="BDD7EE")
    for r_idx, (_, r) in enumerate(df_export.iterrows(), start=2):
        status = str(r.get("_STATUS", "normal")).lower()
        row_vals = ["", "", "", r.get("Benevole", ""), "", r.get("Destination", ""), r.get("IATA", ""), r.get("Routing", ""), r.get("Numero_Vol", ""), normalize_hour_str(pd.Series([r.get("Heure_Vol", "")])).iloc[0], r.get("BE_Numero", ""), "" if status.startswith("old") else r.get("BE_Nb_Colis", ""), r.get("BE_Type", ""), "", r.get("BE_Expediteur", ""), r.get("BE_Destinataire", "")]
        for c_idx, val in enumerate(row_vals, start=1):
            ws_plan_new.cell(row=r_idx, column=c_idx, value=val)
        if status.startswith("old") or status.startswith("new"):
            fill = fill_red if status.startswith("old") else fill_blue
            for c in range(4, 18):
                ws_plan_new.cell(row=r_idx, column=c).fill = fill

    wb.save(path)
    cp.sync_local_file_to_onedrive(path)
