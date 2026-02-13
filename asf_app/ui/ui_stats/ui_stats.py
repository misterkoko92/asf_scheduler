# asf_app/ui/ui_stats/ui_stats.py
# -*- coding: utf-8 -*-

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from asf_app.config.runtime import get_onedrive_root, get_output_planning_dir
from asf_app.services.planning_exports_service import load_planning_xlsx as _load_planning_xlsx
from utils.datetime_utils import coerce_datetime

# ==========================================================================
#  EXTRACTION SEMAINE + VERSION POUR LES FICHIERS ASFmm
# ==========================================================================

WK = re.compile(r"(\d{1,2})(?:-(\d+))?")
WK_LABEL = re.compile(r"N[°o]?\s*([0-9]{1,2})\s*[- ]\s*([0-9]{2,4})?", re.IGNORECASE)


def extract_week_version(name: str):
    """
    Extrait (num_semaine, version) à partir d'un nom de fichier du type :
    - ASFmm - PLANNING SEMAINE 2026-47-02.xlsx
    - ASFmm - PLANNING SEMAINE N° 03-2025-MacBook Air (2).xlsx
    etc.
    """
    # 1) Nouveau format : "SEMAINE YYYY-XX-ZZ"
    m = re.search(r"SEMAINE\s*(20\d{2})\D+(\d{1,2})\D+(\d+)", name, re.IGNORECASE)
    if m:
        try:
            wk = int(m.group(2))
            ver = int(m.group(3))
            if 1 <= wk <= 53:
                return wk, ver
        except (TypeError, ValueError, OverflowError):
            pass

    # 2) Ancien format avec version explicite vXX
    m = re.search(r"N[°o]?\s*(\d{1,2}).*?v(\d+)", name, re.IGNORECASE)
    if m:
        try:
            wk = int(m.group(1))
            ver = int(m.group(2))
            if 1 <= wk <= 53:
                return wk, ver
        except (TypeError, ValueError, OverflowError):
            pass

    # 3) Ancien format sans version : version par défaut = 1
    m = re.search(r"N[°o]?\s*(\d{1,2})", name, re.IGNORECASE)
    if m:
        try:
            wk = int(m.group(1))
            if 1 <= wk <= 53:
                return wk, 1
        except (TypeError, ValueError, OverflowError):
            pass

    # 4) Fallback : premier couple de chiffres
    m = WK.search(name)
    if m:
        wk = int(m.group(1))
        ver = int(m.group(2) or 0)
        if 1 <= wk <= 53:
            return wk, ver

    return None, None


def filter_latest(files):
    """
    Parmi une liste de fichiers, ne garder que la dernière version pour
    chaque numéro de semaine (basé sur le suffixe -<version> si présent).
    """
    latest = {}
    for f in files:
        w, v = extract_week_version(f.name)
        if w is None:
            continue
        if w not in latest or v > latest[w][0]:
            latest[w] = (v, f)
    return [x[1] for x in latest.values()]


def _normalize_nom_last(name: str) -> str:
    """
    Ne garde que le NOM (dernier mot, en majuscules) pour fusionner les doublons
    type 'C. BACARA' / 'Claude BACARA'.
    """
    s = str(name or "").strip().upper()
    if not s:
        return ""
    parts = [p for p in re.sub(r"[\\.]", " ", s).split() if p]
    if not parts:
        return ""
    return parts[-1]


# ==========================================================================
#  FILTRES DE PÉRIODE
# ==========================================================================

_PERIOD_OPTIONS = ["Hebdomadaire", "Mensuel", "Trimestriel", "Semestriel", "Annuel"]
_JOURS_FR = {0: "Lundi", 1: "Mardi", 2: "Mercredi", 3: "Jeudi", 4: "Vendredi", 5: "Samedi", 6: "Dimanche"}


