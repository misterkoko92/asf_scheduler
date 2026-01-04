# scheduler/planning_enrichment.py
# -*- coding: utf-8 -*-

"""
Enrichissement du planning brut (sortie moteur)
avec :
 - infos BE (TYPE, EXPEDITEUR, DESTINATAIRE…) depuis MAG CENTRAL
 - infos destination (VILLE, IATA, ROUTING…) via ParamDest + load_vols_df()
 - infos expéditeur depuis ParamExpéditeur
 - infos bénévoles depuis ParamBenev (ID prioritaire)
 - reconstruction des colonnes Excel (DATE LONGUE, ITEM, NOM formaté)
"""

import pandas as pd
from datetime import datetime

from scheduler.config_paths import (
    TABLEAU_DE_BORD,
    PLANNING_BENEVOLES,
    VOLS,
    SHEET_MAG_CENTRAL,
    SHEET_PARAM_BE,
    SHEET_PARAM_DEST,
    SHEET_PARAM_EXP,
    SHEET_PARAM_BENEV,
)

from loaders.universal_loader import load_and_normalize
from loaders.load_vols import load_vols_df

from scheduler.column_map import (
    column_map_mag_central,
    column_map_param_be,
    column_map_param_dest,
    column_map_param_expediteur,
    column_map_param_benev,
)
from scheduler.format_rules import format_be_numero


# ----------------------------------------------------------
#  Helper : Date longue FR
# ----------------------------------------------------------
def _date_longue(d):
    if pd.isna(d):
        return ""
    try:
        dt = pd.to_datetime(d)
        jours = {
            "Monday": "Lundi",
            "Tuesday": "Mardi",
            "Wednesday": "Mercredi",
            "Thursday": "Jeudi",
            "Friday": "Vendredi",
            "Saturday": "Samedi",
            "Sunday": "Dimanche",
        }
        jour = jours.get(dt.strftime("%A"), dt.strftime("%A"))
        return f"{jour} {dt.strftime('%d/%m/%Y')}"
    except Exception:
        return ""


