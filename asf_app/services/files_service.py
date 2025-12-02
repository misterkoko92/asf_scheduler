# asf_app/services/files_service.py
# -*- coding: utf-8 -*-

import os
import datetime
from pathlib import Path
from typing import Dict

import pandas as pd


# ============================================================
# Horodatage fichier
# ============================================================

def pretty_mtime(path_str: str) -> str:
    try:
        ts = os.path.getmtime(path_str)
        dt = datetime.datetime.fromtimestamp(ts)
        return dt.strftime("%d/%m/%Y à %H:%M")
    except Exception:
        return "N/A"


# ============================================================
# Lecture Excel robuste
# ============================================================

def read_excel_sheet(path: str | Path, sheet_name: str, dtype=str) -> pd.DataFrame:
    """
    Lecture robuste d’un onglet Excel.
    - dtype=str → homogénéité
    - NaN → ""
    - support xlsx uniquement
    """
    return (
        pd.read_excel(path, sheet_name=sheet_name, dtype=dtype, engine="openpyxl")
        .fillna("")
    )


# ============================================================
# Sauvegarde Excel SAFE : écrase proprement l’onglet
# ============================================================

def save_excel_sheet(path: str | Path, sheet_name: str, df: pd.DataFrame) -> None:
    """
    Sauvegarde un onglet en remplaçant proprement son contenu.
    - Ouvre le fichier avec openpyxl
    - Remplace la feuille
    - Ne détruit pas les autres onglets
    """
    from openpyxl import load_workbook

    path = Path(path)

    # Si le fichier n'existe pas → on crée un workbook
    if not path.exists():
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
        return

    # Sinon → on charge et on remplace
    wb = load_workbook(path)
    if sheet_name in wb.sheetnames:
        del wb[sheet_name]

    ws = wb.create_sheet(sheet_name)
    # Export pandas → openpyxl
    from openpyxl.utils.dataframe import dataframe_to_rows

    for r in dataframe_to_rows(df, index=False, header=True):
        ws.append(r)

    wb.save(path)


# ============================================================
# Ajouter une ligne à un onglet (respect colonnes)
# ============================================================

def append_row_to_sheet(path: str | Path, sheet_name: str, new_row: Dict[str, str]) -> None:
    df = read_excel_sheet(path, sheet_name)
    cols = df.columns.tolist()

    row = {c: "" for c in cols}
    row.update({k: v for k, v in new_row.items() if k in row})

    df2 = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    save_excel_sheet(path, sheet_name, df2)
