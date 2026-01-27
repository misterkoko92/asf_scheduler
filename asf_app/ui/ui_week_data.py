# asf_app/ui/ui_week_data.py
# -*- coding: utf-8 -*-

import streamlit as st
import pandas as pd
from datetime import datetime, date
from pathlib import Path

from asf_app.state import get_state, get_excel_source_paths

from loaders.load_shipments import load_shipments_df
from utils.ui_helpers import build_iata_city_maps, format_be_label, format_vol_label
from utils.datetime_utils import (
    parse_date_series,
    parse_date_value,
    parse_time_series,
    normalize_hour_value,
    hour_min_value,
    coerce_datetime,
    format_date_series,
    format_time_series,
    format_date_value,
)
from utils.identifiers import format_vol_display


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
    except Exception:
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
    except Exception as e:
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
        except Exception:
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
                rows.append({
                    "Destination": dest_city,
                    "Date": format_date_value(dtdt, fmt="%d/%m/%y", default=""),
                    "Heure": heure_str,
                    "Routing": sub_route,
                    "Numero_Vol": r.get("Numero_Vol", ""),
                    "IATA": dest_iata,
                    "Source": r.get("Source", "excel"),
                    "Label": label,
                })

        df_flights = pd.DataFrame(rows)

        if not df_flights.empty:
            df_flights = df_flights.sort_values(["Destination", "Date", "Heure", "Numero_Vol"], kind="mergesort").reset_index(drop=True)
            if "HEURE_MIN" in df_flights.columns:
                df_flights["HEURE_MIN"] = pd.to_numeric(df_flights["HEURE_MIN"], errors="coerce")
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

    # ------------------------------------------------------------------
    # Vues détaillées (collapse)
    # ------------------------------------------------------------------
    def _week_dates():
        if state.api_start_date:
            ref = coerce_datetime(state.api_start_date, errors="coerce")
        else:
            ref = None
            for df in (df_benev, df_flights):
                if df is None or df.empty:
                    continue
                col = "Date"
                if col in df.columns:
                    ser = parse_date_series(df[col])
                    if not ser.dropna().empty:
                        ref = ser.dropna().iloc[0]
                        break
        if ref is None or pd.isna(ref):
            if week:
                try:
                    today_iso = pd.Timestamp.today().isocalendar()
                    monday = datetime.fromisocalendar(int(today_iso.year), int(week), 1)
                    return [monday + pd.Timedelta(days=i) for i in range(7)]
                except Exception:
                    pass
            ref = pd.Timestamp.today()
        iso = ref.isocalendar()
        monday = datetime.fromisocalendar(int(iso.year), int(iso.week), 1)
        return [monday + pd.Timedelta(days=i) for i in range(7)]

    def _time_to_minutes(val: object) -> int | None:
        return hour_min_value(
            val,
            allow_general_fallback=True,
            strip_spaces=True,
            lowercase=True,
        )

    def _minutes_to_hhmm(m: int | None) -> str:
        if m is None:
            return ""
        h = int(m // 60)
        mi = int(m % 60)
        return f"{h:02d}h{mi:02d}"

    day_names = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    week_dates = _week_dates()
    day_labels = [f"{day_names[i]} {format_date_value(d, fmt='%d/%m', default='')}" for i, d in enumerate(week_dates)]

    # ---- Bloc bénévoles (disponibilités) ----
    with st.expander("👥 Disponibilités bénévoles (vue semaine)", expanded=False):
        if df_benev is None or df_benev.empty:
            st.info("Aucune disponibilité bénévole sur la période.")
        else:
            df_b = df_benev.copy()
            df_b["Date_dt"] = parse_date_series(df_b["Date"]).dt.date

            avail: dict[tuple[str, date], tuple[int, int]] = {}
            for _, r in df_b.iterrows():
                name = str(r.get("Nom", "")).strip()
                d = r.get("Date_dt")
                if not name or pd.isna(d):
                    continue
                arr = _time_to_minutes(r.get("Arrivée", ""))
                dep = _time_to_minutes(r.get("Départ", ""))
                if arr is None or dep is None:
                    continue
                key = (name, d)
                if key in avail:
                    prev_arr, prev_dep = avail[key]
                    arr = min(arr, prev_arr)
                    dep = max(dep, prev_dep)
                avail[key] = (arr, dep)

            names = sorted({str(n).strip() for n in df_b.get("Nom", pd.Series(dtype=object)).tolist() if str(n).strip()})
            if not names:
                st.info("Aucune disponibilité bénévole sur la période.")
            else:
                name_days: dict[str, set[date]] = {}
                for (n, d) in avail.keys():
                    if not n:
                        continue
                    name_days.setdefault(n, set()).add(d)
                name_counts = {n: len(days) for n, days in name_days.items()}
                name_display = {n: f"{n} ({name_counts.get(n, 0)})" for n in names}
                cols = pd.MultiIndex.from_product([day_labels, ["Début", "Fin"]])
                table = pd.DataFrame("", index=[name_display[n] for n in names], columns=cols)
                table.index.name = "Bénévole"
                mask = pd.DataFrame(False, index=[name_display[n] for n in names], columns=cols)
                for name in names:
                    for d, label in zip(week_dates, day_labels):
                        key = (name, d.date())
                        if key in avail:
                            arr, dep = avail[key]
                            row_name = name_display.get(name, name)
                            table.loc[row_name, (label, "Début")] = _minutes_to_hhmm(arr)
                            table.loc[row_name, (label, "Fin")] = _minutes_to_hhmm(dep)
                            mask.loc[row_name, (label, "Début")] = True
                            mask.loc[row_name, (label, "Fin")] = True

                def _style_mask(_):
                    green = "background-color: #d9f2d9;"
                    red = "background-color: #f7d6d6;"
                    return pd.DataFrame(
                        [[green if mask.iloc[i, j] else red for j in range(mask.shape[1])] for i in range(mask.shape[0])],
                        index=mask.index,
                        columns=mask.columns,
                    )

                header_styles = [
                    {"selector": "th.col_heading.level0", "props": [("text-align", "center")]},
                    {"selector": "th.col_heading.level1", "props": [("text-align", "center")]},
                ]

                styler = (
                    table.style.apply(_style_mask, axis=None)
                    .set_properties(**{"text-align": "center"})
                    .set_table_styles(header_styles, overwrite=False)
                )
                st.dataframe(styler, use_container_width=True)

    # ---- Bloc vols (disponibilités) ----
    with st.expander("✈️ Vols disponibles (vue semaine)", expanded=False):
        if df_flights is None or df_flights.empty:
            st.info("Aucun vol disponible sur la période.")
        else:
            df_v = df_flights.copy()
            df_v["Date_dt"] = parse_date_series(df_v["Date"]).dt.date

            def _vol_display(num: object) -> str:
                return format_vol_display(num) or str(num or "").strip()

            # Disponibilités bénévoles par date (en minutes)
            benev_by_date: dict[date, list[tuple[int, int]]] = {}
            if df_benev is not None and not df_benev.empty:
                tmp_b = df_benev.copy()
                tmp_b["Date_dt"] = parse_date_series(tmp_b["Date"]).dt.date
                for _, r in tmp_b.iterrows():
                    d = r.get("Date_dt")
                    if pd.isna(d):
                        continue
                    arr = _time_to_minutes(r.get("Arrivée", ""))
                    dep = _time_to_minutes(r.get("Départ", ""))
                    if arr is None or dep is None:
                        continue
                    benev_by_date.setdefault(d, []).append((arr, dep))

            def _is_compatible(d: date, minute_val: int | None) -> bool:
                if minute_val is None:
                    return False
                for s, e in benev_by_date.get(d, []):
                    if s <= minute_val <= e:
                        return True
                return False

            flights: dict[tuple[str, date], list[tuple[str, bool]]] = {}
            for _, r in df_v.iterrows():
                dest = str(r.get("Destination", "")).strip()
                d = r.get("Date_dt")
                if not dest or pd.isna(d):
                    continue
                heure = str(r.get("Heure", "")).strip()
                hmin = _time_to_minutes(heure)
                routing_raw = str(r.get("Routing", "")).strip().upper()
                routing_parts = [p for p in routing_raw.replace(" ", "").split("-") if p and p != "CDG"]
                routing = "-".join(routing_parts)
                vol = _vol_display(r.get("Numero_Vol", ""))
                parts = [p for p in [heure, vol, routing] if p]
                label = " - ".join(parts)
                key = (dest, d)
                compatible = _is_compatible(d, hmin)
                flights.setdefault(key, []).append((label, compatible))

            dests = sorted({str(d).strip() for d in df_v.get("Destination", pd.Series(dtype=object)).tolist() if str(d).strip()})
            if not dests:
                st.info("Aucun vol disponible sur la période.")
            else:
                colis_counts: dict[str, int] = {}
                if df_be is not None and not df_be.empty:
                    tmp_be = df_be.copy()
                    if "Destination" in tmp_be.columns:
                        tmp_be["Destination"] = tmp_be["Destination"].astype(str).str.strip()
                        tmp_be["Nb_Colis"] = pd.to_numeric(tmp_be.get("Nb_Colis", 0), errors="coerce").fillna(0).astype(int)
                        colis_counts = (
                            tmp_be.groupby("Destination")["Nb_Colis"].sum().astype(int).to_dict()
                        )
                dest_display = {d: f"{d} ({colis_counts.get(d, 0)})" for d in dests}

                table = pd.DataFrame("", index=[dest_display[d] for d in dests], columns=day_labels)
                table.index.name = "Escale"
                status = pd.DataFrame("none", index=[dest_display[d] for d in dests], columns=day_labels)
                for dest in dests:
                    for d, label in zip(week_dates, day_labels):
                        key = (dest, d.date())
                        if key in flights:
                            row_dest = dest_display.get(dest, dest)
                            items = flights[key]
                            table.loc[row_dest, label] = "\n".join([lab for lab, _ in items])
                            if any(ok for _, ok in items):
                                status.loc[row_dest, label] = "compatible"
                            else:
                                status.loc[row_dest, label] = "incompatible"

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
                        [[color_map.get(status.iloc[i, j], red) for j in range(status.shape[1])] for i in range(status.shape[0])],
                        index=status.index,
                        columns=status.columns,
                    )

                header_styles = [
                    {"selector": "th.col_heading", "props": [("text-align", "center"), ("font-size", "0.7em")]},
                    {"selector": "th.row_heading", "props": [("font-size", "0.7em")]},
                ]

                styler = (
                    table.style.apply(_style_mask_flights, axis=None)
                    .set_properties(**{"text-align": "left", "white-space": "pre-line", "font-size": "0.7em"})
                    .set_table_styles(header_styles, overwrite=False)
                )
                st.dataframe(styler, use_container_width=True)
