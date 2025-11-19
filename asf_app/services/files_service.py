# asf_app/services/files_service.py
# -*- coding: utf-8 -*-
import os
import datetime
from pathlib import Path
from typing import Dict

import pandas as pd


def pretty_mtime(path_str: str) -> str:
    try:
        ts = os.path.getmtime(path_str)
        dt = datetime.datetime.fromtimestamp(ts)
        return dt.strftime("%d/%m/%Y à %H:%M")
    except Exception:
        return "N/A"


def read_excel_sheet(path: str | Path, sheet_name: str, dtype=str) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name=sheet_name, dtype=dtype).fillna("")


def save_excel_sheet(path: str | Path, sheet_name: str, df: pd.DataFrame) -> None:
    with pd.ExcelWriter(path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)


def append_row_to_sheet(path: str | Path, sheet_name: str, new_row: Dict[str, str]) -> None:
    df = read_excel_sheet(path, sheet_name)
    cols = df.columns.tolist()
    row = {c: "" for c in cols}
    row.update({k: v for k, v in new_row.items() if k in row})
    df2 = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    save_excel_sheet(path, sheet_name, df2)
