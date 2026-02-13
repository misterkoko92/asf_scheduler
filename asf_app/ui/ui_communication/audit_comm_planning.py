# -*- coding: utf-8 -*-
"""
audit_comm_planning.py — Audit complet du DF Communication
"""



from asf_app.services.params_loader import load_parameters
from asf_app.ui.ui_communication.clean_planning_df import build_df_comm
from loaders.load_benevoles import get_benevoles_cached
from loaders.load_shipments import load_shipments_df
from loaders.load_vols import get_vols_df_cached
from scheduler.data_sources import ExcelSourcePaths
from scheduler.planning_enrichment import enrich_planning
from utils.logging_utils import get_logger

logger = get_logger("audit_comm_planning", console=True)


def audit(paths: ExcelSourcePaths | None = None):
    logger.info("\n==============================================")
    logger.info("🔍 AUDIT COMMUNICATION — Vérification complète")
    logger.info("==============================================\n")

    tdb_path = paths.tableau_de_bord if paths else None
    benev_path = paths.planning_benevoles if paths else None
    vols_path = paths.vols if paths else None

    # ----------------------
    # Chargement paramètres
    # ----------------------
    logger.info("📒 Chargement paramètres…")
    df_paramdest, df_paramexp, df_parambe, df_parambenev = load_parameters(
        tdb_path=tdb_path,
        benev_path=benev_path,
    )

    # ----------------------
    # Chargement BE
    # ----------------------
    logger.info("📘 Chargement BE (MAG CENTRAL)…")
    df_be = load_shipments_df(
        param_be_raw=df_parambe,
        planifiables_only=True,
        tdb_path=tdb_path,
    )
    logger.info("✔ BE charges : %s lignes", len(df_be))

    # ----------------------
    # Chargement vols / bénévoles
    # ----------------------
    logger.info("📗 Chargement vols…")
    df_vols = get_vols_df_cached(vols_path=vols_path, tdb_path=tdb_path)
    logger.info("✔ Vols chargés : %s lignes\n", len(df_vols))


    logger.info("📙 Chargement disponibilités bénévoles…")
    get_benevoles_cached(planning_path=benev_path)

    # ----------------------
    # Construction d’un planning "raw"
    # ----------------------
    logger.info("\n📊 Construction planning brut…")

    df_planning_raw = df_be.copy()

    # On ajoute une date si absente, juste pour audit
    if "Date_Vol" in df_vols.columns:
        df_planning_raw["Date_Vol"] = df_vols["Date_Vol"].iloc[0]

    logger.info("✔ Planning brut : %s lignes\n", len(df_planning_raw))

    # ----------------------
    # Enrichissement complet
    # ----------------------
    logger.info("🔧 enrich_planning(df_planning_raw)")
    df_final = enrich_planning(df_planning_raw)

    logger.info("\n📌 Colonnes df_final :")
    logger.info("%s", list(df_final.columns))

    logger.info("\n📌 Aperçu df_final :")
    logger.info("%s", df_final.head(20))

    # ----------------------
    # DF Communication
    # ----------------------
    logger.info("\n🔧 build_df_comm(df_final)")
    df_comm = build_df_comm(df_final, df_paramdest, df_parambenev)

    logger.info("\n📌 Colonnes df_comm :")
    logger.info("%s", list(df_comm.columns))

    logger.info("\n📌 Aperçu df_comm :")
    logger.info("%s", df_comm.head(20))

    # ----------------------
    # Colonnes WhatsApp
    # ----------------------
    required = ["BENEVOLE", "Benevole_Tel", "Date_Affichage_WA",
                "Destination", "Numero_BE_Aff", "Nb_Colis"]

    logger.info("\n==============================================")
    logger.info("📲 Audit WhatsApp")
    logger.info("==============================================")

    missing = [c for c in required if c not in df_comm.columns]
    if missing:
        logger.error("❌ Colonnes manquantes pour WA: %s", missing)
    else:
        logger.info("✔ Toutes les colonnes WA sont présentes")

    df_ok = df_comm[
        (df_comm["BENEVOLE"].astype(str) != "") &
        (df_comm["Benevole_Tel"].astype(str) != "") &
        (df_comm["Numero_BE_Aff"].astype(str) != "")
    ]

    logger.info("\n📌 Lignes WhatsApp exploitables : %s", len(df_ok))
    if df_ok.empty:
        logger.error("❌ Aucun message WA possible → problème amont")
    else:
        logger.info("✔ OK : messages WA compatibles.")


if __name__ == "__main__":
    audit()