def _filter_period(df: pd.DataFrame, period: str, ref_date=None) -> pd.DataFrame:
    """
    Filtre un DataFrame sur la période souhaitée en se basant sur df['date_dt'].
    Périodes :
      - Hebdomadaire : même semaine ISO que ref_date
      - Mensuel      : même mois/année
      - Trimestriel  : même trimestre/année
      - Semestriel   : H1 (mois 1-6) ou H2 (7-12) de l'année
      - Annuel       : même année
    """
    if df is None or df.empty or "date_dt" not in df.columns:
        return df

    if ref_date is None:
        ref_date = df["date_dt"].max()
    ref = coerce_datetime(ref_date, errors="coerce")
    if pd.isna(ref):
        return df

    d = df.copy()
    d["_year"] = d["date_dt"].dt.year
    d["_week"] = d["date_dt"].dt.isocalendar().week
    d["_month"] = d["date_dt"].dt.month
    d["_quarter"] = ((d["_month"] - 1) // 3) + 1
    d["_semester"] = d["_month"].apply(lambda m: 1 if m <= 6 else 2)

    if period == "Hebdomadaire":
        mask = (d["_year"] == ref.year) & (d["_week"] == ref.isocalendar().week)
    elif period == "Mensuel":
        mask = (d["_year"] == ref.year) & (d["_month"] == ref.month)
    elif period == "Trimestriel":
        ref_q = ((ref.month - 1) // 3) + 1
        mask = (d["_year"] == ref.year) & (d["_quarter"] == ref_q)
    elif period == "Semestriel":
        ref_s = 1 if ref.month <= 6 else 2
        mask = (d["_year"] == ref.year) & (d["_semester"] == ref_s)
    elif period == "Annuel":
        mask = d["_year"] == ref.year
    else:
        return df

    return d[mask].drop(columns=["_year", "_week", "_month", "_quarter", "_semester"])


def _select_period(df: pd.DataFrame, label: str, general_period: str) -> pd.DataFrame:
    """
    Affiche un sélecteur de période pour un bloc. L'option par défaut est la période générale.
    """
    options = [f"Période générale ({general_period})"] + _PERIOD_OPTIONS
    choice = st.selectbox(f"Période ({label})", options, key=f"{label}_period")
    if choice.startswith("Période générale"):
        return df
    return _filter_period(df, choice, ref_date=df["date_dt"].max())


# ==========================================================================
#  LOADER ROBUSTE DU PLANNING ASFmm 2025 (INDEX-BASED)
# ==========================================================================


def load_planning_xlsx(path: Path, default_year: int | None = None) -> pd.DataFrame:
    return _load_planning_xlsx(path, default_year=default_year)


# ==========================================================================
#  CHARGEMENT MULTI-FICHIERS & PRÉ-PROCESS
# ==========================================================================


def _extract_year_from_name(name: str) -> int | None:
    # chercher une année 4 chiffres dans le nom de fichier
    m = re.search(r"(20\d{2})", name)
    if m:
        return int(m.group(1))
    return None


def _load_all_plannings(base_override: Path | None = None) -> pd.DataFrame:
    """
    Charge tous les plannings ASFmm dans le dossier ASFmm (ou OUTPUT_PLANNING_DIR en fallback).
    Ajoute colonnes: week, year, date_dt, mois, jour_semaine.
    """
    # Re-détection OneDrive à la volée pour supporter overrides (ENV/Session)
    get_planning_dirs = None
    try:
        from scheduler.config_paths import detect_onedrive_asf
        from scheduler.config_paths import get_planning_dirs as _get_planning_dirs
        base_root = detect_onedrive_asf()
        get_planning_dirs = _get_planning_dirs
    except (ImportError, OSError, RuntimeError, TypeError, ValueError):
        base_root = get_onedrive_root()
    try:
        roots = get_planning_dirs() if callable(get_planning_dirs) else []
    except (OSError, RuntimeError, TypeError, ValueError):
        roots = []
    if base_override:
        roots.insert(0, base_override)
    if not roots:
        roots = [base_root / "Planning MAB" / "ASFmm PLANNING 2025", base_root / "Planning MAB", get_output_planning_dir()]
    seen = []
    all_files: list[Path] = []
    for r in roots:
        if not r or not r.exists():
            continue
        try:
            for f in r.glob("**/*.xls*"):
                if not f.is_file():
                    continue
                # on ne garde que les fichiers dont on peut extraire une semaine
                wk, _ = extract_week_version(f.name)
                if wk is None:
                    continue
                if f not in seen:
                    seen.append(f)
                    all_files.append(f)
        except OSError:
            continue

    all_files = sorted(
        all_files,
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )

    if not all_files:
        return pd.DataFrame()

    files = filter_latest(all_files)

    dfs = []
    for f in files:
        wk, _ = extract_week_version(f.name)
        year_guess = _extract_year_from_name(f.name) or f.stat().st_mtime
        try:
            if isinstance(year_guess, float):
                year_guess = datetime.fromtimestamp(year_guess).year
        except (OSError, OverflowError, TypeError, ValueError):
            year_guess = None

        df = load_planning_xlsx(f, default_year=year_guess)
        if df.empty:
            continue
        df = df.copy()
        df["week"] = wk
        df["source_file"] = f.name

        df["date_dt"] = coerce_datetime(df["date"], errors="coerce")
        df["year"] = df["date_dt"].dt.year
        df["month"] = df["date_dt"].dt.month
        df["jour_semaine"] = df["date_dt"].dt.dayofweek  # 0=lundi
        dfs.append(df)

    if not dfs:
        return pd.DataFrame()

    out = pd.concat(dfs, ignore_index=True)
    out = out[out["date_dt"].notna()].copy()

    # Normalisation des bénévoles : on ne garde que le NOM pour fusionner les variantes
    out["nom"] = out["nom"].apply(_normalize_nom_last)

    # Identifiant de vol unique par date (pour compter AF723 le 10/11 et le 11/11 comme 2 vols)
    out["vol_day"] = out["vol_info"].astype(str) + "|" + out["date_dt"].dt.date.astype(str)

    return out


def _kpi_global(df: pd.DataFrame) -> dict:
    if df.empty:
        return {
            "nb_be": 0,
            "nb_colis": 0,
            "nb_semaines": 0,
            "nb_dest": 0,
            "nb_expediteurs": 0,
            "nb_benevoles": 0,
        }

    return {
        "nb_be": int(df["be"].nunique()),
        "nb_colis": int(df["nb_colis"].sum()),
        "nb_semaines": int(df["week"].nunique()),
        "nb_dest": int(df["destination_iata"].nunique()),
        "nb_expediteurs": int(df["expediteur"].nunique()),
        "nb_benevoles": int(df["nom"].nunique()),
    }


# ==========================================================================
#  GRAPHIQUES PLOTLY
# ==========================================================================


def plot_weekly_volume(df: pd.DataFrame, general_period: str):
    if df.empty:
        st.info("Aucune donnée pour le volume hebdomadaire.")
        return

    df_local = _select_period(df, "Volume hebdomadaire", general_period)

    agg = (
        df_local.groupby("week", as_index=False)
        .agg(
            nb_colis=("nb_colis", "sum"),
            nb_be=("be", "nunique"),
            nb_dest=("destination_iata", "nunique"),
            nb_vol=("vol_day", "nunique"),
            nb_exped=("expediteur", "nunique"),
            nb_bene=("nom", "nunique"),
            nb_jour=("date_dt", "nunique"),
        )
        .sort_values("week")
    )

    tab = st.radio(
        "Afficher par :",
        ["Nb colis", "Nb BE", "Nb Destination", "Nb Numéro de Vol", "Nb expéditeur", "Nb Benevole", "Nb Jour"],
        horizontal=True,
        key="stats_week_metric_choice",
    )

    col_map = {
        "Nb colis": ("nb_colis", "Nombre de colis"),
        "Nb BE": ("nb_be", "Nombre de BE"),
        "Nb Destination": ("nb_dest", "Nombre de destinations"),
        "Nb Numéro de Vol": ("nb_vol", "Nombre de vols"),
        "Nb expéditeur": ("nb_exped", "Nombre d'expéditeurs"),
        "Nb Benevole": ("nb_bene", "Nombre de bénévoles"),
        "Nb Jour": ("nb_jour", "Nombre de jours (distincts)"),
    }

    y_col, y_label = col_map.get(tab, ("nb_colis", "Nombre de colis"))

    fig = px.bar(
        agg,
        x="week",
        y=y_col,
        labels={"week": "Semaine", y_col: y_label},
        title=f"{tab} par semaine",
    )

    fig.update_layout(margin=dict(l=20, r=20, t=40, b=40))
    st.plotly_chart(fig, width="stretch")


def plot_top_destinations(df: pd.DataFrame, general_period: str):
    if df.empty:
        st.info("Aucune donnée pour les destinations.")
        return

    df_local = _select_period(df, "Destinations", general_period)

    agg = (
        df_local.groupby(["destination_iata", "destination_nom"], as_index=False)
        .agg(
            nb_colis=("nb_colis", "sum"),
            nb_be=("be", "nunique"),
            nb_vol=("vol_day", "nunique"),
            nb_exped=("expediteur", "nunique"),
            nb_bene=("nom", "nunique"),
        )
    )

    metric = st.radio(
        "Classer les destinations par :",
        ["Nb colis", "Nb BE", "Nb Vols", "Nb Expéditeur", "Nb Benevole"],
        horizontal=True,
        key="stats_dest_metric_choice",
    )

    top_n = st.slider("Nombre de destinations à afficher :", 5, 30, 10, key="stats_dest_topn")

    metric_map = {
        "Nb colis": ("nb_colis", "Nombre de colis"),
        "Nb BE": ("nb_be", "Nombre de BE"),
        "Nb Vols": ("nb_vol", "Nombre de vols"),
        "Nb Expéditeur": ("nb_exped", "Nombre d'expéditeurs"),
        "Nb Benevole": ("nb_bene", "Nombre de bénévoles"),
    }

    y_col, y_label = metric_map.get(metric, ("nb_colis", "Nombre de colis"))
    agg = agg.sort_values(y_col, ascending=False).head(top_n)
    title = f"Top {top_n} destinations (par {metric})"

    agg["dest_label"] = agg["destination_iata"] + " — " + agg["destination_nom"]

    fig = px.bar(
        agg,
        x="dest_label",
        y=y_col,
        labels={"dest_label": "Destination", y_col: y_label},
        title=title,
    )
    fig.update_layout(xaxis_tickangle=-45, margin=dict(l=20, r=20, t=40, b=80))
    st.plotly_chart(fig, width="stretch")


def plot_heatmap_week_destination(df: pd.DataFrame, general_period: str):
    if df.empty:
        st.info("Aucune donnée pour la heatmap.")
        return

    df_local = _select_period(df, "Heatmap", general_period)

    agg = (
        df_local.groupby(["week", "destination_iata"], as_index=False)
        .agg(nb_colis=("nb_colis", "sum"))
    )

    pivot = agg.pivot(index="destination_iata", columns="week", values="nb_colis").fillna(0)

    if pivot.empty:
        st.info("Pas assez de données pour la heatmap.")
        return

    fig = px.imshow(
        pivot.values,
        x=pivot.columns,
        y=pivot.index,
        aspect="auto",
        labels=dict(x="Semaine", y="Destination (IATA)", color="Colis"),
        title="Heatmap — Colis par semaine et destination",
    )
    st.plotly_chart(fig, width="stretch")


def plot_hour_day_heatmap(df: pd.DataFrame, general_period: str):
    if df.empty:
        st.info("Aucune donnée horaire.")
        return

    df_local = _select_period(df, "Heures/Jours", general_period)
    if df_local.empty:
        st.info("Aucune donnée sur la période.")
        return

    def _parse_hour(val):
        try:
            t = coerce_datetime(str(val), errors="coerce").time()
            return t.hour if t else np.nan
        except (AttributeError, TypeError, ValueError):
            return np.nan

    df_local = df_local.copy()
    df_local["hour"] = df_local["heure"].apply(_parse_hour)
    df_local = df_local.dropna(subset=["hour"])
    if df_local.empty:
        st.info("Heures non exploitables.")
        return

    df_local["dow"] = df_local["date_dt"].dt.dayofweek
    pivot = (
        df_local.groupby(["dow", "hour"], as_index=False)
        .agg(nb_colis=("nb_colis", "sum"))
        .pivot(index="dow", columns="hour", values="nb_colis")
        .fillna(0)
    )
    pivot.index = pivot.index.map(lambda d: _JOURS_FR.get(d, str(d)))

    fig = px.imshow(
        pivot.values,
        x=pivot.columns,
        y=pivot.index,
        labels=dict(x="Heure", y="Jour", color="Colis"),
        title="Répartition colis par jour & heure",
        aspect="auto",
    )
    st.plotly_chart(fig, width="stretch")


def plot_benevole_load(df: pd.DataFrame, general_period: str):
    if df.empty:
        st.info("Aucune donnée pour les bénévoles.")
        return

    df_local = _select_period(df, "Bénévoles", general_period)

    agg = (
        df_local.groupby("nom", as_index=False)
        .agg(
            nb_colis=("nb_colis", "sum"),
            nb_be=("be", "nunique"),
            nb_semaines=("week", "nunique"),
            nb_dest=("destination_iata", "nunique"),
            nb_jour=("date_dt", lambda s: s.dt.date.nunique()),  # jours avec au moins un vol
            nb_vol=("vol_day", "nunique"),  # vol+date distincts
            nb_num_vol=("vol_info", "nunique"),  # numéros de vol distincts
        )
    )

    metric = st.radio(
        "Afficher la charge par :",
        ["Nb Colis", "Nb Destination", "Nb Jour", "Nb Vol", "Nb Numéro de vol"],
        horizontal=True,
        key="stats_benev_metric_choice",
    )

    metric_map = {
        "Nb Colis": ("nb_colis", "Nombre de colis"),
        "Nb Destination": ("nb_dest", "Nombre de destinations"),
        "Nb Jour": ("nb_jour", "Nombre de jours"),
        "Nb Vol": ("nb_vol", "Nombre de vols"),
        "Nb Numéro de vol": ("nb_num_vol", "Nombre de numéros de vol"),
    }
    y_col, y_label = metric_map.get(metric, ("nb_colis", "Nombre de colis"))

    top_n = st.slider("Top bénévoles :", 5, 50, 15, key="stats_benev_topn")
    agg = agg.sort_values(y_col, ascending=False).head(top_n)

    fig = px.bar(
        agg,
        x="nom",
        y=y_col,
        labels={"nom": "Bénévole", y_col: y_label},
        title=f"Top {top_n} bénévoles ({metric})",
    )
    fig.update_layout(xaxis_tickangle=-45, margin=dict(l=20, r=20, t=40, b=100))
    st.plotly_chart(fig, width="stretch")

    with st.expander("Détails bénévoles (tableau)", expanded=False):
        st.dataframe(
            agg[
                [
                    "nom",
                    "nb_colis",
                    "nb_dest",
                    "nb_jour",
                    "nb_vol",
                    "nb_num_vol",
                    "nb_be",
                    "nb_semaines",
                ]
            ],
            width="stretch",
        )


def plot_expediteur_volume(df: pd.DataFrame, general_period: str):
    if df.empty:
        st.info("Aucune donnée pour les expéditeurs.")
        return

    df_local = _select_period(df, "Expéditeurs", general_period)

    # Nettoyage : exclure valeurs qui sont en réalité des types (CN, MM, etc.)
    type_like = {
        "CN", "MM", "FR", "FRE", "MED", "AUTRE", "MOB",
        "JOUETS", "JOUET", "BEQUILLE", "BEQUILLES", "POTENCE",
        "LAIT", "CN/LAIT", "LAIT/MM", "DEAMBULATEUR", "DEAMBULATEURS",
    }
    tmp = df_local.copy()
    tmp["expediteur_up"] = tmp["expediteur"].astype(str).str.strip().str.upper()
    tmp = tmp[~tmp["expediteur_up"].isin(type_like)]

    exclude_asf = st.checkbox("Hors ASF", value=False, key="stats_exped_exclude_asf")
    if exclude_asf:
        tmp = tmp[tmp["expediteur_up"] != "ASF"]

    if tmp.empty:
        st.info("Aucun expéditeur après filtrage.")
        return

    agg = (
        tmp.groupby("expediteur", as_index=False)
        .agg(
            nb_colis=("nb_colis", "sum"),
            nb_be=("be", "nunique"),
            nb_vol=("vol_day", "nunique"),
        )
    )

    metric = st.radio(
        "Classer les expéditeurs par :",
        ["Nb Colis", "Nb BE", "Nb Vol"],
        horizontal=True,
        key="stats_exped_metric_choice",
    )

    metric_map = {
        "Nb Colis": ("nb_colis", "Nombre de colis"),
        "Nb BE": ("nb_be", "Nombre de BE"),
        "Nb Vol": ("nb_vol", "Nombre de vols"),
    }
    y_col, y_label = metric_map.get(metric, ("nb_colis", "Nombre de colis"))

    agg = agg.sort_values(y_col, ascending=False)

    top_n = st.slider("Top expéditeurs :", 5, 40, 10, key="stats_exped_topn")
    agg = agg.head(top_n)

    fig = px.bar(
        agg,
        x="expediteur",
        y=y_col,
        labels={"expediteur": "Expéditeur", y_col: y_label},
        title=f"Top {top_n} expéditeurs ({metric})",
    )
    fig.update_layout(xaxis_tickangle=-45, margin=dict(l=20, r=20, t=40, b=120))
    st.plotly_chart(fig, width="stretch")


def plot_type_colis(df: pd.DataFrame, general_period: str):
    if df.empty:
        st.info("Aucune donnée pour les types de colis.")
        return

    df_local = _select_period(df, "Types de colis", general_period)

    agg_type = (
        df_local.groupby("type", as_index=False)
        .agg(
            nb_colis=("nb_colis", "sum"),
            nb_vol=("vol_day", "nunique"),
        )
        .sort_values("nb_colis", ascending=False)
    )

    metric = st.radio(
        "Afficher par :",
        ["Nb colis", "Nb Vol", "Répartition par destination"],
        horizontal=True,
        key="stats_type_metric_choice",
    )

    if metric == "Répartition par destination":
        agg_dest = (
            df_local.groupby(["type", "destination_iata"], as_index=False)
            .agg(nb_colis=("nb_colis", "sum"))
        )
        if agg_dest.empty:
            st.info("Aucune donnée de répartition.")
            return
        fig = px.bar(
            agg_dest,
            x="destination_iata",
            y="nb_colis",
            color="type",
            labels={"destination_iata": "Destination", "nb_colis": "Colis", "type": "Type"},
            title="Répartition des colis par destination et type",
        )
        fig.update_layout(margin=dict(l=20, r=20, t=40, b=80))
        st.plotly_chart(fig, width="stretch")
    else:
        y_col = "nb_colis" if metric == "Nb colis" else "nb_vol"
        y_label = "Nombre de colis" if metric == "Nb colis" else "Nombre de vols"
        fig = px.bar(
            agg_type.head(30),
            x="type",
            y=y_col,
            labels={"type": "Type de colis", y_col: y_label},
            title=f"Types de colis — {metric}",
        )
        fig.update_layout(xaxis_tickangle=-30, margin=dict(l=20, r=20, t=40, b=80))
        st.plotly_chart(fig, width="stretch")


def plot_exp_dest_matrix(df: pd.DataFrame, general_period: str):
    if df.empty:
        st.info("Aucune donnée expéditeur × destination.")
        return

    df_local = _select_period(df, "Matrice expéditeur/destination", general_period)
    if df_local.empty:
        st.info("Aucune donnée sur la période.")
        return

    pivot = (
        df_local.groupby(["expediteur", "destination_iata"], as_index=False)
        .agg(nb_colis=("nb_colis", "sum"))
        .pivot(index="expediteur", columns="destination_iata", values="nb_colis")
        .fillna(0)
    )

    if pivot.empty:
        st.info("Matrice vide.")
        return

    fig = px.imshow(
        pivot.values,
        x=pivot.columns,
        y=pivot.index,
        labels=dict(x="Destination", y="Expéditeur", color="Colis"),
        title="Expéditeur × Destination (colis)",
        aspect="auto",
    )
    st.plotly_chart(fig, width="stretch")


def plot_quality_report(df: pd.DataFrame, general_period: str):
    if df.empty:
        st.info("Aucune donnée pour le contrôle qualité.")
        return

    df_local = _select_period(df, "Qualité", general_period)
    if df_local.empty:
        st.info("Aucune donnée sur la période.")
        return

    issues = []
    for col in ["destination_iata", "vol_info", "heure", "be", "nom", "expediteur"]:
        n_missing = df_local[col].replace("", np.nan).isna().sum()
        if n_missing:
            issues.append({"Type": "Manquants", "Champ": col, "Occurences": int(n_missing)})

    # doublons BE sur même vol
    dup_mask = df_local.duplicated(subset=["be", "vol_day"], keep=False)
    n_dup = int(dup_mask.sum())
    if n_dup:
        issues.append({"Type": "Doublons BE/Vol", "Champ": "be+vol_day", "Occurences": n_dup})

    df_issues = pd.DataFrame(issues)
    if df_issues.empty:
        st.success("Pas d'anomalies détectées sur la période.")
    else:
        st.warning("Anomalies détectées")
        st.dataframe(df_issues, width="stretch", hide_index=True)


def plot_comparison(df: pd.DataFrame, general_period: str):
    if df.empty:
        st.info("Aucune donnée pour la comparaison.")
        return

    df = df.sort_values("date_dt")
    if df["date_dt"].nunique() < 2:
        st.info("Période insuffisante pour comparer.")
        return

    span = df["date_dt"].max() - df["date_dt"].min()
    if span.days <= 0:
        st.info("Période trop courte pour comparer.")
        return

    current = _select_period(df, "Comparaison (période actuelle)", general_period)
    ref_start = df["date_dt"].min() - span
    ref_end = df["date_dt"].min()
    prev = df[(df["date_dt"] >= ref_start) & (df["date_dt"] < ref_end)]

    def _agg(d):
        if d.empty:
            return {"nb_colis": 0, "nb_be": 0, "nb_vol": 0}
        return {
            "nb_colis": int(d["nb_colis"].sum()),
            "nb_be": int(d["be"].nunique()),
            "nb_vol": int(d["vol_day"].nunique()),
        }

    cur = _agg(current)
    old = _agg(prev)

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Colis", cur["nb_colis"], cur["nb_colis"] - old["nb_colis"])
    col_b.metric("BE", cur["nb_be"], cur["nb_be"] - old["nb_be"])
    col_c.metric("Vols (vol+date)", cur["nb_vol"], cur["nb_vol"] - old["nb_vol"])


def plot_top_alerts(df: pd.DataFrame, general_period: str):
    if df.empty:
        st.info("Aucune donnée pour les alertes.")
        return

    df_local = _select_period(df, "Alertes", general_period)
    if df_local.empty:
        st.info("Aucune donnée sur la période.")
        return

    vols = (
        df_local.groupby(["vol_day", "vol_info", "destination_iata", "date_dt"], as_index=False)
        .agg(nb_colis=("nb_colis", "sum"), nb_bene=("nom", "nunique"))
    )
    vols["colis_par_bene"] = vols.apply(
        lambda r: r["nb_colis"] / r["nb_bene"] if r["nb_bene"] else r["nb_colis"], axis=1
    )

    top_charge = vols.sort_values("colis_par_bene", ascending=False).head(10)
    sans_bene = vols[vols["nb_bene"] == 0].head(10)

    st.markdown("**Vols les plus chargés par bénévole**")
    st.dataframe(top_charge, width="stretch", hide_index=True)

    st.markdown("**Vols sans bénévole affecté**")
    if sans_bene.empty:
        st.info("Aucun vol sans bénévole.")
    else:
        st.dataframe(sans_bene, width="stretch", hide_index=True)


# ==========================================================================
#  RAPPORT PDF — STATISTIQUES ANNUELLES
# ==========================================================================


def _df_to_rl_table(df: pd.DataFrame, max_rows: int = 30):
    """
    Convertit un DataFrame en Table ReportLab simple.
    Limite le nombre de lignes pour éviter un PDF gigantesque.
    """
    if df.empty:
        return None

    df = df.head(max_rows).copy()
    data = [list(df.columns)] + df.values.tolist()

    table = Table(data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8e8")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.black),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
            ]
        )
    )
    return table


