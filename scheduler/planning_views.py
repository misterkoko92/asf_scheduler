# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict

import pandas as pd

from scheduler.planning_schema import normalize_planning_df
from utils.datetime_utils import parse_date_series


def _strip_af_prefix(value: object) -> str:
    s = str(value or "").strip()
    if s.upper().startswith("AF"):
        s = s.replace("AF", "").strip()
    return s.replace(".0", "").strip()

def _build_dest_city_map(df_paramdest: pd.DataFrame | None) -> Dict[str, str]:
    if df_paramdest is None or getattr(df_paramdest, "empty", True):
        return {}
    return {
        str(r.get("Dest_IATA", "")).strip().upper(): str(r.get("Dest_Ville", "")).strip()
        for _, r in df_paramdest.iterrows()
        if str(r.get("Dest_IATA", "")).strip()
    }

def _build_dest_maps(df_paramdest: pd.DataFrame | None) -> tuple[Dict[str, str], Dict[str, str]]:
    iata_to_city = _build_dest_city_map(df_paramdest)
    city_to_iata = {str(v).strip().upper(): k for k, v in iata_to_city.items() if str(v).strip()}
    return iata_to_city, city_to_iata


def build_export_view(
    planning_df: pd.DataFrame | None,
    *,
    df_paramdest: pd.DataFrame | None = None,
    df_vols: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Construit une vue export à partir du planning canonique.
    Ajoute Dest_Ville, IATA et Routing si disponibles.
    """
    df = normalize_planning_df(planning_df)
    if df.empty:
        return df

    df_out = df.copy()
    df_out["Date_Vol"] = parse_date_series(df_out["Date_Vol"]).dt.date
    df_out["Numero_Vol"] = df_out["Numero_Vol"].apply(_strip_af_prefix)

    dest_raw = df_out["Destination"].astype(str).str.strip()
    dest_up = dest_raw.str.upper()
    iata_to_city, city_to_iata = _build_dest_maps(df_paramdest)

    is_iata = dest_up.str.len() == 3
    iata_series = df_out["IATA"] if "IATA" in df_out.columns else pd.Series([""] * len(df_out), index=df_out.index)
    df_out["IATA"] = iata_series.astype(str).str.strip().str.upper()
    df_out.loc[is_iata, "IATA"] = dest_up[is_iata]
    df_out.loc[~is_iata, "IATA"] = dest_up[~is_iata].map(city_to_iata).fillna(df_out.loc[~is_iata, "IATA"])

    df_out["Dest_Ville"] = ""
    df_out.loc[is_iata, "Dest_Ville"] = dest_up[is_iata].map(iata_to_city).fillna(dest_raw[is_iata])
    df_out.loc[~is_iata, "Dest_Ville"] = dest_raw[~is_iata]
    df_out["Dest_Ville"] = df_out["Dest_Ville"].fillna("")

    if df_vols is not None and not getattr(df_vols, "empty", True):
        vols = df_vols.copy()
        vols["Date_Vol"] = parse_date_series(vols.get("Date_Vol", "")).dt.date
        vols["Numero_Vol"] = vols.get("Numero_Vol", "").apply(_strip_af_prefix)
        vols["IATA"] = vols.get("IATA", "").astype(str).str.strip().str.upper()
        vols["Destination"] = vols.get("Destination", "").astype(str).str.strip()
        # Fallback ville depuis vols si ParamDest absent
        if not iata_to_city and "IATA" in vols.columns and "Destination" in vols.columns:
            map_iata_city = (
                vols.dropna(subset=["IATA"])
                .drop_duplicates(subset=["IATA"])
                .set_index("IATA")["Destination"]
                .astype(str)
                .to_dict()
            )
            df_out["Dest_Ville"] = df_out["Destination"].map(map_iata_city).fillna(df_out["Dest_Ville"])

        # Fallback IATA depuis vols si encore vide
        mask_iata_empty = df_out["IATA"].astype(str).str.strip().eq("")
        if mask_iata_empty.any() and "Destination" in vols.columns and "IATA" in vols.columns:
            city_to_iata_vols = (
                vols.dropna(subset=["Destination", "IATA"])
                .assign(Dest_UP=lambda d: d["Destination"].astype(str).str.strip().str.upper())
                .drop_duplicates(subset=["Dest_UP"])
                .set_index("Dest_UP")["IATA"]
                .astype(str)
                .to_dict()
            )
            df_out.loc[mask_iata_empty, "IATA"] = (
                dest_up[mask_iata_empty].map(city_to_iata_vols).fillna(df_out.loc[mask_iata_empty, "IATA"])
            )

    if "Routing" not in df_out.columns:
        df_out["Routing"] = ""
    df_out["Routing"] = df_out["Routing"].fillna("")

    return df_out


def build_comm_base(planning_df: pd.DataFrame | None) -> pd.DataFrame:
    """
    Base communication à partir du planning canonique.
    Ajoute les colonnes standards attendues par la communication.
    """
    df = normalize_planning_df(planning_df)
    if df.empty:
        return df

    df_out = df.copy()
    df_out["DATE"] = df_out["Date_Vol"]
    df_out["HEURE VOL"] = df_out["Heure_Vol"]
    df_out["NUMERO VOL"] = df_out["Numero_Vol"]
    df_out["DESTINATION"] = df_out["Destination"]
    df_out["NUMERO BE"] = df_out["BE_Numero"]
    df_out["NOMBRE COLIS"] = df_out["BE_Nb_Colis"]
    df_out["TYPE"] = df_out["BE_Type"]
    df_out["EXPEDITEUR"] = df_out["BE_Expediteur"]
    df_out["DESTINATAIRE"] = df_out["BE_Destinataire"]
    df_out["BENEVOLE"] = df_out["Benevole"]
    df_out["BENEVOLE_ID"] = df_out["ID"]
    df_out["Telephone"] = df_out["Telephone"]
    return df_out
