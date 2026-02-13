# asf_app/services/params_service.py
# -*- coding: utf-8 -*-

import datetime
from typing import Dict

import pandas as pd

from scheduler.config_paths import (
    SHEET_PARAM_BE,
    SHEET_PARAM_BENEV,
    SHEET_PARAM_DEST,
    SHEET_VOLS,
)
from utils.datetime_utils import format_date_value, format_time_value

from .files_service import read_excel_sheet, save_excel_sheet

# =====================================================================
# PARAM DEST
# =====================================================================

def load_paramdest(path_tdb: str) -> pd.DataFrame:
    return read_excel_sheet(path_tdb, SHEET_PARAM_DEST)


def save_paramdest(path_tdb: str, df: pd.DataFrame) -> None:
    save_excel_sheet(path_tdb, SHEET_PARAM_DEST, df)


# =====================================================================
# PARAM BE
# =====================================================================

def load_parambe(path_tdb: str) -> pd.DataFrame:
    return read_excel_sheet(path_tdb, SHEET_PARAM_BE)


def save_parambe(path_tdb: str, df: pd.DataFrame) -> None:
    save_excel_sheet(path_tdb, SHEET_PARAM_BE, df)


# =====================================================================
# PARAM BÉNÉVOLES
# =====================================================================

def load_parambenev(path_benev: str) -> pd.DataFrame:
    return read_excel_sheet(path_benev, SHEET_PARAM_BENEV)


def save_parambenev(path_benev: str, df: pd.DataFrame) -> None:
    save_excel_sheet(path_benev, SHEET_PARAM_BENEV, df)


# =====================================================================
# AJOUT MANUEL DISPONIBILITÉ BÉNÉVOLE
# =====================================================================

def add_benevole_dispo(path_benev: str, form_data: Dict) -> None:
    """
    Ajoute une disponibilité dans ParamBenev.
    Prend en compte la règle ASF :
      Heure_ARRIVEE = heure entrée - 3 heures
    """
    df = load_parambenev(path_benev)
    cols = df.columns.tolist()
    new_row = {c: "" for c in cols}

    # Identité
    new_row["ID"] = form_data.get("id_ben", "")
    new_row["BENEVOLE"] = (
        form_data.get("benevole_label")
        or f"{form_data.get('prenom', '')} {form_data.get('nom', '')}".strip()
    )
    new_row["NOM"] = form_data.get("nom", "")
    new_row["PRENOM"] = form_data.get("prenom", "")
    new_row["PRENOM_COURT"] = form_data.get("prenom_court", "")

    # Date
    date_dispo = form_data.get("date_dispo")
    if isinstance(date_dispo, datetime.date):
        new_row["DATE"] = format_date_value(date_dispo, fmt="%d/%m/%Y", default="")

    # Heure ARRIVÉE = input - 3 heures
    h_arr_input = form_data.get("h_arr")
    if isinstance(h_arr_input, datetime.time):
        h_real = (
            datetime.datetime.combine(datetime.date.today(), h_arr_input)
            - datetime.timedelta(hours=3)
        ).time()
        new_row["HEURE_ARRIVEE"] = format_time_value(h_real, fmt="%H:%M", default="")

    # Heure départ
    h_dep = form_data.get("h_dep")
    if isinstance(h_dep, datetime.time):
        new_row["HEURE_DEPART"] = format_time_value(h_dep, fmt="%H:%M", default="")

    # Contraintes
    for f in ["MAX_JOURS_SEMAINE", "MAX_EXP_SEMAINE", "MAX_EXP_JOUR", "ATTENTE_MAX_H", "MAX_COLIS_VOL"]:
        if f in new_row:
            new_row[f] = form_data.get(f.lower(), "")

    # Enregistrer
    df2 = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_parambenev(path_benev, df2)


# =====================================================================
# AJOUT MANUEL D’UN VOL PVOL
# =====================================================================

def add_vol(path_vols: str, form_data: Dict) -> None:
    """
    Ajoute un vol manuel :
      - PVOL_NUMERO (texte)
      - PVOL_DATE (dd/mm/yyyy)
      - PVOL_HEURE (HH:MM)
      - PVOL_FK_DESTINATION (IATA / code ASF)
      - PVOL_ROUTE_API (JSON-like)
    """

    df_vols = (
        pd.read_excel(path_vols, dtype=str, engine="openpyxl")
        .fillna("")
    )
    cols = df_vols.columns.tolist()

    new_row = {c: "" for c in cols}

    # Numéro vol
    new_row["PVOL_NUMERO"] = form_data.get("pvol_num", "")

    # Date
    d = form_data.get("pvol_date")
    if isinstance(d, datetime.date):
        new_row["PVOL_DATE"] = format_date_value(d, fmt="%d/%m/%Y", default="")

    # Heure
    h = form_data.get("pvol_heure")
    if isinstance(h, datetime.time):
        new_row["PVOL_HEURE"] = format_time_value(h, fmt="%H:%M", default="")

    # Destination
    new_row["PVOL_FK_DESTINATION"] = form_data.get("pvol_dest", "")

    # Routing API
    new_row["PVOL_ROUTE_API"] = form_data.get("pvol_route", "")

    # Ajout
    df2 = pd.concat([df_vols, pd.DataFrame([new_row])], ignore_index=True)
    save_excel_sheet(path_vols, SHEET_VOLS, df2)
