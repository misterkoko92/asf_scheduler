# asf_app/ui/ui_week_data.py
# -*- coding: utf-8 -*-

from pathlib import Path

import pandas as pd
import streamlit as st

from asf_app.state import get_excel_source_paths, get_state
from asf_app.ui.ui_week_data_helpers import (
    _build_benev_ranges_by_date,
    _build_benev_week_table,
    _build_day_labels,
    _build_flights_week_table,
    _compute_week_dates,
)
from loaders.load_shipments import load_shipments_df
from utils.datetime_utils import (
    coerce_datetime,
    format_date_series,
    format_date_value,
    format_time_series,
    normalize_hour_value,
    parse_date_series,
    parse_date_value,
    parse_time_series,
)
from utils.logging_utils import get_logger
from utils.ui_helpers import build_iata_city_maps, format_be_label, format_vol_label

logger = get_logger("ui_week_data", console=False)


# ======================================================================
# Détection semaine
# ======================================================================
def detect_week(state):
    df_vols = state.df_vols
    if df_vols is None or df_vols.empty:
        return None
    if "Date_Vol" not in df_vols.columns:
        return None
    dates = parse_date_series(df_vols["Date_Vol"]).dropna()
    if dates.empty:
        return None
    return int(dates.min().isocalendar().week)


# ======================================================================
# Conversion robust datetime
# ======================================================================
def robust_to_datetime(series):
    try:
        return parse_date_series(series)
    except (AttributeError, TypeError, ValueError):
        return parse_date_series(series.astype(str))


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
        tdb_path = Path(state.tdb_tmp) if state.tdb_tmp is not None else None
        df_raw = load_shipments_df(
            planifiables_only=True,
            param_be_raw=state.df_param_be.copy(),
            tdb_path=tdb_path,
        )
    except (FileNotFoundError, OSError, KeyError, RuntimeError, TypeError, ValueError) as e:
        return None, f"Erreur load_shipments_df : {e}"

    if df_raw is None or df_raw.empty:
        return None, "Aucun BE moteur"

    def _col(name: str, default: str = "") -> pd.Series:
        if name in df_raw.columns:
            return df_raw[name]
        return pd.Series([default] * len(df_raw), index=df_raw.index)

    df_be = pd.DataFrame()
    df_be["BE_Numero"] = _col("BE_Numero").astype(str)
    df_be["Type"] = _col("BE_Type").astype(str)
    df_be["Destination"] = _col("Destination").astype(str)
    df_be["IATA"] = _col("Destination").astype(str)
    df_be["Expéditeur"] = _col("BE_Expediteur").astype(str)
    df_be["Nb_Colis"] = pd.to_numeric(_col("BE_Nb_Colis", "0"), errors="coerce").fillna(0).astype(int)
    df_be["Equiv_colis"] = pd.to_numeric(_col("Equiv_Colis", "0"), errors="coerce").fillna(0).astype(int)
    df_be["Priorité"] = pd.to_numeric(_col("Priorite", "0"), errors="coerce").fillna(0).astype(int)
    douane_raw = _col("BE_Douane").astype(str).str.strip().str.lower()
    df_be["Douane"] = douane_raw.apply(
        lambda v: "OUI" if v in {"oui", "yes", "1", "true"} else "NON"
    )
    df_be["Special"] = _col("BE_Special").astype(str)

    df_be = df_be.sort_values(
        by=["Priorité", "Equiv_colis"],
        ascending=[True, False],
        kind="mergesort",
    ).reset_index(drop=True)

    return df_be, None