def generate_year_pdf_report(df: pd.DataFrame, output_dir: Path) -> Path:
    """
    Génère un rapport PDF synthétique dans output_dir / 'Statistiques'.
    Contenu : KPIs globaux, top destinations, top expéditeurs, stats hebdo.
    """
    output_dir = Path(output_dir)
    stats_dir = output_dir / "Statistiques"
    stats_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    year = df["year"].iloc[0] if not df.empty and "year" in df.columns else now.year
    filename = f"ASFmm_STATS_{year}_{now:%Y%m%d-%H%M%S}.pdf"
    pdf_path = stats_dir / filename

    styles = getSampleStyleSheet()
    style_h1 = styles["Heading1"]
    style_h2 = styles["Heading2"]
    style_normal = styles["Normal"]

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    story = []

    # Titre
    story.append(Paragraph(f"ASF — Statistiques Messagerie Médicale {year}", style_h1))
    story.append(Spacer(1, 0.5 * cm))

    # KPIs globaux
    kpi = _kpi_global(df)
    story.append(Paragraph("1. Indicateurs globaux", style_h2))
    story.append(Spacer(1, 0.2 * cm))

    lines = [
        f"• Nombre total de BE : {kpi['nb_be']}",
        f"• Nombre total de colis : {kpi['nb_colis']}",
        f"• Semaines couvertes : {kpi['nb_semaines']}",
        f"• Destinations uniques : {kpi['nb_dest']}",
        f"• Expéditeurs uniques : {kpi['nb_expediteurs']}",
        f"• Bénévoles uniques : {kpi['nb_benevoles']}",
    ]
    for line in lines:
        story.append(Paragraph(line, style_normal))
    story.append(Spacer(1, 0.5 * cm))

    # Stats hebdomadaires
    story.append(Paragraph("2. Volume hebdomadaire", style_h2))
    story.append(Spacer(1, 0.2 * cm))

    weekly = (
        df.groupby("week", as_index=False)
        .agg(nb_colis=("nb_colis", "sum"), nb_be=("be", "nunique"))
        .sort_values("week")
    )
    tbl_week = _df_to_rl_table(weekly.rename(columns={"week": "Semaine"}))
    if tbl_week:
        story.append(tbl_week)
        story.append(Spacer(1, 0.5 * cm))

    # Top destinations
    story.append(Paragraph("3. Top destinations (par colis)", style_h2))
    story.append(Spacer(1, 0.2 * cm))

    dest = (
        df.groupby(["destination_iata", "destination_nom"], as_index=False)
        .agg(nb_colis=("nb_colis", "sum"), nb_be=("be", "nunique"))
        .sort_values("nb_colis", ascending=False)
    )
    dest = dest.rename(
        columns={
            "destination_iata": "IATA",
            "destination_nom": "Destination",
            "nb_colis": "Colis",
            "nb_be": "BE",
        }
    )
    tbl_dest = _df_to_rl_table(dest)
    if tbl_dest:
        story.append(tbl_dest)
        story.append(Spacer(1, 0.5 * cm))

    # Top expéditeurs
    story.append(Paragraph("4. Top expéditeurs (par colis)", style_h2))
    story.append(Spacer(1, 0.2 * cm))

    exped = (
        df.groupby("expediteur", as_index=False)
        .agg(nb_colis=("nb_colis", "sum"), nb_be=("be", "nunique"))
        .sort_values("nb_colis", ascending=False)
        .rename(
            columns={
                "expediteur": "Expéditeur",
                "nb_colis": "Colis",
                "nb_be": "BE",
            }
        )
    )
    tbl_exp = _df_to_rl_table(exped)
    if tbl_exp:
        story.append(tbl_exp)
        story.append(Spacer(1, 0.5 * cm))

    # Commentaire final
    story.append(Paragraph("5. Commentaires", style_h2))
    story.append(Spacer(1, 0.2 * cm))
    story.append(
        Paragraph(
            "Ce rapport est généré automatiquement à partir des plannings validés "
            "ASFmm 2025. Il permet d'avoir une vue synthétique des flux sur l'année.",
            style_normal,
        )
    )

    doc.build(story)
    return pdf_path


