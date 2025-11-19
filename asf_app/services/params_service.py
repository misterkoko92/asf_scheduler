# asf_app/services/params_service.py
# -*- coding: utf-8 -*-
import datetime
from typing import Dict

import pandas as pd

from .files_service import read_excel_sheet, save_excel_sheet
from scheduler.config_paths import SHEET_PARAM_DEST, SHEET_PARAM_BE, SHEET_PARAM_BENEV


def load_paramdest(path_tdb: str) -> pd.DataFrame:
    return read_excel_sheet(path_tdb, SHEET_PARAM_DEST)


def save_paramdest(path_tdb: str, df: pd.DataFrame) -> None:
    save_excel_sheet(path_tdb, SHEET_PARAM_DEST, df)


def load_parambe(path_tdb: str) -> pd.DataFrame:
    return read_excel_sheet(path_tdb, SHEET_PARAM_BE)


def save_parambe(path_tdb: str, df: pd.DataFrame) -> None:
    save_excel_sheet(path_tdb, SHEET_PARAM_BE, df)


def load_parambenev(path_benev: str) -> pd.DataFrame:
    return read_excel_sheet(path_benev, SHEET_PARAM_BENEV)


def save_parambenev(path_benev: str, df: pd.DataFrame) -> None:
    save_excel_sheet(path_benev, SHEET_PARAM_BENEV, df)


def add_benevole_dispo(path_benev: str, form_data: Dict[str, str | datetime.date | datetime.time]) -> None:
    df = load_parambenev(path_benev)
    cols = df.columns.tolist()
    new_row = {c: "" for c in cols}

    # Mapping logique identique à ton app actuelle
    if "ID" in new_row:
        new_row["ID"] = form_data.get("id_ben", "")
    if "BENEVOLE" in new_row:
        benevole_label = form_data.get("benevole_label") or f"{form_data.get('prenom', '')} {form_data.get('nom', '')}".strip()
        new_row["BENEVOLE"] = benevole_label
    if "NOM" in new_row:
        new_row["NOM"] = form_data.get("nom", "")
    if "PRENOM" in new_row:
        new_row["PRENOM"] = form_data.get("prenom", "")
    if "PRENOM_COURT" in new_row:
        new_row["PRENOM_COURT"] = form_data.get("prenom_court", "")

    date_dispo = form_data.get("date_dispo")
    if isinstance(date_dispo, datetime.date) and "DATE" in new_row:
        new_row["DATE"] = date_dispo.strftime("%d/%m/%Y")

    h_arr = form_data.get("h_arr")
    if isinstance(h_arr, datetime.time) and "HEURE_ARRIVEE" in new_row:
        new_row["HEURE_ARRIVEE"] = h_arr.strftime("%H:%M")

    h_dep = form_data.get("h_dep")
    if isinstance(h_dep, datetime.time) and "HEURE_DEPART" in new_row:
        new_row["HEURE_DEPART"] = h_dep.strftime("%H:%M")

    if "MAX_JOURS_SEMAINE" in new_row:
        new_row["MAX_JOURS_SEMAINE"] = form_data.get("max_jours_semaine", "")
    if "MAX_EXP_SEMAINE" in new_row:
        new_row["MAX_EXP_SEMAINE"] = form_data.get("max_exp_semaine", "")
    if "MAX_EXP_JOUR" in new_row:
        new_row["MAX_EXP_JOUR"] = form_data.get("max_exp_jour", "")
    if "ATTENTE_MAX_H" in new_row:
        new_row["ATTENTE_MAX_H"] = form_data.get("attente_max_h", "")

    df2 = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_parambenev(path_benev, df2)


def add_vol(path_vols: str, form_data: Dict[str, str | datetime.date | datetime.time]) -> None:
    df_vols = pd.read_excel(path_vols, dtype=str).fillna("")
    cols = df_vols.columns.tolist()
    new_row = {c: "" for c in cols}

    if "PVOL_NUMERO" in new_row:
        new_row["PVOL_NUMERO"] = form_data.get("pvol_num", "")
    if "PVOL_DATE" in new_row and isinstance(form_data.get("pvol_date"), datetime.date):
        new_row["PVOL_DATE"] = form_data["pvol_date"].strftime("%d/%m/%Y")
    if "PVOL_HEURE" in new_row and isinstance(form_data.get("pvol_heure"), datetime.time):
        new_row["PVOL_HEURE"] = form_data["pvol_heure"].strftime("%H:%M")
    if "PVOL_FK_DESTINATION" in new_row:
        new_row["PVOL_FK_DESTINATION"] = form_data.get("pvol_dest", "")
    if "PVOL_ROUTE_API" in new_row:
        new_row["PVOL_ROUTE_API"] = form_data.get("pvol_route", "")

    df2 = pd.concat([df_vols, pd.DataFrame([new_row])], ignore_index=True)
    df2.to_excel(path_vols, index=False)