# ======================================================================
# Onglet Données Semaine
# ======================================================================
def render_tab_week_data():
    state = get_state()
    if state.api_start_date:
        week = coerce_datetime(state.api_start_date).isocalendar().week
    else:
        week = detect_week(state)

    st.header(f"📊 Données — Semaine {week if week else 'inconnue'}")

    col1, col2, col3 = st.columns(3, gap="medium")

    # Mapping ParamDest pour affichages (ville <-> IATA)
    iata_to_city, city_to_iata = build_iata_city_maps(state.df_param_dest)

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
        # Label standard
        def _label_be(row):
            return format_be_label(
                dest=str(row.get("IATA", row.get("Destination", ""))),
                be_num=str(row.get("BE_Numero", "")),
                nb_colis=row.get("Nb_Colis", row.get("BE_Nb_Colis", "")),
                be_type=row.get("Type", ""),
                status="moteur",
                date_str=row.get("Date_Vol", ""),
            )
        df_be["Label"] = df_be.apply(_label_be, axis=1)

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
            mask = (tmp["Date_dt"] >= coerce_datetime(state.api_start_date)) & (
                tmp["Date_dt"] <= coerce_datetime(state.api_end_date)
            )
            tmp = tmp[mask]
        elif week:
            tmp = tmp[tmp["Date_dt"].dt.isocalendar().week == week]

        tmp["Date_fmt"] = format_date_series(tmp["Date_dt"], fmt="%d/%m/%y")

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
        arr_dt = parse_time_series(
            df_benev["Arrivée_brut"],
            allow_hour_only=True,
            allow_general_fallback=True,
            strip_spaces=True,
            lowercase=True,
        )
        dep_dt = parse_time_series(
            df_benev["Départ_brut"],
            allow_hour_only=True,
            allow_general_fallback=True,
            strip_spaces=True,
            lowercase=True,
        )
        valid_mask = arr_dt.notna() & dep_dt.notna()

        # --- format final ---
        arr_fmt = format_time_series(
            arr_dt + pd.Timedelta(hours=3),
            fmt="%Hh%M",
            allow_general_fallback=True,
        ).fillna("")
        dep_fmt = format_time_series(
            dep_dt,
            fmt="%Hh%M",
            allow_general_fallback=True,
        ).fillna("")

        df_benev["Arrivée"] = arr_fmt
        df_benev["Départ"] = dep_fmt

        # --- MASQUAGE : si arrivée vide OU départ vide → ligne supprimée ---
        # Filtre période choisie (prioritaire si définie)
        df_benev["Date_dt"] = robust_to_datetime(df_benev["Date"])
        if state.api_start_date and state.api_end_date:
            start_dt = coerce_datetime(state.api_start_date)
            end_dt = coerce_datetime(state.api_end_date)
            mask = (df_benev["Date_dt"] >= start_dt) & (df_benev["Date_dt"] <= end_dt)
            df_benev = df_benev[mask]
        elif week:
            df_benev = df_benev[df_benev["Date_dt"].dt.isocalendar().week == week]

        # Garder uniquement les bénévoles avec créneaux valides
        df_benev = df_benev[valid_mask]

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
            paths = get_excel_source_paths(state)
            state.df_vols = load_vols_df(vols_path=paths.vols, param_dest_df=state.df_param_dest)
        except (ImportError, FileNotFoundError, OSError, KeyError, RuntimeError, TypeError, ValueError):
            state.df_vols = None

    def _parse_time_val(val):
        return normalize_hour_value(val, allow_general_fallback=True)

    if state.df_vols is not None and not state.df_vols.empty:
        vols_df = state.df_vols.copy()
        vols_df["Date_dt"] = parse_date_series(vols_df["Date_Vol"], allow_dayfirst_false=False)

        # Période choisie
        if state.api_start_date and state.api_end_date:
            start_dt = parse_date_value(state.api_start_date, allow_dayfirst_false=False)
            end_dt = parse_date_value(state.api_end_date, allow_dayfirst_false=False)
            vols_df = vols_df[(vols_df["Date_dt"] >= start_dt) & (vols_df["Date_dt"] <= end_dt)]
        elif week:
            vols_df = vols_df[vols_df["Date_dt"].dt.isocalendar().week == week]

        def fmt_hour(v):
            return _parse_time_val(v)

        # Destinations éligibles (BE statut D) — matching sur IATA
        iata_set = set()
        try:
            df_be_planif, _ = load_be_moteur()
            for _, rr in df_be_planif.iterrows():
                i = str(rr.get("IATA", "")).strip().upper()
                if len(i) == 3:
                    iata_set.add(i)
        except (AttributeError, KeyError, TypeError, ValueError):
            pass
        try:
            if state.df_be is not None and not state.df_be.empty:
                df_be_d = state.df_be[state.df_be.get("Status_BE", "").astype(str).str.strip() == "D"]
                for _, rr in df_be_d.iterrows():
                    i = str(rr.get("Dest_IATA", rr.get("IATA", ""))).strip().upper()
                    if len(i) == 3:
                        iata_set.add(i)
        except (AttributeError, KeyError, TypeError, ValueError):
            pass
        allow_all_dest = len(iata_set) == 0
        logger.debug("[Vols dispo] IATA BE D: %s", sorted(iata_set))

        rows_map: dict[tuple[str, str, str, str, str], dict[str, object]] = {}
        for _, r in vols_df.iterrows():
            dtdt = r.get("Date_dt")
            if pd.isna(dtdt):
                continue
            heure_str = fmt_hour(r.get("Heure_Vol", ""))
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
                label = format_vol_label(dtdt, dest_iata, r.get("Numero_Vol", ""), heure_str, sub_route, r.get("Source", "excel"))
                date_str = format_date_value(dtdt, fmt="%d/%m/%y", default="")
                numero_vol = str(r.get("Numero_Vol", "")).strip()
                source = str(r.get("Source", "excel")).strip() or "excel"
                source_priority = 0 if source.lower() == "api" else 1
                row_key = (
                    str(dest_iata).strip().upper(),
                    date_str,
                    str(heure_str).strip(),
                    numero_vol,
                    sub_route,
                )
                row_payload = {
                    "Destination": dest_city,
                    "Date": date_str,
                    "Heure": heure_str,
                    "Routing": sub_route,
                    "Numero_Vol": numero_vol,
                    "IATA": dest_iata,
                    "Source": source,
                    "Label": label,
                    "_source_priority": source_priority,
                }
                existing = rows_map.get(row_key)
                if existing is None or source_priority < int(existing.get("_source_priority", 99)):
                    rows_map[row_key] = row_payload

        df_flights = pd.DataFrame(rows_map.values())

        if not df_flights.empty:
            df_flights = df_flights.drop(columns=["_source_priority"], errors="ignore")
            df_flights = df_flights.sort_values(["Destination", "Date", "Heure", "Numero_Vol"], kind="mergesort").reset_index(drop=True)
            if "HEURE_MIN" in df_flights.columns:
                df_flights["HEURE_MIN"] = pd.to_numeric(df_flights["HEURE_MIN"], errors="coerce")
        logger.debug("[Vols dispo] Lignes retenues: %s", len(df_flights))
        if not df_flights.empty:
            logger.debug("[Vols dispo] Dates: %s", sorted(df_flights["Date"].unique().tolist()))
            logger.debug("[Vols dispo] Dest: %s", sorted(df_flights["Destination"].unique().tolist()))

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

    # ------------------------------------------------------------------
    # Vues détaillées (collapse)
    # ------------------------------------------------------------------
    week_dates = _compute_week_dates(
        api_start_date=state.api_start_date,
        week=week,
        df_benev=df_benev,
        df_flights=df_flights,
    )
    day_labels = _build_day_labels(week_dates)

    # ---- Bloc bénévoles (disponibilités) ----
    with st.expander("👥 Disponibilités bénévoles (vue semaine)", expanded=False):
        table_benev, mask_benev = _build_benev_week_table(
            df_benev,
            week_dates=week_dates,
            day_labels=day_labels,
        )
        if table_benev.empty:
            st.info("Aucune disponibilité bénévole sur la période.")
        else:
            def _style_mask(_):
                green = "background-color: #d9f2d9;"
                red = "background-color: #f7d6d6;"
                return pd.DataFrame(
                    [
                        [
                            green if mask_benev.iloc[i, j] else red
                            for j in range(mask_benev.shape[1])
                        ]
                        for i in range(mask_benev.shape[0])
                    ],
                    index=mask_benev.index,
                    columns=mask_benev.columns,
                )

            header_styles = [
                {"selector": "th.col_heading.level0", "props": [("text-align", "center")]},
                {"selector": "th.col_heading.level1", "props": [("text-align", "center")]},
            ]

            styler = (
                table_benev.style.apply(_style_mask, axis=None)
                .set_properties(**{"text-align": "center"})
                .set_table_styles(header_styles, overwrite=False)
            )
            st.dataframe(styler, use_container_width=True)

    # ---- Bloc vols (disponibilités) ----
    with st.expander("✈️ Vols disponibles (vue semaine)", expanded=False):
        benev_by_date = _build_benev_ranges_by_date(df_benev)
        table_flights, status_flights = _build_flights_week_table(
            df_flights,
            df_be=df_be,
            week_dates=week_dates,
            day_labels=day_labels,
            benev_by_date=benev_by_date,
        )
        if table_flights.empty:
            st.info("Aucun vol disponible sur la période.")
        else:
            def _style_mask_flights(_):
                green = "background-color: #d9f2d9;"
                orange = "background-color: #f7e1b5;"
                red = "background-color: #f7d6d6;"
                color_map = {
                    "compatible": green,
                    "incompatible": orange,
                    "none": red,
                }
                return pd.DataFrame(
                    [
                        [
                            color_map.get(status_flights.iloc[i, j], red)
                            for j in range(status_flights.shape[1])
                        ]
                        for i in range(status_flights.shape[0])
                    ],
                    index=status_flights.index,
                    columns=status_flights.columns,
                )

            header_styles = [
                {"selector": "th.col_heading", "props": [("text-align", "center"), ("font-size", "0.7em")]},
                {"selector": "th.row_heading", "props": [("font-size", "0.7em")]},
            ]

            styler = (
                table_flights.style.apply(_style_mask_flights, axis=None)
                .set_properties(**{"text-align": "left", "white-space": "pre-line", "font-size": "0.7em"})
                .set_table_styles(header_styles, overwrite=False)
            )
            st.dataframe(styler, use_container_width=True)
