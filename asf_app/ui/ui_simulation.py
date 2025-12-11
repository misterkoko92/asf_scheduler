import streamlit as st
import pandas as pd

from asf_app.services.simulation_runner import run_ortools_simulation
from asf_app.state import get_state
from utils.datetime_utils import parse_date_series, parse_time_series, normalize_hour_str
from utils.ui_helpers import build_iata_city_maps, sort_planning_df, format_be_label, format_vol_label


def render_tab_simulation():
    # État global (dates de la semaine sélectionnée, chemins TMP, etc.)
    state = get_state()

    st.title("🧪 Simulation OR-Tools")
    st.markdown(
        """
Cet onglet lance un solveur OR-Tools expérimental **sans impacter le moteur principal**.
Il consomme les mêmes sources (MAG CENTRAL, VOLS, PLANNING BENEVOLES) et restitue un planning/bilan simulé.
        """
    )

    st.markdown("### Paramètres")
    col_timeout, col_verbose = st.columns([2, 1])
    with col_timeout:
        timeout = st.number_input("Temps maximum (secondes)", min_value=30, max_value=900, value=180, step=30)
    with col_verbose:
        verbose = st.checkbox("Log console détaillé", value=True)

    if "sim_result" not in st.session_state:
        st.session_state.sim_result = None

    if st.button("Lancer la simulation OR-Tools", type="primary"):
        with st.spinner("Optimisation OR-Tools en cours…"):
            st.session_state.sim_result = run_ortools_simulation(
                timeout_seconds=int(timeout),
                planifiables_only=True,
                verbose=verbose,
            )

    result = st.session_state.sim_result
    if not result:
        st.info("Aucune simulation lancée pour l'instant.")
        return

    stats = result.get("statistiques", {})
    st.markdown("### Résumé")
    resume_container = st.container()

    # Disponibilités bénévoles sur la semaine
    def _week_bounds():
        if state.api_start_date and state.api_end_date:
            return pd.to_datetime(state.api_start_date), pd.to_datetime(state.api_end_date)
        if result.get("planning_df") is not None and not result.get("planning_df").empty:
            dates = parse_date_series(result["planning_df"]["Date_Vol"]).dropna()
            if not dates.empty:
                return dates.min(), dates.max()
        return None, None

    start_dt, end_dt = _week_bounds()

    plan_df = result.get("planning_df")
    if plan_df is None or plan_df.empty:
        st.info("Aucun planning simulé à modifier.")
        return

    # Chargements nécessaires pour les statuts
    from loaders.load_shipments import load_shipments_df
    from loaders.load_vols import load_vols_df
    from loaders.load_benevoles import load_benevoles
    from loaders.load_params import get_param_dest, get_param_benev

    df_be = load_shipments_df(planifiables_only=True)
    df_vols_all = load_vols_df()
    df_dispo = load_benevoles()
    df_paramdest = get_param_dest()
    df_parambenev = get_param_benev()

    # Disponibilités bénévoles uniques sur la semaine
    def _compute_benev_dispo(df_dispo_src, s_dt, e_dt):
        try:
            dates_col = df_dispo_src.get("Date_dt", df_dispo_src.get("Date", ""))
            df_tmp = df_dispo_src.copy()
            df_tmp["_Date_dt"] = _parse_date_series(dates_col)
            mask_week = pd.Series(True, index=df_tmp.index)
            if s_dt is None or e_dt is None:
                dates_dispo = df_tmp["_Date_dt"].dropna()
                if not dates_dispo.empty:
                    s_dt = dates_dispo.min()
                    e_dt = dates_dispo.max()
            if s_dt is not None and e_dt is not None:
                mask_week = mask_week & (df_tmp["_Date_dt"] >= s_dt) & (df_tmp["_Date_dt"] <= e_dt)
            return int(df_tmp.loc[mask_week, "Benevole"].dropna().nunique()), s_dt, e_dt
        except Exception:
            return 0, s_dt, e_dt

    benev_dispo_total, start_dt, end_dt = _compute_benev_dispo(df_dispo, start_dt, end_dt)

    # Carte IATA -> Ville (pour afficher Destination en clair)
    dest_city_map, city_to_iata_map = build_iata_city_maps(df_paramdest)

    def _parse_date_series(series):
        # Première passe sur format attendu jj/mm/aa, fallback dayfirst
        ser = pd.to_datetime(series, format="%d/%m/%y", errors="coerce")
        mask_na = ser.isna()
        if mask_na.any():
            ser.loc[mask_na] = pd.to_datetime(series.loc[mask_na], errors="coerce", dayfirst=True)
        return ser

    def _parse_time_series(series):
        s_clean = series.astype(str).str.replace("h", ":", regex=False)
        return pd.to_datetime(s_clean, format="%H:%M", errors="coerce")

    if "_MANUEL" not in plan_df.columns:
        plan_df["_MANUEL"] = False
    # Garder une copie du planning initial pour les diffs export
    if "sim_original_df" not in st.session_state:
        st.session_state["sim_original_df"] = plan_df.copy()
    # Trie initial pour affichage cohérent
    plan_df = sort_planning_df(plan_df)
    # On conserve le tri dans le state pour l'affichage final
    st.session_state.sim_result["planning_df"] = plan_df

    # Style helper pour les lignes manuelles
    def _style_manual_df(df: pd.DataFrame):
        if df is None or df.empty:
            return df
        mask_manual = df["_MANUEL"] == True if "_MANUEL" in df.columns else pd.Series(False, index=df.index)  # noqa: E712
        df_display = df.drop(columns=["_MANUEL"], errors="ignore")
        def _apply(_df):
            styles = pd.DataFrame("", index=_df.index, columns=_df.columns)
            styles.loc[mask_manual[mask_manual].index] = "background-color: #f2f2f2"
            return styles
        return df_display.style.apply(_apply, axis=None)

    # -------------------------------
    # Bilans / détails (expand) avant édition
    # -------------------------------
    def _recompute_bilan(df_plan: pd.DataFrame) -> pd.DataFrame:
        if df_plan is None or df_plan.empty:
            return pd.DataFrame()
        cols = []
        for _, row in df_plan.iterrows():
            nb_colis = row.get("BE_Nb_Colis", row.get("BE_Nb_Colis_MAG", 0))
            nb_equiv = row.get("BE_Nb_Equiv", row.get("Equiv_Colis", 0))
            cols.append(
                {
                    "Date_Vol": row.get("Date_Vol", ""),
                    "Vol": row.get("Vol", row.get("Numero_Vol", "")),
                    "Destination": row.get("Destination", ""),
                    "BE_Numero": row.get("BE_Numero", ""),
                    "Nb_Colis": nb_colis if pd.notna(nb_colis) else 0,
                    "Nb_Equiv": nb_equiv if pd.notna(nb_equiv) else 0,
                    "Partant": "OUI",
                    "Raison": "MANUEL" if row.get("_MANUEL", False) else "OK",
                    "BE_Destinataire": row.get("BE_Destinataire", ""),
                    "_MANUEL": bool(row.get("_MANUEL", False)),
                }
            )
        return pd.DataFrame(cols)

    def _recompute_vols(df_plan: pd.DataFrame) -> pd.DataFrame:
        if df_plan is None or df_plan.empty:
            return pd.DataFrame()
        df = df_plan.copy()
        df["_MANUEL"] = df.get("_MANUEL", False)
        agg = (
            df.groupby(["Date_Vol", "Vol", "Destination"], as_index=False)
            .agg(
                {
                    "Heure_Vol": "first",
                    "BE_Numero": "count",
                    "Benevole": pd.Series.nunique,
                    "_MANUEL": "max",
                }
            )
            .rename(columns={"BE_Numero": "Nb_BE", "Benevole": "Nb_Benevoles"})
        )
        return agg

    def _recompute_benev(df_plan: pd.DataFrame) -> pd.DataFrame:
        if df_plan is None or df_plan.empty:
            return pd.DataFrame()
        rows = []
        for _, row in df_plan.iterrows():
            rows.append(
                {
                    "Benevole": row.get("Benevole", ""),
                    "Date_Vol": row.get("Date_Vol", ""),
                    "Heure_Vol": row.get("Heure_Vol", ""),
                    "Vol": row.get("Vol", row.get("Numero_Vol", "")),
                    "Destination": row.get("Destination", ""),
                    "BE_Numero": row.get("BE_Numero", ""),
                    "_MANUEL": bool(row.get("_MANUEL", False)),
                }
            )
        df = pd.DataFrame(rows)
        return df[df["Benevole"].astype(str).str.strip() != ""]

    def _recompute_dest_stats(df_plan: pd.DataFrame) -> pd.DataFrame:
        if df_plan is None or df_plan.empty:
            return pd.DataFrame()
        df = df_plan.copy()
        df["_MANUEL"] = df.get("_MANUEL", False)
        agg = (
            df.groupby("Destination", as_index=False)
            .agg(
                {
                    "BE_Numero": "count",
                    "BE_Nb_Colis": "sum",
                    "BE_Nb_Equiv": "sum",
                    "_MANUEL": "max",
                }
            )
            .rename(columns={"BE_Numero": "Nb_BE", "BE_Nb_Colis": "Nb_Colis", "BE_Nb_Equiv": "Nb_Equiv"})
        )
        return agg

    def _recompute_be_non_planifies(df_plan: pd.DataFrame, df_be_src: pd.DataFrame) -> pd.DataFrame:
        if df_be_src is None or df_be_src.empty:
            return pd.DataFrame()
        planned = set(df_plan["BE_Numero"].astype(str)) if df_plan is not None and not df_plan.empty else set()
        df_src = df_be_src.copy()
        df_src["BE_Numero_str"] = df_src["BE_Numero"].astype(str)
        return df_src[~df_src["BE_Numero_str"].isin(planned)]

    def _recompute_bilan_benevoles(df_plan: pd.DataFrame, df_dispo_src: pd.DataFrame) -> pd.DataFrame:
        """
        - Nombre de disponibilités (0..7) sur la semaine
        - Nombre de jours affectés (unique dates)
        - Nombre de vols affectés
        - Nombre de BE affectés
        """
        if df_plan is None and df_dispo_src is None:
            return pd.DataFrame()

        # Disponibilités par bénévole (filtrées sur la semaine)
        dispo_counts = {}
        try:
            dates_col = df_dispo_src.get("Date_dt", df_dispo_src.get("Date", ""))
            df_tmp = df_dispo_src.copy()
            df_tmp["_Date_dt"] = parse_date_series(dates_col)
            mask_week = pd.Series(True, index=df_tmp.index)
            if start_dt is not None and end_dt is not None:
                mask_week = mask_week & (df_tmp["_Date_dt"] >= start_dt) & (df_tmp["_Date_dt"] <= end_dt)
            df_tmp = df_tmp[mask_week]
            dispo_counts = df_tmp.groupby("Benevole")["_Date_dt"].nunique().to_dict()
        except Exception:
            dispo_counts = {}

        # Affectations
        rows = []
        df_plan_local = pd.DataFrame()
        if df_plan is not None and not df_plan.empty:
            df_plan_local = df_plan.copy()
            df_plan_local["_Date_dt"] = parse_date_series(df_plan_local.get("Date_Vol", ""))

        benevole_set = set(dispo_counts.keys())
        benevole_set.update(df_plan_local.get("Benevole", []).dropna().unique() if not df_plan_local.empty else [])

        for bene in benevole_set:
            if str(bene).strip() == "":
                continue
            nb_dispo = int(dispo_counts.get(bene, 0))
            if not df_plan_local.empty:
                grp = df_plan_local[df_plan_local["Benevole"] == bene]
                nb_jours = int(grp["_Date_dt"].dt.date.nunique())
                nb_vols = int(len(grp))
                nb_be = int(grp["BE_Numero"].nunique())
                manual_flag = bool(grp.get("_MANUEL", False).any())
            else:
                nb_jours = 0
                nb_vols = 0
                nb_be = 0
                manual_flag = False
            rows.append(
                {
                    "Benevole": bene,
                    "Nb_Dispos": nb_dispo,
                    "Nb_Jours_Affectes": nb_jours,
                    "Nb_Vols_Affectes": nb_vols,
                    "Nb_BE_Affectes": nb_be,
                    "_MANUEL": manual_flag,
                }
            )
        return pd.DataFrame(rows)

    def _compute_resume_numbers(df_plan: pd.DataFrame):
        nb_be_total = df_be["BE_Numero"].nunique() if df_be is not None and not df_be.empty else 0
        nb_be_envoyes = df_plan["BE_Numero"].nunique() if df_plan is not None and not df_plan.empty else 0
        nb_vols = 0
        if df_plan is not None and not df_plan.empty:
            nb_vols = len(df_plan[["Date_Vol", "Vol"]].drop_duplicates())

        def _col_sum(df_src):
            if df_src is None or df_src.empty:
                return 0
            vals = []
            for _, r in df_src.iterrows():
                for key in ["BE_Nb_Colis", "BE_Nb_Colis_MAG", "Nb_Colis"]:
                    v = r.get(key, 0)
                    if pd.notna(v):
                        vals.append(float(v))
                        break
                    vals.append(0)
            return round(sum(vals))

        nb_colis_total = _col_sum(df_be)
        nb_colis_expedies = _col_sum(df_plan)

        benev_used = 0
        if df_plan is not None and not df_plan.empty and "Benevole" in df_plan.columns:
            benev_used = df_plan["Benevole"].dropna().astype(str).str.strip().replace("", pd.NA).dropna().nunique()

        benev_dispo = benev_dispo_total
        taux_colis = round(nb_colis_expedies / nb_colis_total * 100, 1) if nb_colis_total else 0

        status_label = stats.get("status", "N/A")
        if df_plan is not None and not df_plan.empty and df_plan.get("_MANUEL", pd.Series(dtype=bool)).any():
            status_label = f"{status_label} (ajusté)"

        return {
            "status": status_label,
            "nb_be_envoyes": nb_be_envoyes,
            "nb_be_total": nb_be_total,
            "nb_vols": nb_vols,
            "nb_colis_expedies": nb_colis_expedies,
            "nb_colis_total": nb_colis_total,
            "taux_colis": taux_colis,
            "benev_used": benev_used,
            "benev_dispo": benev_dispo,
        }

    def _recompute_all_tables(df_plan: pd.DataFrame):
        return (
            _recompute_bilan(df_plan),
            _recompute_vols(df_plan),
            _recompute_benev(df_plan),
            _recompute_dest_stats(df_plan),
            _recompute_be_non_planifies(df_plan, df_be),
            _recompute_bilan_benevoles(df_plan, df_dispo),
        )

    # Helper export Excel (reprend la logique onglet Planning)
    def _compute_week_year(df_plan: pd.DataFrame):
        if state.current_week and state.current_year:
            return state.current_week, state.current_year
        if df_plan is not None and not df_plan.empty:
            first_date = pd.to_datetime(df_plan["Date_Vol"], errors="coerce", dayfirst=True).dropna()
            if not first_date.empty:
                iso = first_date.iloc[0].isocalendar()
                return int(iso.week), int(iso.year)
        # Fallback : semaine courante
        today_iso = pd.Timestamp.today().isocalendar()
        return int(today_iso.week), int(today_iso.year)

    def _clean_for_excel(df: pd.DataFrame | None) -> pd.DataFrame | None:
        if df is None or getattr(df, "empty", True):
            return df
        clean = df.copy()
        clean = clean.astype(object)
        clean = clean.where(pd.notna(clean), None)
        return clean

    def _build_export_with_diff(current_plan: pd.DataFrame, original_plan: pd.DataFrame | None) -> pd.DataFrame:
        cur = pd.DataFrame(current_plan).copy()
        cur["_STATUS"] = "normal"
        if original_plan is None or getattr(original_plan, "empty", True):
            # Tout est considéré comme nouveau si aucune base
            cur["_STATUS"] = "new"
            return cur
        orig = pd.DataFrame(original_plan).copy()
        orig["_STATUS"] = "orig"
        # Normaliser clé BE
        def _key(df):
            return df["BE_Numero"].astype(str).str.strip()
        cur["__KEY"] = _key(cur)
        orig["__KEY"] = _key(orig)
        orig_by_key = {k: r for k, r in orig.groupby("__KEY")}
        rows = []
        # Détections
        for _, row in cur.iterrows():
            key = row["__KEY"]
            if key not in orig_by_key:
                row["_STATUS"] = "new"
                rows.append(row)
            else:
                # comparer valeurs principales
                ref = orig_by_key[key].iloc[0]
                cols_cmp = ["Date_Vol", "Heure_Vol", "Vol", "Destination", "Benevole"]
                changed = any(str(row.get(c, "")) != str(ref.get(c, "")) for c in cols_cmp)
                if changed:
                    # ancienne version
                    ref_old = ref.copy()
                    ref_old["_STATUS"] = "old"
                    rows.append(ref_old)
                    row["_STATUS"] = "new"
                    rows.append(row)
                else:
                    row["_STATUS"] = "normal"
                    rows.append(row)
        # BE supprimés
        keys_cur = set(cur["__KEY"])
        for _, ref in orig.iterrows():
            if ref["__KEY"] not in keys_cur:
                ref_old = ref.copy()
                ref_old["_STATUS"] = "old_deleted"
                rows.append(ref_old)
        df_out = pd.DataFrame(rows).drop(columns=["__KEY"], errors="ignore")
        return df_out

    def _export_simulation_excel():
        from asf_app.ui.ui_planning.ui_planning import export_excel_planning
        current_plan = st.session_state.sim_result.get("planning_df", plan_df)
        original_plan = st.session_state.get("sim_original_df")
        # Export sans traçage des anciennes lignes : on prend uniquement le planning courant
        df_with_status = sort_planning_df(current_plan)
        week, year = _compute_week_year(current_plan)
        df_export = pd.DataFrame(df_with_status).copy()
        df_export = df_export.drop(columns=["_MANUEL", "_STATUS"], errors="ignore")
        # Colonnes attendues par l'export principal
        required_cols = [
            "Ville",
            "Dest_Ville",
            "Destination",  # sera l'IATA pour alimenter la colonne IATA de l'export
            "Heure_Vol",
            "Vol",
            "Numero_Vol",
            "BE_Numero",
            "BE_Nb_Colis",
            "BE_Type",
            "BE_Expediteur",
            "BE_Destinataire",
            "Routing",
            "Date_Vol",
        ]
        for col in required_cols:
            if col not in df_export.columns:
                df_export[col] = ""
        # Assurer la colonne Destinataire
        if "BE_Destinataire" not in df_export.columns:
            df_export["BE_Destinataire"] = ""

        # Enrichir avec les infos vols (Routing, IATA, Numero_Vol) via jointure
        vols_enrich = df_vols_all.copy()
        def _norm_vol(val: str) -> str:
            s = str(val).strip().upper()
            s = s.replace("AF ", "AF").replace("  ", " ")
            s = s.replace("AF", "AF ").strip() if s.startswith("AF") else s
            return s
        vols_enrich["Date_key"] = pd.to_datetime(vols_enrich["Date_Vol"], errors="coerce", dayfirst=True).dt.date
        vols_enrich["Vol_key"] = vols_enrich["Numero_Vol"].apply(_norm_vol) if "Numero_Vol" in vols_enrich.columns else ""

        df_export["Date_key"] = pd.to_datetime(df_export["Date_Vol"], errors="coerce", dayfirst=True).dt.date
        df_export["Vol_key"] = df_export.get("Vol", df_export.get("Numero_Vol", "")).apply(_norm_vol)

        df_export = df_export.merge(
            vols_enrich[["Date_key", "Vol_key", "Routing", "IATA", "Numero_Vol", "Destination"]],
            on=["Date_key", "Vol_key"],
            how="left",
            suffixes=("", "_VOL"),
        )

        # Colonnes finales : Ville (ville), Destination (IATA), Routing, Numero_Vol
        def _city_for(row):
            # privilégier Dest_Ville si déjà là, sinon mapping IATA->ville
            existing = str(row.get("Dest_Ville", "") or row.get("Ville", "")).strip()
            if existing:
                return existing
            iata_val = str(row.get("IATA_VOL", "") or row.get("Dest_IATA", "") or row.get("IATA", "")).strip().upper()
            return dest_city_map.get(iata_val, iata_val)

        df_export["Dest_Ville"] = df_export.apply(_city_for, axis=1)
        df_export["Ville"] = df_export["Dest_Ville"]

        def _iata_for(row):
            val = str(row.get("IATA_VOL", "") or row.get("IATA", "") or row.get("Dest_IATA", "")).strip().upper()
            if not val:
                val = city_to_iata_map.get(str(row.get("Dest_Ville", "")).strip().upper(), "")
            return val

        df_export["IATA"] = df_export.apply(_iata_for, axis=1)
        df_export["Dest_IATA"] = df_export["IATA"]
        df_export["Destination"] = df_export["IATA"]  # utilisé par l'export pour alimenter la col IATA
        df_export["Routing"] = df_export.get("Routing_VOL", df_export.get("Routing", ""))
        df_export["Numero_Vol"] = df_export.get("Numero_Vol_VOL", df_export.get("Vol", df_export.get("Numero_Vol", "")))

        # Dates/heures en datetime pour éviter NaT -> Planning vide
        df_export["Date_Vol"] = _parse_date_series(df_export["Date_Vol"])
        df_export["Heure_Vol"] = parse_time_series(df_export["Heure_Vol"]).dt.strftime("%H:%M")
        # Tri Date/Heure avant export pour alimenter la feuille Planning dans l'ordre
        try:
            df_export = df_export.sort_values(by=["Date_Vol", "Heure_Vol"], kind="mergesort").reset_index(drop=True)
        except Exception:
            pass
        # Nettoyage valeurs Excel (pas de NA/NaT)
        df_export = _clean_for_excel(df_export)
        # Filtrer les vols à la période du planning (si bornes dispo)
        vols_filtered = df_vols_all.copy()
        try:
            start_dt = pd.to_datetime(state.api_start_date) if state.api_start_date else None
            end_dt = pd.to_datetime(state.api_end_date) if state.api_end_date else None
            if start_dt is None or end_dt is None:
                if df_export is not None and not df_export.empty:
                    dates_plan = pd.to_datetime(df_export["Date_Vol"], errors="coerce", dayfirst=True).dropna()
                    if not dates_plan.empty:
                        start_dt = dates_plan.min()
                        end_dt = dates_plan.max()
            if start_dt is not None and end_dt is not None and "Date_Vol" in vols_filtered.columns:
                vols_filtered["Date_dt"] = _parse_date_series(vols_filtered["Date_Vol"])
                vols_filtered = vols_filtered[(vols_filtered["Date_dt"] >= start_dt) & (vols_filtered["Date_dt"] <= end_dt)]
                vols_filtered = vols_filtered.drop(columns=["Date_dt"], errors="ignore")
        except Exception:
            pass
        vols_clean = _clean_for_excel(vols_filtered)
        dispo_clean = _clean_for_excel(df_dispo)
        out_path = export_excel_planning(
            df_export,
            week,
            year,
            df_vols=vols_clean,
            df_parambenev=df_parambenev,
            df_dispos=dispo_clean,
        )
        return out_path

    # ------------------------------------------------------------------
    # Edition manuelle du planning de simulation (sélecteurs alignés onglet Planning)
    # ------------------------------------------------------------------
    st.markdown("### ✏️ Ajuster le planning simulé")

    # --- Helpers ---
    def _fmt_be_label(row, planned_set):
        dest = str(row.get("Destination", "")).upper()
        be_num = str(row.get("BE_Numero", ""))
        nb_colis = row.get("BE_Nb_Colis", row.get("BE_Nb_Colis_MAG", ""))
        nb_colis = int(nb_colis) if pd.notna(nb_colis) else ""
        type_colis = str(row.get("BE_Type", "")).upper()
        status = "déjà au planning" if be_num in planned_set else "non planifié"
        date_str = str(row.get("Date_Vol", "") or "")
        return format_be_label(dest, be_num, nb_colis, type_colis, status, date_str)

    def _time_from_str(val):
        import datetime as dt
        if val in (None, "", pd.NA):
            return None
        if isinstance(val, dt.time):
            return val
        try:
            sval = str(val).replace("h", ":")
            return pd.to_datetime(sval, errors="coerce").time()
        except Exception:
            return None

    # BE options
    planned_set = set(plan_df["BE_Numero"].astype(str))
    be_options = []
    for _, r in df_be.iterrows():
        be_options.append(
            (
                str(r.get("Destination", "")).upper(),
                str(r.get("BE_Numero", "")),
                _fmt_be_label(r, planned_set),
                r,
            )
        )
    be_options = sorted(be_options, key=lambda x: (x[0], x[1]))
    if not be_options:
        st.warning("Aucun BE statut D chargé.")
        return
    be_labels = [b[2] for b in be_options]
    be_values = [b[1] for b in be_options]
    selected_idx = 0
    selected_be_label = st.selectbox("Sélectionner un BE", options=be_labels, index=selected_idx)
    idx_sel = be_labels.index(selected_be_label)
    be_num = be_values[idx_sel]
    be_row = be_options[idx_sel][3]
    # Ligne planifiée existante si déjà au planning
    planned_row = plan_df[plan_df["BE_Numero"].astype(str) == str(be_num)]
    planned_row = planned_row.iloc[0] if not planned_row.empty else None

    # Vols filtrés par destination du BE
    code_iata_be = str(be_row.get("Destination", "")).strip().upper()
    df_vols = df_vols_all.copy()
    # Filtrer les vols sur la semaine du planning si dates connues
    try:
        if state.api_start_date and state.api_end_date:
            start_dt = pd.to_datetime(state.api_start_date)
            end_dt = pd.to_datetime(state.api_end_date)
            df_vols["Date_dt"] = _parse_date_series(df_vols["Date_Vol"])
            df_vols = df_vols[(df_vols["Date_dt"] >= start_dt) & (df_vols["Date_dt"] <= end_dt)]
    except Exception:
        pass
    df_vols["Dest_UP"] = df_vols["IATA"].astype(str).str.upper()
    mask_dest = df_vols["Dest_UP"].str.contains(code_iata_be, na=False)
    df_vols_filt = df_vols[mask_dest] if mask_dest.any() else df_vols

    # Statut vol (déjà utilisé dans planning simulé)
    vol_options = []
    for _, r in df_vols_filt.iterrows():
        vol_num = r.get("Numero_Vol", "")
        date_raw = r.get("Date_Vol", "")
        heure_raw = r.get("Heure_Vol", "")
        already = (
            (plan_df.get("Vol", plan_df.get("Numero_Vol", "")).astype(str) == str(vol_num))
            & (plan_df.get("Date_Vol", "").astype(str) == str(date_raw))
        ).any()
        status = "déjà utilisé" if already else "disponible"
        date_dt = None
        try:
            date_dt = parse_date_series(pd.Series([date_raw])).iloc[0]
        except Exception:
            pass
        routing_lbl = str(r.get("Routing", "")) or ""
        label = format_vol_label(date_dt if date_dt is not None else date_raw, str(r.get("IATA", "")).upper(), vol_num, heure_raw, routing_lbl, status)
        vol_options.append((label, (date_raw, vol_num, heure_raw)))
    if not vol_options:
        vol_options = [("Aucun vol pour cette destination", ("", "", ""))]
    vol_labels = [v[0] for v in vol_options]
    vol_values = [v[1] for v in vol_options]
    # Pré-sélection si BE déjà planifié
    sel_vol_idx = 0
    if planned_row is not None:
        planned_date = str(planned_row.get("Date_Vol", ""))
        planned_vol = str(planned_row.get("Vol", planned_row.get("Numero_Vol", "")))
        for i, (d, vnum, _) in enumerate(vol_values):
            if str(d) == planned_date and str(vnum) == planned_vol:
                sel_vol_idx = i
                break
    else:
        # Ajoute un message explicite si BE non planifié
        message = "BE absent du planning, pour l'ajouter choisissez un vol et un bénévole"
        vol_labels = [message] + vol_labels
        vol_values = [("", "", "")] + vol_values
        sel_vol_idx = 0
    chosen_vol_label = st.selectbox("Sélectionner un vol", options=vol_labels, index=sel_vol_idx)
    date_choice, vol_choice_val, heure_choice = vol_values[vol_labels.index(chosen_vol_label)]

    # Bénévoles : statut dispo/occupé/inconnu
    bene_options = []
    benev_existing = plan_df.copy()
    for _, r in df_parambenev.iterrows():
        name = str(r.get("Benevole", "")).strip()
        bene_options.append(name)
    bene_options = sorted(set(bene_options))

    def _bene_status(name):
        # Occupé si déjà affecté sur ce vol/date
        already = (
            (benev_existing.get("Benevole", "").astype(str) == name)
            & (benev_existing.get("Vol", benev_existing.get("Numero_Vol", "")).astype(str) == str(vol_choice_val))
            & (benev_existing.get("Date_Vol", "").astype(str) == str(date_choice))
        ).any()
        if already:
            return "Occupé"

        # Disponibilité
        try:
            d = pd.to_datetime(date_choice, dayfirst=True, errors="coerce").date()
            t = _time_from_str(heure_choice)
        except Exception:
            return "Inconnu"
        rows = df_dispo
        if "Date_dt" in df_dispo.columns:
            try:
                dates_dt = _parse_date_series(df_dispo["Date_dt"])
                rows = df_dispo[dates_dt.dt.date == d]
            except Exception:
                rows = df_dispo
        rows = rows[rows["Benevole"].astype(str) == name]
        if rows.empty:
            return "Inconnu"
        ok = False
        for _, row in rows.iterrows():
            arr = row.get("Heure_Arrivee_time") or row.get("Heure_Arrivee_time")
            dep = row.get("Heure_Depart_time") or row.get("Heure_Depart_time")
            arr = arr if isinstance(arr, type(t)) else _time_from_str(arr)
            dep = dep if isinstance(dep, type(t)) else _time_from_str(dep)
            if arr and dep and t:
                if arr <= t <= dep:
                    ok = True
                    break
        return "Disponible" if ok else "Occupé"

    bene_labels = []
    for name in bene_options:
        bene_labels.append(f"{name} — {_bene_status(name)}")
    bene_values = bene_options
    # Ajout message si non planifié
    if planned_row is None:
        message = "BE absent du planning, pour l'ajouter choisissez un vol et un bénévole"
        bene_labels = [message] + bene_labels
        bene_values = [""] + bene_values
    # Pré-sélection si planifié
    sel_bene_idx = 0
    if planned_row is not None:
        planned_bene = str(planned_row.get("Benevole", "")).strip()
        for i, name in enumerate(bene_values):
            if str(name).strip() == planned_bene:
                sel_bene_idx = i
                break
    chosen_bene_label = st.selectbox("Affecter un bénévole", options=bene_labels or [""], index=sel_bene_idx)
    benev_val = bene_values[bene_labels.index(chosen_bene_label)] if bene_labels else ""

    # Actions
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        if st.button("Ajouter / Mettre à jour", type="primary"):
            df_new = plan_df.copy()
            mask = df_new["BE_Numero"].astype(str) == str(be_num)
            bene_row = df_parambenev[df_parambenev["Benevole"].astype(str) == str(benev_val)]
            bene_id = bene_row["ID"].iloc[0] if not bene_row.empty else ""
            bene_tel = bene_row["Telephone"].iloc[0] if not bene_row.empty else ""
            dest_city = dest_city_map.get(code_iata_be, str(be_row.get("Destination", "")))
            row_data = {
                "BE_Numero": be_num,
                "Destination": dest_city,
                "Date_Vol": date_choice,
                "Heure_Vol": heure_choice,
                "Vol": vol_choice_val,
                "BE_Nb_Colis": be_row.get("BE_Nb_Colis", ""),
                "BE_Nb_Equiv": be_row.get("Equiv_Colis", be_row.get("BE_Nb_Equiv", "")),
                "BE_Expediteur": be_row.get("BE_Expediteur", ""),
                "BE_Destinataire": be_row.get("BE_Destinataire", ""),
                "BE_Type": be_row.get("BE_Type", ""),
                "Benevole": benev_val,
                "ID": bene_id,
                "Telephone": bene_tel,
                "_MANUEL": True,
            }
            if mask.any():
                df_new.loc[mask, row_data.keys()] = list(row_data.values())
            else:
                df_new = pd.concat([df_new, pd.DataFrame([row_data])], ignore_index=True)
            st.session_state.sim_result["planning_df"] = _sort_planning(df_new)
            st.success("Planning simulation mis à jour.")
    with col_d2:
        if st.button("Supprimer l'expédition sélectionnée", type="secondary"):
            df_new = plan_df[plan_df["BE_Numero"].astype(str) != str(be_num)].copy()
            st.session_state.sim_result["planning_df"] = _sort_planning(df_new)
            st.success("Expédition supprimée du planning simulé.")

    # Re-trier et recalculer tous les tableaux dès cette passe pour éviter le décalage d'une interaction
    plan_df = _sort_planning(st.session_state.sim_result["planning_df"])
    st.session_state.sim_result["planning_df"] = plan_df

    (
        bilan_df,
        vols_df,
        benev_df,
        dest_stats,
        be_non_planifies,
        bilan_benevoles,
    ) = _recompute_all_tables(plan_df)

    # Mettre à jour le bloc résumé avec les données recalculées
    resume_vals = _compute_resume_numbers(plan_df)
    with resume_container:
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Statut", resume_vals["status"])
        c2.metric("BE planifiés", f"{resume_vals['nb_be_envoyes']} / {resume_vals['nb_be_total']}")
        c3.metric("Vols utilisés", resume_vals["nb_vols"])
        c4.metric("Bénévoles mobilisés", f"{resume_vals['benev_used']} / {resume_vals['benev_dispo']}")
        c5.metric(
            "Colis expédiés",
            f"{resume_vals['nb_colis_expedies']} / {resume_vals['nb_colis_total']}",
            f"{resume_vals['taux_colis']}%",
        )

    # Export Excel (bouton sous le tableau de planning)
    def _open_file(path_obj):
        import subprocess, os, platform
        if path_obj is None:
            return
        try:
            if platform.system() == "Darwin":
                subprocess.Popen(["open", str(path_obj)])
            elif platform.system() == "Windows":
                os.startfile(str(path_obj))  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", str(path_obj)])
        except Exception:
            pass

    if st.button("📤 Exporter le planning simulé (Excel)", type="primary"):
        try:
            out_path = _export_simulation_excel()
            st.success(f"Planning simulé exporté : {out_path.name}")
            _open_file(out_path)
            # Export PDF 1ère feuille + ouvrir le PDF
            try:
                from utils.export_pdf import export_first_sheet_to_pdf
                pdf_path = export_first_sheet_to_pdf(out_path)
                _open_file(pdf_path)
            except Exception as e_pdf:
                st.warning(f"PDF non généré automatiquement : {e_pdf}")
        except Exception as e:
            st.error(f"Erreur lors de l'export : {e}")

    st.dataframe(_style_manual_df(plan_df), height=400, width="stretch", hide_index=True)

    with st.expander("Bilans détaillés (simulation)", expanded=False):
        st.markdown("**Bilan des expéditions**")
        st.dataframe(_style_manual_df(bilan_df), width="stretch", hide_index=True)

        st.markdown("**Bilan des vols**")
        st.dataframe(_style_manual_df(vols_df), width="stretch", hide_index=True)

        st.markdown("**Bilan par destination**")
        st.dataframe(_style_manual_df(dest_stats), width="stretch", hide_index=True)

        st.markdown("**Planning bénévoles**")
        st.dataframe(_style_manual_df(benev_df), width="stretch", hide_index=True)

        st.markdown("**BE non planifiés**")
        st.dataframe(be_non_planifies, width="stretch", hide_index=True)

        st.markdown("**Bilan des bénévoles**")
        st.dataframe(_style_manual_df(bilan_benevoles), width="stretch", hide_index=True)
