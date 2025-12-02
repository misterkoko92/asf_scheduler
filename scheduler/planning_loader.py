# -*- coding: utf-8 -*-
import pandas as pd
from pathlib import Path

DAY_NAMES = ["LUNDI","MARDI","MERCREDI","JEUDI","VENDREDI","SAMEDI","DIMANCHE"]
MONTH_NAMES = ["JANVIER","FEVRIER","MARS","AVRIL","MAI","JUIN","JUILLET",
               "AOUT","SEPTEMBRE","OCTOBRE","NOVEMBRE","DECEMBRE"]

def col_letter_to_index(letter: str) -> int:
    return ord(letter.upper()) - 65


def load_planning_from_index(path: Path, col_map: dict, start_row: int = 4) -> pd.DataFrame:

    if not path.exists():
        return pd.DataFrame()

    df_raw = pd.read_excel(path, sheet_name=0, header=None)
    if df_raw.empty:
        return pd.DataFrame()

    df = df_raw.iloc[start_row-1:].copy()
    n = len(df)

    important_cols = [c for c in range(df.shape[1]) if c != 0]
    to_drop = set()
    i = 0

    while i < n - 1:

        rowA = str(df.iloc[i, 0]).strip().upper()
        nextA = str(df.iloc[i+1, 0]).strip().upper()

        if rowA == "" and nextA in DAY_NAMES:
            start = i
            i += 2
            month_found = False

            while i < n:
                cellA = str(df.iloc[i, 0]).strip().upper()

                if cellA in MONTH_NAMES:
                    month_found = True

                elif month_found and all(
                    (pd.isna(df.iloc[i, c]) or str(df.iloc[i, c]).strip() == "")
                    for c in important_cols
                ):
                    end = i
                    to_drop.update(range(start, end+1))
                    break

                i += 1

        i += 1

    df = df.drop(index=to_drop, errors="ignore").copy()

    extracted = {}
    for letter, new_col in col_map.items():
        idx = col_letter_to_index(letter)
        extracted[new_col] = df.iloc[:, idx] if idx < df.shape[1] else None

    df_final = pd.DataFrame(extracted)

    df_final["be"] = df_final["be"].astype(str).str.strip()
    df_final = df_final[df_final["be"].str.match(r"^\d{5,6}$", na=False)]

    if df_final.empty:
        return pd.DataFrame()

    vol_cols = ["destination_nom","destination_iata","routing","vol_info","heure"]
    df_final[vol_cols] = df_final[vol_cols].ffill()

    for col in ["nom","destination_nom","destination_iata","routing",
                "vol_info","heure","type","expediteur","destinataire"]:
        if col in df_final.columns:
            df_final[col] = df_final[col].astype(str).str.strip()

    if "nb_colis" in df_final.columns:
        df_final["nb_colis"] = pd.to_numeric(df_final["nb_colis"], errors="coerce").fillna(0).astype(int)

    return df_final.reset_index(drop=True)
