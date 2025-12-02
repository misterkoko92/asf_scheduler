# asf_app/ui/ui_week_data.py
# -*- coding: utf-8 -*-

import streamlit as st
import pandas as pd
from datetime import datetime

from asf_app.state import get_state

from scheduler.be_manager import filter_shipments, sort_shipments
from loaders.load_shipments import load_shipments


# ======================================================================
# Détection semaine
# ======================================================================
def detect_week(state):
    df_vols = state.df_vols
    if df_vols is None or df_vols.empty:
        return None
    if "Date_Vol" not in df_vols.columns:
        return None
    dates = pd.to_datetime(df_vols["Date_Vol"], errors="coerce").dropna()
    if dates.empty:
        return None
    return int(dates.min().isocalendar().week)


# ======================================================================
# Conversion robust datetime
# ======================================================================
def robust_to_datetime(series):
    try:
        return pd.to_datetime(series, errors="coerce")
    except Exception:
        return pd.to_datetime(series.astype(str), errors="coerce")


# ======================================================================
# Bloc sortable générique
# ======================================================================
def bloc_with_sort(title, df, sort_options, default_sort, min_height=350):
    with st.container():
        st.markdown(f"<div style='min-height:{min_height}px'>", unsafe_allow_html=True)
        st.subheader(title)

        if df is None or df.empty:
            st.info("Aucune donnée.")
            st.markdown("</div>", unsafe_allow_html=True)
            return

        df = df.reset_index(drop=True)

        sort_choice = st.selectbox(
            f"Trier par ({title})",
            sort_options,
            index=sort_options.index(default_sort) if default_sort in sort_options else 0
        )

        if sort_choice in df.columns:
            df = df.sort_values(sort_choice, kind="mergesort")

        st.data_editor(df, width="stretch", hide_index=True, disabled=True)
        st.markdown("</div>", unsafe_allow_html=True)


# ======================================================================
# BE moteur ASF
# ======================================================================
def load_be_moteur():
    state = get_state()

    if state.df_param_be is None or state.df_param_be.empty:
        return None, "ParamBE indisponible"

    try:
        shipments = load_shipments(state.df_param_be.copy())
    except Exception as e:
        return None, f"Erreur load_shipments : {e}"

    if not shipments:
        return None, "Aucun BE moteur"

    shipments = filter_shipments(shipments)
    shipments = sort_shipments(shipments)

    df_be = pd.DataFrame([
        {
            "BE_Numero": str(s.be_numero),
            "Type": s.type_colis,
            "Destination": getattr(s, "dest", ""),
            "IATA": getattr(s, "dest_iata", getattr(s, "dest", "")),
            "Expéditeur": s.expediteur,
            "Nb_Colis": s.nb_colis_physiques,
            "Equiv_colis": s.equiv_colis,
            "Priorité": s.priority,
            "Douane": "OUI" if s.customs else "NON",
            "Special": s.special or "",
        }
        for s in shipments
    ])

    return df_be, None