def _resolve_stats_default_planning_dir() -> Path:
    try:
        from scheduler.config_paths import detect_onedrive_asf

        base_root = detect_onedrive_asf()
    except (ImportError, OSError, RuntimeError, TypeError, ValueError):
        base_root = get_onedrive_root()
    return base_root / "Planning MAB" / "ASFmm PLANNING 2025"


def _render_stats_planning_dir_selector(default_dir: Path) -> Path:
    if "stats_planning_dir" not in st.session_state:
        st.session_state["stats_planning_dir"] = str(default_dir)

    with st.expander("📂 Dossier plannings à analyser", expanded=False):
        st.caption("Saisis le dossier contenant les fichiers 'ASFmm - PLANNING SEMAINE YYYY-XX-ZZ.xlsx'")
        selected_dir = st.text_input(
            "Chemin du dossier plannings",
            value=st.session_state["stats_planning_dir"],
        )
        if st.button("✅ Utiliser ce dossier", key="btn_stats_set_dir"):
            st.session_state["stats_planning_dir"] = selected_dir.strip()
            st.session_state.pop("stats_should_load", None)
            st.rerun()

    planning_dir = Path(st.session_state.get("stats_planning_dir", default_dir))
    st.caption(f"Dossier plannings : `{planning_dir}`")
    return planning_dir


