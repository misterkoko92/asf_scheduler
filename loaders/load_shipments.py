# loaders/load_shipments.py
# -*- coding: utf-8 -*-

from typing import List, Dict
import uuid
import pandas as pd
import numpy as np

from scheduler.models import Shipment
from scheduler.config_paths import TABLEAU_DE_BORD, SHEET_MAG_CENTRAL

from scheduler.be_rules import (
    compute_be_priority,
    compute_equiv_colis,
    compute_status_row,
    STATUS_PLANIFIABLE,
)
from scheduler import be_manager

from loaders.universal_loader import load_and_normalize
from scheduler.column_map import column_map_mag_central
from scheduler.column_map import column_map_param_be
from scheduler.format_rules import format_be_numero
from scheduler.config_paths import SHEET_PARAM_BE


# ======================================================================
#  CLEANERS — robustes & minimalistes
# ======================================================================

def _clean_date(df, col, dayfirst=True):
    """Nettoyage générique des dates, robuste, silencieux."""
    if col not in df.columns:
        df[col] = None
        return df

    df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=dayfirst)
    return df


def _clean_all_dates(df):
    """Nettoie seulement les colonnes réellement utilisées par le moteur."""
    for col in [
        "BE_Date_Conditionnement",
        "BE_Date_Vol",
        "BE_Date_Impression",
        "BE_Date_Depart_Mag",
    ]:
        df = _clean_date(df, col)
    return df


# ======================================================================
#  NORMALISATION SIMPLE
# ======================================================================

def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Normalisation minimaliste — juste ce qu'il faut pour stabilité."""
    if "Destination" in df.columns:
        df["Destination"] = df["Destination"].astype(str).str.strip()

    if "BE_Special" in df.columns:
        df["BE_Special"] = (
            df["BE_Special"]
            .astype(str)
            .fillna("")
            .str.strip()
            .str.lower()
        )

    return df


# ======================================================================
#  LOAD SHIPMENTS — VERSION FINALE (STATUT BE = source de vérité)
# ======================================================================

def load_shipments(param_be_raw) -> List[Shipment]:
    """
    Charge les BE du MAG CENTRAL.

    `param_be_raw` peut être :
      - un DataFrame (df_param_be UI)
      - un dict {type: {"Priorite_Type": int, "Equiv": int}}

    Applique : Statut BE (colonne 'BE_Statut') comme vérité absolue.
    Seuls les BE ayant 'D' sont planifiables.
    """

    # ------------------------------------------------------------------
    # 0) Normalisation ParamBE (clé du problème 'AUTRE' / 'Priorite_Type')
    # ------------------------------------------------------------------
    param_be = be_manager.normalize_param_be(param_be_raw)

    # ------------------------------------------------------------------
    # 1) Lecture Excel + normalisation
    # ------------------------------------------------------------------
    df = load_and_normalize(
        path=TABLEAU_DE_BORD,
        sheet_name=SHEET_MAG_CENTRAL,
        mapping=column_map_mag_central,
        header=5,
    )

    df = df.fillna("")
    print(f"\n➡ BE bruts chargés : {len(df)}")

    # ------------------------------------------------------------------
    # 2) Nettoyage des dates
    # ------------------------------------------------------------------
    df = _clean_all_dates(df)

    latest_impr_date = None
    if "BE_Date_Impression" in df.columns:
        latest_impr_date = df["BE_Date_Impression"].max(skipna=True)

    # ------------------------------------------------------------------
    # 3) Normalisation
    # ------------------------------------------------------------------
    df = _normalize(df)

    # ------------------------------------------------------------------
    # 4) CALCUL STATUT — VERSION AVEC SOURCE DE VÉRITÉ : BE_Statut
    # ------------------------------------------------------------------
    if "BE_Statut" in df.columns:
        df["Status_BE"] = (
            df["BE_Statut"]
            .astype(str)
            .str.strip()
            .str.upper()
        )
        print("\n=== STATUTS BE (depuis Excel) ===")
        print(df["Status_BE"].value_counts(dropna=False))

    else:
        # sécurité si la colonne n’existe pas (fallback)
        print("⚠️ Colonne 'BE_Statut' absente → fallback compute_status_row()")
        df["Status_BE"] = df.apply(compute_status_row, axis=1)

    # ------------------------------------------------------------------
    # 5) Filtre PLANIFIABLE = statut 'D'
    # ------------------------------------------------------------------
    df_planif = df[df["Status_BE"] == "D"].copy()

    print(f"\n🎯 TOTAL BE À PLANIFIER (Statut BE = 'D') : {len(df_planif)}")
    print("=======================================================\n")

    shipments: List[Shipment] = []

    # ------------------------------------------------------------------
    # 6) Construction des objets Shipment
    # ------------------------------------------------------------------
    for _, r in df_planif.iterrows():

        # ------------------------------
        # Numéro BE formaté
        # ------------------------------
        raw_num = str(r.get("BE_Numero", "")).strip()
        if not raw_num:
            continue

        be_fmt, suffix = format_be_numero(
            raw_value=raw_num,
            date_impression=r.get("BE_Date_Impression", None),
            fallback_latest_date=latest_impr_date,
        )
        if not be_fmt:
            print(f"⚠️ BE ignoré (format impossible) : {raw_num}")
            continue

        # ------------------------------
        # Destination
        # ------------------------------
        dest = str(r.get("Destination", "")).upper().strip()
        if not dest:
            continue

        # ------------------------------
        # Colis
        # ------------------------------
        raw_nb = str(r.get("BE_Nb_Colis", "")).replace(",", ".").strip()
        try:
            nb_colis = int(float(raw_nb)) if raw_nb else 0
        except Exception:
            nb_colis = 0

        # ------------------------------
        # Champs utilisateur
        # ------------------------------
        type_mag = str(r.get("BE_Type", "")).upper().strip()
        expediteur_mag = str(r.get("BE_Expediteur", "")).strip()
        destinataire_mag = str(r.get("BE_Destinataire", "")).strip()
        special_mag = str(r.get("BE_Special", "")).strip() or None
        customs = str(r.get("BE_Douane", "")).upper().strip() in ("OUI", "YES", "1", "X")

        # ------------------------------
        # Construction Shipment (provisoire)
        # ------------------------------
        temp = Shipment(
            uid=str(uuid.uuid4()),
            be_numero=be_fmt,
            dest=dest,
            nb_colis_physiques=nb_colis,
            nb_hf=0,
            priority=0,
            type_colis=type_mag,
            expediteur=expediteur_mag,
            customs=customs,
            special=special_mag,
            status=STATUS_PLANIFIABLE,
            equiv_colis=0,
        )

        # === PRIORITÉ ===
        temp.priority = compute_be_priority(temp, param_be)

        # === COLIS ÉQUIVALENTS ===
        temp.equiv_colis = compute_equiv_colis(temp, param_be)

        # ------------------------------
        # Champs enrichis
        # ------------------------------
        temp.be_numero_suffix = suffix
        temp.type_mag = type_mag
        temp.expediteur_mag = expediteur_mag
        temp.destinataire_mag = destinataire_mag
        temp.nb_colis_mag = nb_colis

        temp.date_conditionnement = r.get("BE_Date_Conditionnement", None)
        temp.date_impression_be = r.get("BE_Date_Impression", None)
        temp.date_depart_mag = r.get("BE_Date_Depart_Mag", None)
        temp.date_vol_mag = r.get("BE_Date_Vol", None)
        temp.delai_mag = r.get("BE_Delai_Mag", None)
        temp.delai_depart = r.get("BE_Delai_Depart", None)

        temp.special_mag = special_mag
        temp.douane_brut = r.get("BE_Douane", "")

        # Dump brut utile en debug / UI
        temp.mag_fields = {
            "BE_Numero_Brut": raw_num,
            "BE_Numero_Formatted": be_fmt,
            "BE_Numero_Suffix": suffix,
            "Status_BE": r.get("Status_BE"),
        }

        shipments.append(temp)

    print(f"➡ BE chargés (PLANIFIABLES) : {len(shipments)}\n")
    return shipments