# ======================================================================
# Onglet Données Semaine
# ======================================================================
def render_tab_week_data():
    state = get_state()
    week = detect_week(state)

    st.header(f"📊 Données — Semaine {week if week else 'inconnue'}")

    col1, col2, col3 = st.columns(3, gap="medium")

    # ==========================================================================
    # BE PLANIFIABLES
    # ==========================================================================
    df_be, err = load_be_moteur()
    if df_be is None:
        df_be = pd.DataFrame()
        st.error(f"❌ Erreur BE moteur : {err}")

    with col1:
        bloc_with_sort(
            title="BE à planifier",
            df=df_be,
            sort_options=["Priorité", "BE_Numero", "Destination", "IATA", "Expéditeur", "Type"],
            default_sort="BE_Numero",
            min_height=50
        )

    # ==========================================================================
    # BÉNÉVOLES — FORMAT + MASQUAGE
    # ==========================================================================
    if state.df_benev is not None and not state.df_benev.empty:

        tmp = state.df_benev.copy()
        tmp["Date_dt"] = robust_to_datetime(tmp["Date"])

        if week:
            tmp = tmp[tmp["Date_dt"].dt.isocalendar().week == week]

        tmp["Date_fmt"] = tmp["Date_dt"].dt.strftime("%d/%m/%y")

        # --- extraction brute ---
        df_benev = tmp[[
            "Nom",
            "Date_fmt",
            "Heure_Arrivee",
            "Heure_Depart"
        ]].rename(columns={
            "Date_fmt": "Date",
            "Heure_Arrivee": "Arrivée_brut",
            "Heure_Depart": "Départ_brut"
        })

        # --- parsing minimal ---
        def parse_time(v):
            if v is None or v == "" or pd.isna(v):
                return None

            # string simples
            s = str(v).strip().lower()
            s = s.replace("h", ":").replace(" ", "")
            if s.isdigit() and len(s) == 2:
                s += ":00"

            try:
                t = pd.to_datetime(s, errors="coerce")
                if t is not None:
                    return t.time()
            except:
                pass

            # float Excel
            try:
                if isinstance(v, (float, int)):
                    base = datetime(1899, 12, 30) + pd.to_timedelta(float(v), unit="D")
                    return base.time()
            except:
                pass

            return None

        arr_t = df_benev["Arrivée_brut"].apply(parse_time)
        dep_t = df_benev["Départ_brut"].apply(parse_time)

        # --- format final ---
        arr_fmt = []
        for t in arr_t:
            if t is None:
                arr_fmt.append("")
                continue
            new_t = datetime.combine(datetime.today(), t) + pd.Timedelta(hours=3)
            arr_fmt.append(new_t.strftime("%Hh%M"))

        dep_fmt = []
        for t in dep_t:
            if t is None:
                dep_fmt.append("")
                continue
            dep_fmt.append(t.strftime("%Hh%M"))

        df_benev["Arrivée"] = arr_fmt
        df_benev["Départ"] = dep_fmt

        # --- MASQUAGE : si arrivée vide OU départ vide → ligne supprimée ---
        df_benev = df_benev[df_benev["Arrivée"] != ""]
        df_benev = df_benev[df_benev["Départ"] != ""]

        # on ne garde que les 4 colonnes utiles
        df_benev = df_benev[["Nom", "Date", "Arrivée", "Départ"]]

    else:
        df_benev = pd.DataFrame()

    with col2:
        bloc_with_sort(
            title="Bénévoles disponibles",
            df=df_benev,
            sort_options=["Nom", "Date", "Arrivée", "Départ"],
            default_sort="Nom",
            min_height=50
        )

    # ==========================================================================
    # VOLS — MASQUAGE HEURES VIDES
    # ==========================================================================
    if state.df_vols is not None and not state.df_vols.empty:
        tmp = state.df_vols.copy()
        tmp["Date_dt"] = robust_to_datetime(tmp["Date_Vol"])

        if week:
            tmp = tmp[tmp["Date_dt"].dt.isocalendar().week == week]

        tmp["Date_fmt"] = tmp["Date_dt"].dt.strftime("%d/%m/%y")

        df_flights = tmp[[
            "Destination_Nom",
            "Date_fmt",
            "Heure_Vol",
            "Routing"
        ]].rename(columns={
            "Destination_Nom": "Destination",
            "Date_fmt": "Date",
            "Heure_Vol": "Heure",
        })

        # --- masquage des lignes sans heure ---
        df_flights = df_flights[df_flights["Heure"].notna()]
        df_flights = df_flights[df_flights["Heure"] != ""]

        # tri strict
        if not df_flights.empty:
            df_flights = df_flights.sort_values(
                ["Destination", "Date", "Heure"],
                kind="mergesort"
            ).reset_index(drop=True)

    else:
        df_flights = pd.DataFrame()

    with col3:
        bloc_with_sort(
            title="Vols disponibles",
            df=df_flights,
            sort_options=["Destination", "Date", "Heure"],
            default_sort="Destination",
            min_height=50
        )