def _trigger_stats_loading() -> bool:
    if st.button("📥 Charger / actualiser les données", key="btn_stats_load"):
        st.session_state["stats_should_load"] = True
    return bool(st.session_state.get("stats_should_load"))


def _load_stats_dataframe(planning_dir: Path) -> pd.DataFrame:
    with st.spinner("Chargement des plannings et préparation des statistiques…"):
        return _load_all_plannings(base_override=planning_dir)


def _resolve_stats_year_default(years: list[int]) -> int:
    current_year = datetime.now().year
    if current_year in years:
        return current_year
    if (current_year - 1) in years:
        return current_year - 1
    return years[0] if years else current_year


def _render_stats_filters(df_all: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, str] | None:
    years = sorted(df_all["year"].dropna().unique())
    if not years:
        return None

    year_default = _resolve_stats_year_default(years)
    col_y, col_w = st.columns([1, 2])
    with col_y:
        year_sel = st.selectbox(
            "Année à analyser",
            options=years,
            index=years.index(year_default) if year_default in years else 0,
        )

    df_year = df_all[df_all["year"] == year_sel].copy()
    weeks = sorted(df_year["week"].dropna().unique())
    if not weeks:
        return None

    with col_w:
        if len(weeks) == 1:
            week_min = week_max = int(weeks[0])
        else:
            week_min, week_max = int(min(weeks)), int(max(weeks))
        week_range = st.slider(
            "Intervalle de semaines",
            week_min,
            week_max,
            (week_min, week_max),
        )

    df = df_year[
        (df_year["week"] >= week_range[0]) & (df_year["week"] <= week_range[1])
    ].copy()
    if df.empty:
        return df_year, df, "Annuel"

    general_period = st.selectbox(
        "Période générale pour les blocs",
        _PERIOD_OPTIONS,
        index=_PERIOD_OPTIONS.index("Annuel"),
    )
    df = _filter_period(df, general_period, ref_date=df["date_dt"].max())
    return df_year, df, general_period