# =====================================================================
# VERSION DATAFRAME — pour audit & communication
# =====================================================================
# =====================================================================
# VERSION DATAFRAME — Chargement complet MAG CENTRAL + ParamBE
# =====================================================================
def load_shipments_df() -> pd.DataFrame:
    """
    Charge les BE depuis MAG CENTRAL + ParamBE
    et retourne un DataFrame normalisé (pas une liste).
    Utilisable hors Streamlit.
    """

    print("\n=== LOAD_SHIPMENTS_DF ===")

    # -----------------------------------------------------------
    # 1) Charger MAG CENTRAL (CSV sheet dans TABLEAU_DE_BORD)
    # -----------------------------------------------------------
    df_raw = load_and_normalize(
        path=TABLEAU_DE_BORD,
        sheet_name=SHEET_MAG_CENTRAL,
        mapping=column_map_mag_central,
        header=5,
    )

    print(f"➡ BE bruts chargés : {len(df_raw)}")

    # -----------------------------------------------------------
    # 2) Charger ParamBE automatiquement
    # -----------------------------------------------------------
    try:
        param_be_raw = load_and_normalize(
            path=TABLEAU_DE_BORD,
            sheet_name=SHEET_PARAM_BE,
            mapping=column_map_param_be,
            header=0,
        )
        print(f"ParamBE chargé automatiquement : {len(param_be_raw)} lignes")
    except Exception as e:
        print("⚠️ ParamBE introuvable ou illisible — valeurs par défaut utilisées")
        param_be_raw = pd.DataFrame(columns=["Type", "Priorite", "Coeff_Equiv"])

    # Normalisation ParamBE
    param_be = be_manager.normalize_param_be(param_be_raw)

    # -----------------------------------------------------------
    # 3) Filtrer les BE planifiables (Statut BE = 'D')
    # -----------------------------------------------------------
    df = df_raw.copy()
    df["BE_Statut"] = df["BE_Statut"].astype(str).str.strip().str.upper()
    df = df[df["BE_Statut"] == "D"].copy()

    print(f"➡ BE planifiables : {len(df)}")

    # -----------------------------------------------------------
    # 4) Calcul priorité + équivalences (utilise l'API Shipment)
    # -----------------------------------------------------------
    def _row_to_shipment(row):
        from scheduler.models import Shipment
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
        # Flatten exotic returns (Series/DataFrame/tuple)
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
        # Force scalar fallback
        if isinstance(val, dict):
            # take first value
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

    df["Priorite"] = df.apply(_safe_priority, axis=1)
    df["Equiv_Colis"] = df.apply(_safe_equiv, axis=1)

    # -----------------------------------------------------------
    # 5) Nettoyage final
    # -----------------------------------------------------------
    keep_cols = [
        "BE_Numero",
        "BE_Nb_Colis",
        "BE_Type",
        "BE_Expediteur",
        "BE_Destinataire",
        "BE_Douane",
        "BE_Statut",
        "Priorite",
        "Equiv_Colis",
        "Destination",
    ]

    # Conserver uniquement les colonnes disponibles
    keep_cols = [c for c in keep_cols if c in df.columns]
    df = df[keep_cols].reset_index(drop=True)

    print(f"✔ load_shipments_df OK — {len(df)} lignes, {len(df.columns)} colonnes")

    return df
