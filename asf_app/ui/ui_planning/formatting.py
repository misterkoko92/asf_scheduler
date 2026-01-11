# -*- coding: utf-8 -*-

from __future__ import annotations

import pandas as pd

from scheduler.format_rules import format_vol_display
from utils.identifiers import normalize_be_number


def _date_longue_fr(series_date):
    """Retourne une série 'Lundi 01/12/25' à partir d'une colonne DATE."""
    jours = {
        "Monday": "Lundi",
        "Tuesday": "Mardi",
        "Wednesday": "Mercredi",
        "Thursday": "Jeudi",
        "Friday": "Vendredi",
        "Saturday": "Samedi",
        "Sunday": "Dimanche",
    }
    dt = pd.to_datetime(series_date, errors="coerce")
    return dt.apply(
        lambda d: f"{jours.get(d.day_name(), d.strftime('%A'))} {d.strftime('%d/%m/%y')}"
        if pd.notna(d) else ""
    )


def _format_vol_display(v):
    """Formatte un numéro de vol en 'AF XXX'."""
    return format_vol_display(v)


def build_preview(df_planning: pd.DataFrame, df_paramdest: pd.DataFrame) -> pd.DataFrame:
    preview_cols = [
        "Date_Vol",
        "Benevole",
        "Ville",
        "Destination",
        "Numero_Vol",
        "Heure_Vol",
        "BE_Numero",
        "BE_Nb_Colis",
        "BE_Type",
        "BE_Expediteur",
        "Telephone",
    ]
    df_preview = df_planning.copy()

    # Mapping IATA -> Ville à partir de ParamDest
    map_iata_to_ville = {}
    try:
        map_iata_to_ville = (
            df_paramdest.dropna(subset=["Dest_IATA"])
            .drop_duplicates(subset=["Dest_IATA"])
            .set_index("Dest_IATA")["Dest_Ville"]
            .to_dict()
        )
    except Exception:
        map_iata_to_ville = {}

    df_preview["Destination"] = df_preview.get("Destination", "")
    df_preview["Destination_UP"] = df_preview["Destination"].astype(str).str.strip().str.upper()
    df_preview["Ville"] = df_preview["Destination_UP"].map(map_iata_to_ville).fillna(df_preview["Destination_UP"])

    # Format numéro de vol en AFXXX
    df_preview["Numero_Vol"] = df_preview.get("Numero_Vol", "").apply(_format_vol_display)
    # Nombre de colis (entier)
    df_preview["BE_Nb_Colis"] = pd.to_numeric(df_preview.get("BE_Nb_Colis", 0), errors="coerce").fillna(0).astype(int)
    # Heure format HHhMM
    df_preview["Heure_Vol"] = pd.to_datetime(df_preview.get("Heure_Vol", ""), errors="coerce").dt.strftime("%Hh%M")
    # BE formaté en YYNNNN
    df_preview["BE_Numero"] = df_preview.get("BE_Numero", "").apply(normalize_be_number)

    # Tri par date + heure
    try:
        df_preview["Date_Vol"] = pd.to_datetime(df_preview["Date_Vol"], errors="coerce")
        df_preview = df_preview.sort_values(by=["Date_Vol", "Heure_Vol"], kind="mergesort")
        df_preview["Date_Vol"] = df_preview["Date_Vol"].dt.date
    except Exception:
        pass

    for col in preview_cols:
        if col not in df_preview.columns:
            df_preview[col] = ""
    # Flag manuel (fond gris) sans afficher la colonne
    manual_mask = df_preview["_MANUEL"].fillna(False) if "_MANUEL" in df_preview.columns else pd.Series([False] * len(df_preview), index=df_preview.index)

    df_vis = df_preview[preview_cols].copy()

    def _style_manual(row):
        color = "background-color: #f2f2f2" if manual_mask.get(row.name, False) else ""
        return [color] * len(row)

    return df_vis.style.apply(_style_manual, axis=1)
