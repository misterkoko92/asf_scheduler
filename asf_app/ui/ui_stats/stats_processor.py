# asf_app/ui/ui_stats/stats_processor.py
# -*- coding: utf-8 -*-

import pandas as pd
import numpy as np


# ===============================================================
# KPIs avancés
# ===============================================================
def compute_kpis(df: pd.DataFrame):

    def safe_sum(col):
        return int(df[col].fillna(0).astype(int).sum()) if col in df else 0

    return {
        "total_be": len(df),
        "total_colis": safe_sum("nb_colis"),
        "nb_dest": df["destination_iata"].nunique(),
        "nb_expediteurs": df["expediteur"].nunique(),
        "nb_vols": df["vol_info"].nunique(),
        "colis_par_be": safe_sum("nb_colis") / max(1, len(df)),
    }


# ===============================================================
# CHARGE PAR JOUR
# ===============================================================
def daily_load(df):
    df2 = df.copy()
    df2["date"] = pd.to_datetime(df2["date"], errors="coerce")
    return df2.groupby(df2["date"].dt.date)["nb_colis"].sum()


# ===============================================================
# CHARGE PAR VOL
# ===============================================================
def load_per_flight(df):
    return df.groupby(["destination_iata", "vol_info"])["nb_colis"].sum()


# ===============================================================
# DÉLAI TRANSFERT → VOL (si présent)
# ===============================================================
def compute_transfer_delay(df):
    if "date" not in df or "heure" not in df:
        return pd.Series(dtype=float)

    try:
        dt_vol = pd.to_datetime(df["date"] + " " + df["heure"], errors="coerce")
        dt_trans = pd.to_datetime(df.get("date_transfert", None), errors="coerce")
        return (dt_vol - dt_trans).dt.total_seconds() / 3600  # heures
    except Exception:
        return pd.Series(dtype=float)


# ===============================================================
# GROUP BY classiques
# ===============================================================
def group_by_destination(df):
    return df.groupby("destination_iata")["nb_colis"].sum().sort_values(ascending=False)


def group_by_expediteur(df):
    return df.groupby("expediteur")["nb_colis"].sum().sort_values(ascending=False)


def group_by_benevole(df):
    return df.groupby("nom")["be"].count().sort_values(ascending=False)


def group_by_week(df):
    return df.groupby("week")["nb_colis"].sum()


# ===============================================================
# HEATMAP DEST × WEEK
# ===============================================================
def pivot_dest_week(df):
    return df.pivot_table(
        index="destination_iata",
        columns="week",
        values="nb_colis",
        aggfunc="sum",
        fill_value=0,
    )


# ===============================================================
# HEATMAP DAY × DEST
# ===============================================================
def pivot_day_dest(df):
    df2 = df.copy()
    df2["date"] = pd.to_datetime(df2["date"], errors="coerce")
    df2["day"] = df2["date"].dt.strftime("%a")
    return df2.pivot_table(
        index="day",
        columns="destination_iata",
        values="nb_colis",
        aggfunc="sum",
        fill_value=0,
    )