def _render_stats_kpi_block(df: pd.DataFrame) -> None:
    kpi = _kpi_global(df)

    st.subheader("📌 Indicateurs clés sur la période sélectionnée")
    c1, c2, c3 = st.columns(3)
    c4, c5, c6 = st.columns(3)
    c1.metric("BE distincts", kpi["nb_be"])
    c2.metric("Colis totaux", kpi["nb_colis"])
    c3.metric("Semaines couvertes", kpi["nb_semaines"])
    c4.metric("Destinations", kpi["nb_dest"])
    c5.metric("Expéditeurs", kpi["nb_expediteurs"])
    c6.metric("Bénévoles", kpi["nb_benevoles"])

    with st.expander("Voir un extrait du jeu de données (20 premières lignes)", expanded=False):
        st.dataframe(df.head(20), width="stretch")


def _render_stats_visual_sections(df: pd.DataFrame, general_period: str) -> None:
    st.markdown("---")
    st.subheader("📦 Volume hebdomadaire")
    plot_weekly_volume(df, general_period)

    st.markdown("---")
    st.subheader("🌍 Destinations")
    plot_top_destinations(df, general_period)

    st.markdown("---")
    st.subheader("📦 Types de colis")
    plot_type_colis(df, general_period)

    st.markdown("---")
    st.subheader("🕒 Répartition jour / heure")
    plot_hour_day_heatmap(df, general_period)

    st.markdown("---")
    st.subheader("🔥 Heatmap semaine / destination")
    plot_heatmap_week_destination(df, general_period)

    st.markdown("---")
    st.subheader("👥 Charge bénévoles")
    plot_benevole_load(df, general_period)

    st.markdown("---")
    st.subheader("📦✈️ Expéditeur × Destination")
    plot_exp_dest_matrix(df, general_period)

    st.markdown("---")
    st.subheader("📦 Expéditeurs")
    plot_expediteur_volume(df, general_period)

    st.markdown("---")
    st.subheader("⚠️ Alerte / Qualité")
    plot_top_alerts(df, general_period)
    st.markdown("")
    plot_quality_report(df, general_period)

    st.markdown("---")
    st.subheader("↔️ Comparaison période précédente")
    plot_comparison(df, general_period)


