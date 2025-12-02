# main.py
# -*- coding: utf-8 -*-

import pandas as pd

# Chemins configurés + copies temporaires
from scheduler.config_paths import print_config_paths, cleanup_tmp, prepare_paths

# Moteur
from scheduler.core_scheduler import Scheduler


# -------------------------------------------------------------------------
#  Résumés & Statistiques
# -------------------------------------------------------------------------

def build_resume_benevoles(planning_df: pd.DataFrame) -> pd.DataFrame:
    """Construit un tableau de synthèse des bénévoles."""
    if planning_df.empty:
        return pd.DataFrame(columns=[
            "Benevole", "Nb_Vols", "Colis_Réels", "Colis_Équiv_Total",
            "Colis_Équiv_Moyen", "Vols"
        ])

    df = planning_df.copy()
    df["Benevole"] = df["Benevole"].astype(str)

    resume = df.groupby("Benevole").agg(
        Nb_Vols=("Vol", "nunique"),
        Colis_Réels=("BE_Nb_Colis", "sum"),
        Colis_Équiv_Total=("BE_Nb_Equiv", "sum"),
        Vols=("Vol", lambda x: ", ".join(sorted(set(x)))),
    ).reset_index()

    resume["Colis_Équiv_Moyen"] = (
        resume["Colis_Équiv_Total"] / resume["Nb_Vols"]
    ).round(2)

    return resume[[
        "Benevole", "Nb_Vols", "Colis_Réels",
        "Colis_Équiv_Total", "Colis_Équiv_Moyen", "Vols"
    ]]


def build_stats_destinations(planning_df: pd.DataFrame) -> pd.DataFrame:
    """Statistiques par destination."""
    if planning_df.empty:
        return pd.DataFrame(columns=[
            "Destination", "Nb_BE", "Total_Colis", "Total_Equiv",
            "Nb_Jours", "Date_Min", "Date_Max"
        ])

    df = planning_df.copy()

    stats = df.groupby("Destination").agg(
        Nb_BE=("BE_Numero", "count"),
        Total_Colis=("BE_Nb_Colis", "sum"),
        Total_Equiv=("BE_Nb_Equiv", "sum"),
        Nb_Jours=("Date_Vol", lambda x: len(set(x))),
        Date_Min=("Date_Vol", "min"),
        Date_Max=("Date_Vol", "max"),
    ).reset_index()

    return stats


def build_stats_jours(planning_df: pd.DataFrame) -> pd.DataFrame:
    """Statistiques par jour."""
    if planning_df.empty:
        return pd.DataFrame(columns=[
            "Date_Vol", "Nb_Vols", "Nb_BE", "Colis_Réels", "Colis_Équiv"
        ])

    df = planning_df.copy()

    stats = df.groupby("Date_Vol").agg(
        Nb_Vols=("Vol", "nunique"),
        Nb_BE=("BE_Numero", "count"),
        Colis_Réels=("BE_Nb_Colis", "sum"),
        Colis_Équiv=("BE_Nb_Equiv", "sum"),
    ).reset_index()

    return stats


# -------------------------------------------------------------------------
# EXPORT XLSX FINAL
# -------------------------------------------------------------------------

def export_results(planning_df: pd.DataFrame, bilan_df: pd.DataFrame):
    """Génère Planning.xlsx + Bilan.xlsx avec plusieurs feuilles."""

    # ---------------------------
    # Planning.xlsx
    # ---------------------------
    planning_xlsx = "Planning.xlsx"
    planning_df.to_excel(planning_xlsx, index=False)

    # ---------------------------
    # Bilan.xlsx
    # ---------------------------
    bilan_xlsx = "Bilan.xlsx"

    with pd.ExcelWriter(bilan_xlsx, engine="xlsxwriter") as writer:

        # 1) Bilan principal
        bilan_df.to_excel(writer, sheet_name="Bilan", index=False)

        # 2) Résumé bénévoles
        df_res_benev = build_resume_benevoles(planning_df)
        df_res_benev.to_excel(writer, sheet_name="Résumé_Bénévoles", index=False)

        # 3) Stat destinations
        df_stats_dest = build_stats_destinations(planning_df)
        df_stats_dest.to_excel(writer, sheet_name="Stats_Destinations", index=False)

        # 4) Stat par jour
        df_stats_jours = build_stats_jours(planning_df)
        df_stats_jours.to_excel(writer, sheet_name="Stats_Jours", index=False)

    print("=== FICHIERS GÉNÉRÉS ===")
    print(f"📘 {planning_xlsx}")
    print(f"📘 {bilan_xlsx}")


# -------------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------------

def main():
    # Prépare les copies locales avant toute lecture
    prepare_paths(copy_sources=True)

    # Toujours afficher les chemins
    print_config_paths()

    print("=== LANCEMENT DU PLANNING ===")

    scheduler = Scheduler()

    try:
        # → Exécute le moteur
        planning_df, bilan_df = scheduler.run()

        # → Export
        export_results(planning_df, bilan_df)

    except Exception as e:
        print("\n❌ ERREUR FATALE :", e)
        raise

    finally:
        # → Supprime le dossier TMP même en cas d’erreur
        cleanup_tmp()
        print("🧹 TMP nettoyé")


if __name__ == "__main__":
    main()
