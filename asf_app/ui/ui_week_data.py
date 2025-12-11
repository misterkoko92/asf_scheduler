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
    dates = pd.to_datetime(df_vols["Date_Vol"], errors="coerce", dayfirst=True, format="%d/%m/%y").dropna()
    if dates.empty:
        return None
    return int(dates.min().isocalendar().week)


# ======================================================================
# Conversion robust datetime
# ======================================================================
def robust_to_datetime(series):
    try:
        return pd.to_datetime(series, errors="coerce", dayfirst=True, format="%d/%m/%y")
    except Exception:
        return pd.to_datetime(series.astype(str), errors="coerce", dayfirst=True, format="%d/%m/%y")


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
    if state.api_start_date:
        week = pd.to_datetime(state.api_start_date).isocalendar().week
    else:
        week = detect_week(state)

    st.header(f"📊 Données — Semaine {week if week else 'inconnue'}")

    col1, col2, col3 = st.columns(3, gap="medium")

    # Mapping ParamDest pour affichages (ville <-> IATA)
    iata_to_city = {}
    city_to_iata = {}
    try:
        if state.df_param_dest is not None and not state.df_param_dest.empty:
            for _, r in state.df_param_dest.iterrows():
                iata = str(r.get("Dest_IATA", "")).upper()
                city = str(r.get("Dest_Ville", "")).upper()
                if iata:
                    iata_to_city[iata] = city or iata
                if city:
                    city_to_iata[city] = iata or city
    except Exception:
        pass

    # ==========================================================================
    # BE PLANIFIABLES
    # ==========================================================================
    df_be, err = load_be_moteur()
    if df_be is None:
        df_be = pd.DataFrame()
        st.error(f"❌ Erreur BE moteur : {err}")
    else:
        # Affichage Destination = Ville si possible
        if "Destination" in df_be.columns:
            df_be["Destination"] = df_be.apply(
                lambda r: iata_to_city.get(str(r.get("IATA", "")).upper(), str(r.get("Destination", ""))),
                axis=1
            )

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

        if state.api_start_date and state.api_end_date:
            mask = (tmp["Date_dt"] >= pd.to_datetime(state.api_start_date)) & (
                tmp["Date_dt"] <= pd.to_datetime(state.api_end_date)
            )
            tmp = tmp[mask]
        elif week:
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
        # Filtre période choisie (prioritaire si définie)
        df_benev["Date_dt"] = robust_to_datetime(df_benev["Date"])
        if state.api_start_date and state.api_end_date:
            start_dt = pd.to_datetime(state.api_start_date)
            end_dt = pd.to_datetime(state.api_end_date)
            mask = (df_benev["Date_dt"] >= start_dt) & (df_benev["Date_dt"] <= end_dt)
            df_benev = df_benev[mask]
        elif week:
            df_benev = df_benev[df_benev["Date_dt"].dt.isocalendar().week == week]

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
    # VOLS — reconstruction propre par segment
    # ==========================================================================
    # Si le dataframe vols n'est pas chargé, on tente un chargement direct
    if state.df_vols is None or (hasattr(state.df_vols, "empty") and state.df_vols.empty):
        try:
            from loaders.load_vols import load_vols_df
            state.df_vols = load_vols_df()
        except Exception:
            state.df_vols = None

    if state.df_vols is not None and not state.df_vols.empty:
        vols_df = state.df_vols.copy()
        vols_df["Date_dt"] = pd.to_datetime(vols_df["Date_Vol"], errors="coerce", dayfirst=True)

        # Période choisie
        if state.api_start_date and state.api_end_date:
            start_dt = pd.to_datetime(state.api_start_date)
            end_dt = pd.to_datetime(state.api_end_date)
            vols_df = vols_df[(vols_df["Date_dt"] >= start_dt) & (vols_df["Date_dt"] <= end_dt)]
        elif week:
            vols_df = vols_df[vols_df["Date_dt"].dt.isocalendar().week == week]

        def fmt_hour(v):
            if v is None or v == "" or pd.isna(v):
                return ""
            if hasattr(v, "strftime"):
                return v.strftime("%Hh%M")
            parsed = pd.to_datetime(v, errors="coerce", dayfirst=True)
            if pd.isna(parsed):
                return ""
            return parsed.strftime("%Hh%M")

        # Destinations éligibles (BE statut D) — matching sur IATA
        iata_set = set()
        try:
            df_be_planif, _ = load_be_moteur()
            for _, rr in df_be_planif.iterrows():
                i = str(rr.get("IATA", "")).strip().upper()
                if len(i) == 3:
                    iata_set.add(i)
        except Exception:
            pass
        try:
            if state.df_be is not None and not state.df_be.empty:
                df_be_d = state.df_be[state.df_be.get("Status_BE", "").astype(str).str.strip() == "D"]
                for _, rr in df_be_d.iterrows():
                    i = str(rr.get("Dest_IATA", rr.get("IATA", ""))).strip().upper()
                    if len(i) == 3:
                        iata_set.add(i)
        except Exception:
            pass
        allow_all_dest = len(iata_set) == 0
        # Debug sets
        try:
            print("[Vols dispo] IATA BE D:", sorted(iata_set))
        except Exception:
            pass

        rows = []
        for _, r in vols_df.iterrows():
            dtdt = r.get("Date_dt")
            if pd.isna(dtdt):
                continue
            date_str = dtdt.strftime("%d/%m/%y")
            heure_str = str(r.get("Heure_Vol", "")).strip()
            if not heure_str:
                continue
            routing_raw = str(r.get("Routing", "")) or ""
            parts = [p.strip().upper() for p in routing_raw.replace(" ", "").replace(",", "-").split("-") if p]
            # si le dernier est CDG (retour), on le retire pour l'affichage
            if len(parts) > 1 and parts[-1] == "CDG":
                parts = parts[:-1]
            if len(parts) < 2:
                continue
            # chaque segment vérifie si la destination est dans les BE
            for idx in range(1, len(parts)):
                dest_iata = parts[idx]
                dest_city = iata_to_city.get(dest_iata, dest_iata)
                if (not allow_all_dest) and dest_iata not in iata_set:
                    continue
                # Affiche toujours le routing complet (sans retour CDG), même si la destination est un stop intermédiaire
                sub_route = "-".join(parts)
                rows.append({
                    "Destination": dest_city,
                    "Date": date_str,
                    "Heure": heure_str,
                    "Routing": sub_route,
                    "Numero_Vol": r.get("Numero_Vol", ""),
                    "IATA": dest_iata,
                    "Source": r.get("Source", "excel"),
                })

        df_flights = pd.DataFrame(rows)

        if not df_flights.empty:
            df_flights = df_flights.sort_values(["Destination", "Date", "Heure", "Numero_Vol"], kind="mergesort").reset_index(drop=True)
        try:
            print("[Vols dispo] Lignes retenues:", len(df_flights))
            if not df_flights.empty:
                print("[Vols dispo] Dates:", sorted(df_flights["Date"].unique().tolist()))
                print("[Vols dispo] Dest:", sorted(df_flights["Destination"].unique().tolist()))
        except Exception:
            pass

    else:
        df_flights = pd.DataFrame()

    with col3:
        bloc_with_sort(
            title="Vols disponibles",
            df=df_flights,
            sort_options=["Destination", "Date", "Heure", "Numero_Vol"],
            default_sort="Destination",
            min_height=50,
        )
