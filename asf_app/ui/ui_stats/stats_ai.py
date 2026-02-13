# asf_app/ui/ui_stats/stats_ai.py
# -*- coding: utf-8 -*-

import pandas as pd


def auto_insights(df):
    insights = []

    # Top destination
    top_dest = df["destination_iata"].value_counts().idxmax()
    insights.append(f"🏆 Destination la plus servie : **{top_dest}**")

    # Top expéditeur
    top_exp = df["expediteur"].value_counts().idxmax()
    insights.append(f"📦 Expéditeur le plus actif : **{top_exp}**")

    # Charge max
    vol_max = df.groupby("vol_info")["nb_colis"].sum().idxmax()
    insights.append(f"✈️ Vol le plus chargé : **{vol_max}**")

    # Semaine plus grosse
    w = df.groupby("week")["nb_colis"].sum().idxmax()
    insights.append(f"📈 Semaine la plus forte : **S{w}**")

    return insights


def predict_volume(df, n_future=4):
    """
    Modèle simple de tendance / moyenne mobile.
    Retourne une série future sur 4 semaines.
    """
    s = df.groupby("week")["nb_colis"].sum().sort_index()

    if len(s) < 3:
        return pd.Series(dtype=float)

    trend = s.rolling(3).mean().iloc[-1]

    fut = pd.Series(
        [trend * (1 + 0.02 * i) for i in range(1, n_future + 1)],
        index=[f"Semaine+{i}" for i in range(1, n_future + 1)],
    )
    return fut
