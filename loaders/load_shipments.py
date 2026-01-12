# loaders/load_shipments.py
# -*- coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path
import datetime as dt
import numpy as np
import pandas as pd

from scheduler.models import Shipment
from scheduler.config_paths import TABLEAU_DE_BORD, SHEET_MAG_CENTRAL
from scheduler.be_rules import compute_be_priority, compute_equiv_colis
from scheduler import be_manager
from loaders.universal_loader import load_and_normalize
from scheduler.column_map import column_map_mag_central
from scheduler.format_rules import format_be_numero
from loaders.load_params import get_param_be
from utils.cache_utils import file_mtime
from utils.ui_notifications import warn_ui

try:
    import streamlit as st
except Exception:
    st = None


# ======================================================================
# Helpers
# ======================================================================

def _parse_time_generic(val) -> dt.time | None:
    """Retourne un time depuis formats multiples (HHhMM, HH:MM, HH:MM:SS, numerique)."""
    if val in ("", None):
        return None
    if isinstance(val, dt.time):
        return val
    sval = str(val).strip()
    for fmt in ("%Hh%M", "%H:%M:%S", "%H:%M"):
        try:
            return dt.datetime.strptime(sval, fmt).time()
        except Exception:
            continue
    try:
        num = float(sval)
        hours = int(num)
        minutes = int(round((num - hours) * 60))
        return dt.time(hour=hours, minute=minutes)
    except Exception:
        return None


# ======================================================================
# VERSION DATAFRAME — Chargement complet MAG CENTRAL + ParamBE
# ======================================================================