def _render_stats_pdf_export(df_year: pd.DataFrame) -> None:
    st.markdown("---")
    st.subheader("🧾 Rapport PDF annuel")
    st.caption(
        "Ce bouton analyse tous les plannings de l'année sélectionnée "
        "et génère un rapport PDF dans le sous-dossier "
        "`Statistiques` de `OUTPUT_PLANNING_DIR`."
    )

    if st.button("📑 Analyser toute l'année et générer un rapport PDF"):
        with st.spinner("Génération du rapport PDF en cours…"):
            pdf_path = generate_year_pdf_report(df_year, get_output_planning_dir())
        st.success(f"Rapport généré : `{pdf_path.name}`")
        with open(pdf_path, "rb") as f:
            data = f.read()
        st.download_button(
            "⬇ Télécharger le rapport PDF",
            data=data,
            file_name=pdf_path.name,
            mime="application/pdf",
        )


# ==========================================================================
#  ONGLET STATS — UI PRINCIPALE
# ==========================================================================


def render_tab_stats():
    """
    Onglet complet :
      - Chargement de tous les plannings ASFmm (dernière version par semaine)
      - Filtres année / semaines
      - KPIs globaux
      - Graphiques Plotly interactifs
      - Génération d'un rapport PDF annuel dans OUTPUT_PLANNING_DIR/Statistiques
    """
    st.header("📊 Statistiques & analyse des plannings ASFmm 2025")

    default_dir = _resolve_stats_default_planning_dir()
    planning_dir = _render_stats_planning_dir_selector(default_dir)
    if not _trigger_stats_loading():
        st.info("Clique sur « Charger / actualiser les données » pour afficher les statistiques.")
        return

    df_all = _load_stats_dataframe(planning_dir)
    if df_all.empty:
        st.info("Aucun planning ASFmm détecté ou DataFrame vide.")
        return

    filters = _render_stats_filters(df_all)
    if filters is None:
        st.warning("Aucune donnée annuelle exploitable.")
        return
    df_year, df, general_period = filters
    if df.empty:
        st.warning("Aucune donnée dans l'intervalle choisi.")
        return

    _render_stats_kpi_block(df)
    _render_stats_visual_sections(df, general_period)
    _render_stats_pdf_export(df_year)
