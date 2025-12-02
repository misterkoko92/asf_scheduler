# asf_app/ui/ui_stats/stats_plots.py
# -*- coding: utf-8 -*-

import streamlit as st
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import pandas as pd


sns.set_theme(style="whitegrid")


# ============================
# BARRES SEABORN
# ============================
def plot_bar(series: pd.Series, title: str):
    if series.empty:
        st.info("Aucune donnée.")
        return

    fig, ax = plt.subplots(figsize=(10, max(4, 0.4 * len(series))))
    sns.barplot(x=series.values, y=series.index, ax=ax)
    ax.set_title(title)
    st.pyplot(fig)


# ============================
# PIE PLOTLY
# ============================
def plot_pie(series: pd.Series, title: str):
    if series.empty:
        st.info("Aucune donnée.")
        return

    fig = px.pie(
        names=series.index,
        values=series.values,
        title=title,
        hole=0.4,
    )
    st.plotly_chart(fig, width="stretch")


# ============================
# TIME SERIES (Plotly)
# ============================
def plot_timeseries(series: pd.Series, title: str):
    if series.empty:
        st.info("Aucune donnée.")
        return

    fig = px.line(
        x=series.index,
        y=series.values,
        markers=True,
        title=title,
        labels={"x": "Semaine", "y": "Colis"},
    )
    st.plotly_chart(fig, width="stretch")


# ============================
# HEATMAP
# ============================
def plot_heatmap(pivot: pd.DataFrame, title: str):
    if pivot.empty:
        st.info("Aucune donnée.")
        return

    fig, ax = plt.subplots(figsize=(10, 6))
    sns.heatmap(pivot, annot=True, fmt=".0f", cmap="viridis", ax=ax)
    ax.set_title(title)
    st.pyplot(fig)
