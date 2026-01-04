# -*- coding: utf-8 -*-
"""
audit_comm_planning.py — Audit complet du DF Communication
"""

import pandas as pd
from scheduler.planning_enrichment import enrich_planning
from asf_app.ui.ui_communication.clean_planning_df import build_df_comm

from scheduler.config_paths import (
    TABLEAU_DE_BORD,
    PLANNING_BENEVOLES,
    VOLS,
    SHEET_PARAM_DEST,
    SHEET_PARAM_EXP,
    SHEET_PARAM_BE,
    SHEET_PARAM_BENEV,
)

from loaders.load_shipments import load_shipments_df
from loaders.load_vols import load_vols, get_vols_df_cached
from loaders.load_benevoles import get_benevoles_cached
from loaders.universal_loader import load_and_normalize

from scheduler.column_map import (
    column_map_param_dest,
    column_map_param_expediteur,
    column_map_param_be,
    column_map_param_benev,
)


def load_parameters():
    df_paramdest = load_and_normalize(
        TABLEAU_DE_BORD, SHEET_PARAM_DEST, column_map_param_dest
    )
    df_paramexp = load_and_normalize(
        TABLEAU_DE_BORD, SHEET_PARAM_EXP, column_map_param_expediteur
    )
    df_parambe = load_and_normalize(
        TABLEAU_DE_BORD, SHEET_PARAM_BE, column_map_param_be
    )
    df_parambenev = load_and_normalize(
        PLANNING_BENEVOLES, SHEET_PARAM_BENEV, column_map_param_benev
    )
    return df_paramdest, df_paramexp, df_parambe, df_parambenev


def audit():
    print("\n==============================================")
    print("🔍 AUDIT COMMUNICATION — Vérification complète")
    print("==============================================\n")

    # ----------------------
    # Chargement paramètres
    # ----------------------
    print("📒 Chargement paramètres…")
    df_paramdest, df_paramexp, df_parambe, df_parambenev = load_parameters()

    # ----------------------
    # Chargement BE
    # ----------------------
    print("📘 Chargement BE (MAG CENTRAL)…")
    df_be = load_shipments_df(param_be_raw=df_parambe, planifiables_only=True)
    print(f"✔ BE charges : {len(df_be)} lignes")

    # ----------------------
    # Chargement vols / bénévoles
    # ----------------------
    print("📗 Chargement vols…")
    df_vols = get_vols_df_cached()
    print(f"✔ Vols chargés : {len(df_vols)} lignes\n")


    print("📙 Chargement disponibilités bénévoles…")
    df_dispos = get_benevoles_cached()

    # ----------------------
    # Construction d’un planning "raw"
    # ----------------------
    print("\n📊 Construction planning brut…")

    df_planning_raw = df_be.copy()

    # On ajoute une date si absente, juste pour audit
    if "Date_Vol" in df_vols.columns:
        df_planning_raw["Date_Vol"] = df_vols["Date_Vol"].iloc[0]

    print(f"✔ Planning brut : {len(df_planning_raw)} lignes\n")

    # ----------------------
    # Enrichissement complet
    # ----------------------
    print("🔧 enrich_planning(df_planning_raw)")
    df_final = enrich_planning(df_planning_raw)

    print("\n📌 Colonnes df_final :")
    print(list(df_final.columns))

    print("\n📌 Aperçu df_final :")
    print(df_final.head(20))

    # ----------------------
    # DF Communication
    # ----------------------
    print("\n🔧 build_df_comm(df_final)")
    df_comm = build_df_comm(df_final, df_paramdest, df_parambenev)

    print("\n📌 Colonnes df_comm :")
    print(list(df_comm.columns))

    print("\n📌 Aperçu df_comm :")
    print(df_comm.head(20))

    # ----------------------
    # Colonnes WhatsApp
    # ----------------------
    required = ["BENEVOLE", "Benevole_Tel", "Date_Affichage_WA",
                "Destination", "Numero_BE_Aff", "Nb_Colis"]

    print("\n==============================================")
    print("📲 Audit WhatsApp")
    print("==============================================")

    missing = [c for c in required if c not in df_comm.columns]
    if missing:
        print("❌ Colonnes manquantes pour WA:", missing)
    else:
        print("✔ Toutes les colonnes WA sont présentes")

    df_ok = df_comm[
        (df_comm["BENEVOLE"].astype(str) != "") &
        (df_comm["Benevole_Tel"].astype(str) != "") &
        (df_comm["Numero_BE_Aff"].astype(str) != "")
    ]

    print(f"\n📌 Lignes WhatsApp exploitables : {len(df_ok)}")
    if df_ok.empty:
        print("❌ Aucun message WA possible → problème amont")
    else:
        print("✔ OK : messages WA compatibles.")


if __name__ == "__main__":
    audit()