# ----------------------------------------------------------
#  ENRICHISSEMENT PRINCIPAL
# ----------------------------------------------------------
def enrich_planning(df_planning: pd.DataFrame) -> pd.DataFrame:

    if df_planning is None or df_planning.empty:
        return pd.DataFrame()

    df = df_planning.copy()

    # ==========================================================
    # 1) CHARGEMENT DES TABLES PARAMÈTRES
    # ==========================================================
    df_mag = load_and_normalize(
        TABLEAU_DE_BORD, SHEET_MAG_CENTRAL, column_map_mag_central, header=5
    )

    df_paramdest = load_and_normalize(
        TABLEAU_DE_BORD, SHEET_PARAM_DEST, column_map_param_dest, header=0
    )

    df_paramexp = load_and_normalize(
        TABLEAU_DE_BORD, SHEET_PARAM_EXP, column_map_param_expediteur, header=0
    )

    df_parambe = load_and_normalize(
        TABLEAU_DE_BORD, SHEET_PARAM_BE, column_map_param_be, header=0
    )

    df_parambenev = load_and_normalize(
        PLANNING_BENEVOLES, SHEET_PARAM_BENEV, column_map_param_benev, header=0
    )

    # 🔥 NOUVEAU : version normalisée via load_vols_df()
    df_vols = load_vols_df()
    df_vols["IATA_UP"] = df_vols["IATA"].astype(str).str.upper().str.strip()
    df_vols_unique = df_vols.drop_duplicates(subset=["Numero_Vol", "Date_Vol"])

    # ---------- BE ----------
    def _fmt_be(raw, dt):
        fmt, _ = format_be_numero(raw_value=str(raw), date_impression=dt, fallback_latest_date=None)
        return fmt or str(raw)

    df_mag["BE_Numero_UP"] = df_mag.apply(
        lambda r: _fmt_be(r.get("BE_Numero"), r.get("BE_Date_Impression", None)).upper().strip(),
        axis=1,
    )
    df["BE_Numero_UP"] = df.get("BE_Numero", "")
    df["BE_Numero_UP"] = df["BE_Numero_UP"].astype(str).str.upper().str.strip()

    # ---------- Destination ----------
    df["Destination"] = df.get("Destination", "")
    df["Dest_IATA_UP"] = df["Destination"].astype(str).str.upper().str.strip()
    df_paramdest["Dest_IATA_UP"] = df_paramdest["Dest_IATA"].astype(str).str.upper().str.strip()

    # ---------- Expéditeur ----------
    df["BE_Expediteur"] = df.get("BE_Expediteur", "")
    df_paramexp["Expediteur_UP"] = df_paramexp["Expediteur_Nom"].astype(str).str.upper().str.strip()
    df["EXP_UP"] = df["BE_Expediteur"].astype(str).str.upper().str.strip()

    # ---------- Bénévole : ID prioritaire ----------
    df["ID"] = df.get("ID", "")
    df["ID_UP"] = df["ID"].astype(str).str.upper().str.strip()
    df_parambenev["ID_UP"] = df_parambenev["ID"].astype(str).str.upper().str.strip()

    df["Benevole"] = df.get("Benevole", "")
    df["Benev_UP"] = df["Benevole"].astype(str).str.upper().str.strip()
    df_parambenev["Benev_UP"] = df_parambenev["Benevole"].astype(str).str.upper().str.strip()


    # ==========================================================
    # 3) MERGE MAG CENTRAL ↦ Planning
    # ==========================================================
    df = df.merge(
        df_mag,
        how="left",
        on="BE_Numero_UP",
        suffixes=("", "_MAG")
    )

    # ==========================================================
    # 4) MERGE ParamDest via IATA (clé principale)
    # ==========================================================
    df = df.merge(
        df_paramdest,
        how="left",
        on="Dest_IATA_UP",
        suffixes=("", "_DEST")
    )

    # ==========================================================
    # 5) MERGE routing via df_vols normalisé
    # ==========================================================
    df = df.merge(
        df_vols_unique[["IATA_UP", "Routing", "Heure_Vol", "Date_Vol", "Numero_Vol", "Max_Colis"]],
        left_on=["Numero_Vol", "Date_Vol"],
        right_on=["Numero_Vol", "Date_Vol"],
        how="left",
        suffixes=("", "_VOL")
    )

    # ==========================================================
    # 6) MERGE ParamExpéditeur ↦ via expéditeur normalisé
    # ==========================================================
    df = df.merge(
        df_paramexp,
        how="left",
        left_on="EXP_UP",
        right_on="Expediteur_UP",
        suffixes=("", "_EXP")
    )

    # ==========================================================
    # 7) MERGE ParamBenev : ID prioritaire → fallback nom
    # ==========================================================

    # a) via ID
    df = df.merge(
        df_parambenev,
        how="left",
        left_on="ID_UP",
        right_on="ID_UP",
        suffixes=("", "_BEN_ID")
    )

    # b) fallback via nom si ID manquant
    mask_missing = df["ID"].astype(str).eq("")
    if mask_missing.any():
        df.loc[mask_missing, :] = df.loc[mask_missing].merge(
            df_parambenev,
            how="left",
            on="Benev_UP",
            suffixes=("", "_BEN"),
        )

    # ==========================================================
    # 8) Colonnes Excel à recréer
    # ==========================================================
    df["DATE LONGUE"] = df["Date_Vol"].apply(_date_longue)

    df["ITEM"] = df["Date_Vol"].apply(
        lambda d: pd.to_datetime(d).strftime("%A") if not pd.isna(d) else ""
    )

    df["NOM"] = df.apply(
        lambda r: (
            f"{str(r.get('Prenom_Court', '')).strip()[0]}. {str(r.get('Nom', '')).upper().strip()}"
            if r.get("Prenom_Court") and str(r.get("Prenom_Court")).strip() != ""
            else str(r.get("Nom", "")).upper().strip()
        ),
        axis=1,
    )
    # Fallback NOM si vide ou "nan" -> Benevole
    df["NOM"] = df["NOM"].fillna("").astype(str)
    mask_nom = df["NOM"].str.strip().eq("") | df["NOM"].str.contains("nan", case=False)
    if "Benevole" in df.columns:
        df.loc[mask_nom, "NOM"] = df.loc[mask_nom, "Benevole"]

    # ==========================================================
    # 9) Colonnes finales standardisées
    # ==========================================================

    df["IATA"] = df.get("Dest_IATA", "")
    df["ROUTING"] = df.get("Routing", "")

    df["NUMERO VOL"] = df.get("Numero_Vol", "")
    df["HEURE VOL"] = df.get("Heure_Vol", "")

    df["NUMERO BE"] = df.get("BE_Numero", "")
    df["NOMBRE COLIS"] = df.get("BE_Nb_Colis", "")
    df["TYPE"] = df.get("BE_Type", "")

    df["EXPEDITEUR"] = df.get("BE_Expediteur", "")
    df["DESTINATAIRE"] = df.get("BE_Destinataire", "")

    df["ID_BENEVOLE"] = df.get("ID", "")
    df["TELEPHONE"] = df.get("Telephone", df.get("telephone", ""))

    # ==========================================================
    # 10) Indicateur de merge partiel
    # ==========================================================
    df["_merge_fail"] = (
        df["BE_Expediteur"].eq("") |
        df["BE_Numero"].eq("") |
        df["Dest_IATA_UP"].eq("") |
        df["IATA"].eq("")
    ).astype(int)

    return df