def load_shipments_df(
    planifiables_only: bool = True,
    *,
    tdb_path: Path | None = None,
    param_be_raw: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Charge les BE depuis MAG CENTRAL + ParamBE et retourne un DataFrame normalise.
    planifiables_only=True => filtre BE_Statut == 'D'.
    """

    print("\n=== LOAD_SHIPMENTS_DF ===")

    tableau_de_bord = tdb_path or TABLEAU_DE_BORD
    df_raw = load_and_normalize(
        path=tableau_de_bord,
        sheet_name=SHEET_MAG_CENTRAL,
        mapping=column_map_mag_central,
        header=5,
    )

    print(f"-> BE bruts charges : {len(df_raw)}")
    if not isinstance(df_raw, pd.DataFrame):
        warn_ui("MAG CENTRAL illisible (format invalide).")
        df_raw = pd.DataFrame()

    expected_cols = [
        col
        for col in column_map_mag_central.values()
        if col and not str(col).startswith("_IGNORE")
    ]
    for col in expected_cols:
        if col not in df_raw.columns:
            df_raw[col] = ""

    if param_be_raw is None:
        try:
            param_be_raw = get_param_be()
            print(f"ParamBE charge automatiquement : {len(param_be_raw)} lignes")
        except Exception:
            print("ParamBE introuvable ou illisible - valeurs par defaut.")
            warn_ui("ParamBE introuvable ou illisible - valeurs par defaut.")
            param_be_raw = pd.DataFrame(columns=["Type", "Priorite", "Coeff_Equiv"])

    param_be = be_manager.normalize_param_be(param_be_raw)

    df = df_raw.copy()
    if "BE_Statut" not in df.columns:
        df["BE_Statut"] = ""
    df["BE_Statut"] = df["BE_Statut"].astype(str).str.strip().str.upper()
    if planifiables_only:
        df = df[df["BE_Statut"] == "D"].copy()

    print(f"-> BE planifiables : {len(df)}")

    def _row_to_shipment(row):
        return Shipment(
            be_numero=row.get("BE_Numero"),
            nb_colis_physiques=row.get("BE_Nb_Colis"),
            type_colis=row.get("BE_Type"),
            expediteur=row.get("BE_Expediteur"),
            customs=row.get("BE_Douane"),
            status=row.get("BE_Statut"),
            special=row.get("BE_Special"),
            dest=row.get("Destination"),
            nb_hf=0,
            priority=0,
        )

    def _safe_priority(row):
        val = compute_be_priority(_row_to_shipment(row), param_be)
        if isinstance(val, pd.DataFrame):
            try:
                val = val.iloc[0, 0]
            except Exception:
                val = val.values.flatten()[0] if val.values.size else 0
        if isinstance(val, (list, tuple)):
            return val[0] if val else 0
        if isinstance(val, pd.Series):
            return val.iloc[0] if not val.empty else 0
        if isinstance(val, np.ndarray):
            return val.ravel()[0] if val.size else 0
        if isinstance(val, dict):
            try:
                return next(iter(val.values()))
            except Exception:
                return 0
        return val

    def _safe_equiv(row):
        val = compute_equiv_colis(_row_to_shipment(row), param_be)
        if isinstance(val, pd.DataFrame):
            try:
                val = val.iloc[0, 0]
            except Exception:
                val = val.values.flatten()[0] if val.values.size else 0
        if isinstance(val, (list, tuple)):
            return val[0] if val else 0
        if isinstance(val, pd.Series):
            return val.iloc[0] if not val.empty else 0
        if isinstance(val, np.ndarray):
            return val.ravel()[0] if val.size else 0
        if isinstance(val, dict):
            try:
                return next(iter(val.values()))
            except Exception:
                return 0
        return val

    priorities = df.apply(_safe_priority, axis=1)
    if isinstance(priorities, pd.DataFrame):
        priorities = priorities.iloc[:, 0]
    df["Priorite"] = pd.to_numeric(priorities, errors="coerce").fillna(0)

    equivs = df.apply(_safe_equiv, axis=1)
    if isinstance(equivs, pd.DataFrame):
        equivs = equivs.iloc[:, 0]
    df["Equiv_Colis"] = pd.to_numeric(equivs, errors="coerce").fillna(0)

    def _coerce_int(col: str):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    for col in [
        "BE_Numero",
        "BE_Nb_Colis",
        "BE_Numero_MAG",
        "BE_Nb_Colis_MAG",
        "Numero_Facture",
        "Equiv_Colis",
    ]:
        _coerce_int(col)

    df["BE_Statut"] = df["BE_Statut"].astype(str).str.strip().str.upper()
    if "Destination" not in df.columns:
        df["Destination"] = ""
    df["Destination"] = df["Destination"].astype(str).str.strip().str.upper()

    latest_impr_date = None
    if "BE_Date_Impression" in df.columns:
        try:
            latest_impr_date = pd.to_datetime(df["BE_Date_Impression"], errors="coerce").max(skipna=True)
        except Exception:
            latest_impr_date = None

    for col in [c for c in df.columns if "Date" in c]:
        try:
            dt_col = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
            df[col] = dt_col.dt.date
            df[f"{col}_str"] = dt_col.dt.strftime("%d/%m/%y")
        except Exception:
            pass

    if "Heure_Vol" in df.columns:
        df["Heure_Vol"] = df["Heure_Vol"].apply(_parse_time_generic)
        df["Heure_Vol_str"] = df["Heure_Vol"].apply(
            lambda t: t.strftime("%Hh%M") if isinstance(t, dt.time) else ""
        )
        df["Heure_Display"] = df["Heure_Vol_str"]
    if "BE_Date_Vol" in df.columns:
        df["Date_Display"] = df["BE_Date_Vol_str"] if "BE_Date_Vol_str" in df.columns else ""

    def _fmt_be(row):
        be_raw = row.get("BE_Numero")
        be_date = row.get("BE_Date_Impression")
        fmt, _ = format_be_numero(be_raw, be_date, latest_impr_date)
        return fmt

    df["BE_Numero_YYNNNN"] = df.apply(_fmt_be, axis=1)
    df["BE_Numero"] = df["BE_Numero_YYNNNN"].fillna(df["BE_Numero"].astype(str))

    if "Equiv_Colis" in df.columns:
        df["Equiv_Colis"] = pd.to_numeric(df["Equiv_Colis"], errors="coerce")

    df = df.reset_index(drop=True)

    print(f"load_shipments_df OK : {len(df)} lignes, {len(df.columns)} colonnes")

    return df


# Cache Streamlit (optionnel)
if st is not None and hasattr(st, "cache_data"):

    @st.cache_data(show_spinner=False)
    def _get_shipments_df_cached(planifiables_only: bool, tdb_path: str, tdb_mtime: float) -> pd.DataFrame:
        return load_shipments_df(planifiables_only=planifiables_only, tdb_path=Path(tdb_path))

    def get_shipments_df_cached(planifiables_only: bool = True, tdb_path: Path | None = None) -> pd.DataFrame:
        path = tdb_path or TABLEAU_DE_BORD
        return _get_shipments_df_cached(planifiables_only, str(path), file_mtime(path))

else:

    def get_shipments_df_cached(planifiables_only: bool = True, tdb_path: Path | None = None) -> pd.DataFrame:
        return load_shipments_df(planifiables_only=planifiables_only, tdb_path=tdb_path)


def clear_shipments_cache() -> None:
    cached = globals().get("_get_shipments_df_cached") or globals().get("get_shipments_df_cached")
    if cached is not None and hasattr(cached, "clear"):
        try:
            cached.clear()
        except Exception:
            pass
