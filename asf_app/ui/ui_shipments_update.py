# -*- coding: utf-8 -*-
"""
Onglet : Mise à Jour expéditions
Permet d'annuler ou de reprogrammer un BE déjà planifié (statut P) et
de préparer les brouillons Outlook associés.
"""

from typing import Optional, Tuple, List
from pathlib import Path

import pandas as pd
import streamlit as st

from asf_app.ui.loader import load_parameters
from asf_app.ui.ui_planning.state_planning import get_planning_state
from asf_app.ui.ui_communication.email_destinations_handler import _get_emails_for_destination
from asf_app.ui.ui_communication.email_expediteurs_handler import _get_emails_for_expediteur
from asf_app.ui.ui_communication.outlook import create_outlook_draft
from loaders.load_benevoles import get_benevoles_cached
from loaders.load_vols import get_vols_df_cached
from asf_app.state import get_state, get_excel_source_paths
from asf_app.config.runtime import get_tableau_de_bord_src
from utils.ui_helpers import build_iata_city_maps
from utils.export_pdf import export_first_sheet_to_pdf
from scheduler.planning_schema import normalize_planning_df
from asf_app.ui.ui_shipments_update_helpers import (
    _norm_be,
    _fmt_date_long,
    _fmt_time,
    _fmt_vol,
    _build_action_sentence,
    _build_default_vol_tuple,
    _build_vol_selection_data,
    _resolve_selected_vol,
    _build_bene_options,
    _build_default_bene_label,
    _extract_bene_choice,
    _fill_bene_name_from_parambenev,
    _prepare_dispo,
    _bene_status,
    _collect_be_from_planning,
    _find_row_in_df,
    _weeks_from_status_df,
    _build_week_selector_data,
    _build_planning_version_choices,
    _format_preview_dataframe,
    _load_export_planning_sheet,
    _select_source_for_be,
    _prepare_queue_apply,
    _build_duplicate_be_warning,
    _run_queue_apply_batch,
    _should_show_mag_central_cleanup_info,
    _collect_benevole_emails,
    _notification_period_from_payloads,
    _build_asf_notification_draft,
    _build_destination_notification_drafts,
    _build_expediteur_notification_drafts,
    _add_queue_item,
    _clear_queue_state,
    _build_queue_dataframe,
    _build_queue_labels,
    _pop_prefill_values,
    _build_queue_item,
    _dest_to_iata,
    _build_planif_be_options,
    _prepare_be_lookup,
    _format_be_option_label,
    _build_bene_meta,
)
from asf_app.services.shipments_update_service import (
    load_be_status,
    load_be_status_d_for_week,
    apply_planning_updates_batch,
)
from asf_app.services.planning_exports_service import (
    available_weeks_from_exports,
    parse_version_from_name,
    find_planning_files_for_week,
    load_planning_preview_with_path,
)


# ---------------------------------------------------------------------------
# Chargement BE statut P
# ---------------------------------------------------------------------------
def _load_be_status(status_code: str, *, tdb_path: Path | None = None) -> pd.DataFrame:
    return load_be_status(status_code, tdb_path=tdb_path)

def _load_be_status_d_for_week(week: int, year: int, *, tdb_path: Path | None = None) -> pd.DataFrame:
    return load_be_status_d_for_week(week, year, tdb_path=tdb_path)

def _load_planning_preview_with_path(
    week: int, year: int, path_override: Optional[Path | str]
) -> tuple[pd.DataFrame | None, str, Path | None]:
    """
    Variante : accepte un chemin explicite si déjà sélectionné.
    """
    return load_planning_preview_with_path(week, year, path_override)

def _available_weeks_from_exports() -> set[tuple[int, int]]:
    return available_weeks_from_exports()

def _parse_version_from_name(path: Path) -> tuple[int, int]:
    return parse_version_from_name(path)

def _find_planning_files_for_week(week: int, year: int) -> List[Path | str]:
    return find_planning_files_for_week(week, year)

def _match_planning_row(df_planning: pd.DataFrame, be_value: str) -> Optional[pd.Series]:
    if df_planning is None or df_planning.empty:
        return None

    be_col_planning = None
    for cand in ["BE_Numero", "BE NUMERO", "BE_NUMERO", "BE_Num", "BE_numero"]:
        if cand in df_planning.columns:
            be_col_planning = cand
            break
    if be_col_planning is None:
        return None

    be_norm = _norm_be(be_value)
    df_tmp = df_planning.copy()
    df_tmp["_BE_KEY"] = df_tmp[be_col_planning].apply(_norm_be)

    rows = df_tmp[df_tmp["_BE_KEY"] == be_norm]
    if rows.empty:
        # tenter sur suffixe 3 chiffres
        short = be_norm[-3:] if len(be_norm) >= 3 else be_norm
        rows = df_tmp[df_tmp["_BE_KEY"].str.endswith(short, na=False)]
    if rows.empty:
        return None
    return rows.iloc[0]


# ---------------------------------------------------------------------------
# Vols disponibles pour une destination
# ---------------------------------------------------------------------------
def _build_vol_options(dest_iata: str, df_vols: pd.DataFrame, df_planning: pd.DataFrame) -> list[Tuple[str, Tuple[str, str, str]]]:
    if df_vols is None:
        df_vols = pd.DataFrame()
    try:
        vol_source = df_vols.copy()
    except Exception:
        vol_source = pd.DataFrame()

    if vol_source.empty:
        return []

    vol_source = vol_source.copy()
    if "Dest_IATA" not in vol_source.columns:
        vol_source["Dest_IATA"] = vol_source.get("Destination", "")
    if "Routing" not in vol_source.columns:
        vol_source["Routing"] = vol_source.get("Routing_Str", "")
    if "Date_Vol" not in vol_source.columns:
        vol_source["Date_Vol"] = vol_source.get("Date", "")
    if "Numero_Vol" not in vol_source.columns:
        vol_source["Numero_Vol"] = vol_source.get("Vol", vol_source.get("Numero_Vol", ""))
    if "Heure_Vol" not in vol_source.columns:
        vol_source["Heure_Vol"] = vol_source.get("Heure", "")

    vol_source["Routing_Str"] = vol_source["Routing"].astype(str)
    vol_source["Dest_IATA_UP"] = vol_source["Dest_IATA"].astype(str).str.upper()

    vol_filtered = pd.DataFrame(columns=vol_source.columns)
    if dest_iata:
        mask_dest = vol_source["Dest_IATA_UP"].str.contains(dest_iata, na=False) | vol_source["Routing_Str"].str.upper().str.contains(dest_iata, na=False)
        vol_filtered = vol_source[mask_dest]
        if vol_filtered.empty:
            vol_filtered = vol_source

    if vol_filtered.empty and df_planning is not None and not df_planning.empty:
        df_plan_vols = df_planning.copy()
        df_plan_vols["Destination_UP"] = df_plan_vols.get("Destination", "").astype(str).str.upper()
        df_plan_vols = df_plan_vols[df_plan_vols["Destination_UP"].str.contains(dest_iata, na=False)]
        if not df_plan_vols.empty:
            df_plan_vols = df_plan_vols.rename(columns={"Vol": "Numero_Vol"})
            df_plan_vols["Routing_Str"] = df_plan_vols.get("Routing", "")
            vol_filtered = df_plan_vols

    vols_unique = (
        vol_filtered[["Date_Vol", "Numero_Vol", "Heure_Vol", "Routing_Str"]]
        .dropna(how="all")
        .drop_duplicates()
        .sort_values(by=["Date_Vol", "Heure_Vol"])
    ) if not vol_filtered.empty else pd.DataFrame(columns=["Date_Vol", "Numero_Vol", "Heure_Vol", "Routing_Str"])

    options: list[Tuple[str, Tuple[str, str, str]]] = []
    for _, r in vols_unique.iterrows():
        vol_num_raw = r.get("Numero_Vol", "")
        date_raw = r.get("Date_Vol", "")
        heure_raw = r.get("Heure_Vol", "")
        if (str(vol_num_raw).strip() == "") and (str(date_raw).strip() == ""):
            continue
        label = f"{_fmt_date_long(date_raw)} — {_fmt_vol(vol_num_raw)} — {_fmt_time(heure_raw)}"
        value = (str(date_raw), str(vol_num_raw), str(heure_raw))
        options.append((label, value))

    return options


def render_tab_shipments_update():
    st.title("🚚 Mise à Jour expéditions")

    state = get_state()
    paths = get_excel_source_paths(state)

    planning_state = get_planning_state()
    df_planning = (
        normalize_planning_df(planning_state.planning)
        if planning_state and planning_state.planning is not None
        else pd.DataFrame()
    )

    with st.spinner("Chargement des paramètres…"):
        df_paramdest, df_paramexpediteur, df_parambenev, _ = load_parameters(
            tdb_path=paths.tableau_de_bord,
            benev_path=paths.planning_benevoles,
        )
    df_vols = get_vols_df_cached(vols_path=paths.vols, tdb_path=paths.tableau_de_bord)
    df_dispos_raw = get_benevoles_cached(planning_path=paths.planning_benevoles)
    df_dispos = _prepare_dispo(df_dispos_raw)

    dest_city_map, city_to_iata_map = build_iata_city_maps(df_paramdest)

    # Sélecteur semaine (tri décroissant)
    weeks_set = _available_weeks_from_exports()
    df_be_p = None
    if not weeks_set:
        # fallback : déduire depuis MAG central (statut D)
        df_be_p = _load_be_status("D", tdb_path=paths.tableau_de_bord)
        weeks_set = _weeks_from_status_df(df_be_p)

    weeks, week_labels, week_map = _build_week_selector_data(weeks_set)

    if not weeks:
        st.warning("Impossible d'extraire les numéros de semaine.")
        return

    choice_week_label = st.selectbox("Choisir la semaine", week_labels, index=0)
    selected_week, selected_year = week_map.get(choice_week_label, weeks[0])

    # Sélection de la version du planning (recherche fichiers vX)
    planning_candidates = _find_planning_files_for_week(selected_week, selected_year)
    chosen_path = None
    if planning_candidates:
        labels, path_map = _build_planning_version_choices(
            planning_candidates,
            parse_version_from_name=_parse_version_from_name,
        )
        # ordre déjà décroissant, on garde index 0
        choice_label = st.selectbox("Choisir la version du planning", labels, index=0)
        chosen_path = path_map.get(choice_label)
    else:
        st.info("Aucune version de planning trouvée pour cette semaine, recherche par défaut.")

    # Aperçu du planning validé (OneDrive)
    df_preview, msg_preview, preview_path = _load_planning_preview_with_path(selected_week, selected_year, chosen_path)
    with st.expander("Aperçu du planning sélectionné", expanded=False):
        st.caption(msg_preview)
        if df_preview is not None and not df_preview.empty:
            df_preview = _format_preview_dataframe(df_preview)
            st.dataframe(df_preview.head(100), height=360, hide_index=True, width="stretch")
        else:
            st.warning("Aucun aperçu disponible pour cette semaine.")

    # BE issus du planning sélectionné (priorité à "Export planning") + BE statut D (MAG CENTRAL)
    df_export_planning = _load_export_planning_sheet(preview_path)
    df_source_for_be = _select_source_for_be(df_export_planning, df_preview)
    df_be_plan = _collect_be_from_planning(df_source_for_be, selected_week, selected_year)
    df_be_d = _load_be_status_d_for_week(selected_week, selected_year, tdb_path=paths.tableau_de_bord)

    prefill_values = _pop_prefill_values(st.session_state)
    prefill_action = prefill_values.get("action")
    prefill_be_key = prefill_values.get("be_key")
    prefill_be_num = prefill_values.get("be_num")
    prefill_date_new = prefill_values.get("date_new")
    prefill_vol_new = prefill_values.get("vol_new")
    prefill_heure_new = prefill_values.get("heure_new")
    prefill_bene = prefill_values.get("bene_choice")
    prefill_scope = prefill_values.get("be_scope")

    mode_col_scope, mode_col_be = st.columns([1, 3])
    with mode_col_scope:
        if prefill_scope in ("Déjà au planning", "A planifier"):
            st.session_state["ship_update_be_scope"] = prefill_scope
        be_scope = st.radio(
            "Afficher",
            ["Déjà au planning", "A planifier"],
            horizontal=False,
            key="ship_update_be_scope",
        )

    selected_be = ""
    be_row = None
    be_source = ""
    if be_scope == "A planifier":
        from loaders.load_shipments import load_shipments_df

        df_be_planif = load_shipments_df(planifiables_only=True, tdb_path=paths.tableau_de_bord)
        if df_be_planif is None or df_be_planif.empty:
            st.info("Aucun BE statut D trouvé.")
            return
        planned_set = set()
        if df_be_plan is not None and not df_be_plan.empty and "BE_Numero_Str" in df_be_plan.columns:
            planned_set = set(df_be_plan["BE_Numero_Str"].astype(str))

        be_options = _build_planif_be_options(df_be_planif, planned_set)
        if not be_options:
            st.info("Aucun BE statut D trouvé.")
            return
        be_labels = [b[2] for b in be_options]
        be_values = [b[1] for b in be_options]
        selected_idx = 0
        prefill_be = prefill_be_num or prefill_be_key
        if prefill_be and prefill_be in be_values:
            selected_idx = be_values.index(prefill_be)
        with mode_col_be:
            selected_be_label = st.selectbox(
                "Sélectionner un BE",
                options=be_labels,
                index=selected_idx,
            )
        idx_sel = be_labels.index(selected_be_label)
        selected_be = be_values[idx_sel]
        be_row = be_options[idx_sel][3]
        be_source = "mag_central"
    else:
        be_lookup, be_lookup_reason = _prepare_be_lookup(df_be_plan, df_be_d, df_paramdest)
        if be_lookup.empty:
            if be_lookup_reason == "missing_be":
                st.info("Aucun BE identifié (numéro manquant).")
            else:
                st.info("Aucun BE trouvé pour cette semaine (planning + statut D).")
            return

        with mode_col_be:
            be_options_list = be_lookup.index.tolist()
            prefill_be = prefill_be_key or prefill_be_num
            selected_idx = be_options_list.index(prefill_be) if prefill_be in be_options_list else 0
            selected_be = st.selectbox(
                "Sélectionner un BE",
                be_options_list,
                format_func=lambda num_str: _format_be_option_label(num_str, be_lookup),
                index=selected_idx,
            )

        if not selected_be:
            return

        be_row = be_lookup.loc[selected_be]
        if isinstance(be_row, pd.DataFrame):
            be_row = be_row.iloc[0]
        be_source = str(be_row.get("Source", "")).lower()

    if not selected_be or be_row is None:
        return

    dest_raw = be_row.get("Destination", be_row.get("Dest_IATA_Label", ""))
    dest_iata = _dest_to_iata(dest_raw, df_paramdest)
    date_initial = be_row.get("Date_Vol", be_row.get("BE_Date_Vol", ""))
    date_initial_long = _fmt_date_long(date_initial)
    expediteur_name = str(be_row.get("BE_Expediteur", "") or "").strip()

    plan_row = _match_planning_row(df_planning, selected_be)
    current_vol = ""
    current_heure = ""
    current_bene = ""
    bene_prenom_court = ""
    bene_nom = ""

    if plan_row is not None:
        date_initial = plan_row.get("Date_Vol", date_initial)
        date_initial_long = _fmt_date_long(date_initial)
        current_vol = plan_row.get("Numero_Vol", "")
        current_heure = plan_row.get("Heure_Vol", plan_row.get("Heure", ""))
        current_bene = plan_row.get("Benevole", "")
        bene_prenom_court = plan_row.get("Benevole_Prenom_Court", plan_row.get("Prenom_Court", ""))
        bene_nom = plan_row.get("Benevole_Nom", plan_row.get("Nom", ""))

    if not bene_prenom_court or not bene_nom:
        try:
            row_b = df_parambenev[df_parambenev["Benevole"] == current_bene]
            if not row_b.empty:
                bene_prenom_court = row_b.get("Prenom_Court", pd.Series([""])).iloc[0]
                bene_nom = row_b.get("Nom", pd.Series([""])).iloc[0]
        except Exception:
            pass

    if be_source == "planning":
        action_options = ["Annulation", "Changement de date ou bénévole"]
    else:
        action_options = ["Ajouter au planning"]
    action_idx = action_options.index(prefill_action) if prefill_action in action_options else 0
    action_choice = st.radio("Action", action_options, horizontal=True, index=action_idx)

    vol_options = []
    vol_labels: list[str]
    vol_values: list[Tuple[str, str, str]]
    default_vol_tuple = _build_default_vol_tuple(
        prefill_date_new=prefill_date_new,
        prefill_vol_new=prefill_vol_new,
        prefill_heure_new=prefill_heure_new,
        be_scope=be_scope,
        date_initial=date_initial,
        current_vol=current_vol,
        current_heure=current_heure,
    )
    action_requires_assignment = action_choice != "Annulation"
    if action_requires_assignment:
        col_vol, col_bene = st.columns(2)
        with col_vol:
            vol_options = _build_vol_options(dest_iata, df_vols, df_planning)
            vol_labels, vol_values, default_idx = _build_vol_selection_data(vol_options, default_vol_tuple)
            vol_choice = st.selectbox("Sélectionner un vol", vol_labels, index=default_idx if vol_labels else 0)
            date_new, vol_new, heure_new = _resolve_selected_vol(vol_labels, vol_values, vol_choice)
        with col_bene:
            def _status_for(name: str) -> str:
                return _bene_status(
                    df_dispos,
                    df_planning if df_planning is not None else pd.DataFrame(),
                    name,
                    date_new,
                    heure_new,
                    vol_new,
                )

            bene_options = _build_bene_options(
                df_parambenev,
                be_scope=be_scope,
                status_for=_status_for,
            )
            default_bene_label = _build_default_bene_label(
                prefill_bene=prefill_bene,
                current_bene=current_bene,
                be_scope=be_scope,
                status_for=_status_for,
            )
            bene_idx = bene_options.index(default_bene_label) if default_bene_label in bene_options else 0
            bene_choice_label = st.selectbox("Sélectionner un bénévole", bene_options or ["Aucun bénévole disponible"], index=bene_idx if bene_options else 0)
            bene_choice = _extract_bene_choice(bene_choice_label, bene_options)
            bene_prenom_court, bene_nom = _fill_bene_name_from_parambenev(
                df_parambenev,
                bene_choice=bene_choice,
                bene_prenom_court=str(bene_prenom_court or ""),
                bene_nom=str(bene_nom or ""),
            )
    else:
        date_new, vol_new, heure_new = str(date_initial), str(current_vol), str(current_heure)
        bene_choice = current_bene

    # Infos bénévole pour override
    bene_meta = _build_bene_meta(df_parambenev, bene_choice)
    bene_changed = (bene_choice or "") != (current_bene or "")

    bene_short = f"{str(bene_prenom_court).strip()} {str(bene_nom).strip().upper()}".strip() if (bene_prenom_court or bene_nom) else bene_choice
    vol_disp = _fmt_vol(vol_new) if vol_new else (_fmt_vol(current_vol) if current_vol else "")
    date_new_long = _fmt_date_long(date_new)
    action_sentence = _build_action_sentence(
        be_num=str(selected_be),
        dest_iata=dest_iata,
        date_initial=date_initial_long,
        action=action_choice,
        new_date=date_new_long or date_initial_long,
        vol_disp=vol_disp or "(vol ?)",
        bene_short=bene_short or "(bénévole ?)",
    )

    st.markdown(f"**Action prévue :** {action_sentence}")
    btn_disabled = action_requires_assignment and (not date_new_long or not vol_new or not bene_choice)

    def _open_file(path_obj: Path | None):
        if not path_obj:
            return
        try:
            import platform, subprocess, os
            if platform.system() == "Darwin":
                subprocess.Popen(["open", str(path_obj)])
            elif platform.system() == "Windows":
                os.startfile(str(path_obj))  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", str(path_obj)])
        except Exception:
            pass

    plan_row_full = _find_row_in_df(df_preview, selected_be) if df_preview is not None else None
    queue_item = _build_queue_item(
        week=selected_week,
        year=selected_year,
        dest_iata=dest_iata,
        dest_label=dest_raw,
        selected_be=selected_be,
        be_scope=be_scope,
        date_initial_long=date_initial_long,
        date_new_long=date_new_long,
        vol_disp=vol_disp,
        bene_short=bene_short,
        expediteur_name=expediteur_name,
        action_choice=action_choice,
        action_sentence=action_sentence,
        be_source=be_source,
        preview_path=preview_path,
        be_row=be_row,
        date_new=date_new,
        vol_new=vol_new,
        heure_new=heure_new,
        bene_choice=bene_choice,
        current_bene=current_bene,
        plan_row_full=plan_row_full,
        bene_meta=bene_meta,
        bene_changed=bene_changed,
    )

    queue = st.session_state.get("ship_update_queue", [])

    col_add, col_clear = st.columns([1, 1])
    with col_add:
        add_clicked = st.button(
            "Ajouter à la liste",
            type="primary",
            disabled=btn_disabled,
        )
    with col_clear:
        if st.button("Vider la liste"):
            _clear_queue_state(st.session_state, clear_payloads=True)
            st.success("Liste vidée.")

    if add_clicked:
        queue_path = st.session_state.get("ship_update_queue_planning_path")
        new_queue, add_error = _add_queue_item(
            queue,
            queue_item,
            preview_path=preview_path,
            existing_queue_path=queue_path,
        )
        if add_error:
            st.error(add_error)
            return
        st.session_state["ship_update_queue"] = new_queue or []
        st.session_state["ship_update_queue_planning_path"] = str(preview_path)
        st.session_state["ship_update_queue_week"] = selected_week
        st.session_state["ship_update_queue_year"] = selected_year
        st.success("Modification ajoutée à la liste.")

    queue = st.session_state.get("ship_update_queue", [])
    if queue:
        st.divider()
        st.subheader("Liste d'attente")
        df_queue = _build_queue_dataframe(queue)
        st.dataframe(df_queue, hide_index=True, width="stretch", height=240)

        queue_labels = _build_queue_labels(queue)
        sel_idx = st.selectbox(
            "Sélectionner une modification",
            options=list(range(len(queue_labels))),
            format_func=lambda i: queue_labels[i],
        )
        col_edit, col_del, col_clear2 = st.columns([1, 1, 1])
        with col_edit:
            if st.button("Éditer"):
                item = queue.pop(sel_idx)
                st.session_state["ship_update_queue"] = queue
                if not queue:
                    _clear_queue_state(st.session_state, clear_payloads=False)
                st.session_state["ship_update_prefill"] = item
                st.rerun()
        with col_del:
            if st.button("Supprimer"):
                queue.pop(sel_idx)
                st.session_state["ship_update_queue"] = queue
                if not queue:
                    _clear_queue_state(st.session_state, clear_payloads=False)
                st.success("Modification supprimée.")
                st.rerun()
        with col_clear2:
            if st.button("Vider la liste", key="ship_update_clear_queue_2"):
                _clear_queue_state(st.session_state, clear_payloads=True)
                st.success("Liste vidée.")
                st.rerun()

        col_apply, col_q1, col_mag = st.columns([1, 1, 2])
        with col_q1:
            increment_q1 = st.toggle(
                "Incrémenter Q1",
                value=True,
                key="ship_update_increment_q1",
            )
        with col_mag:
            write_mag_central = st.toggle(
                "Écrire sur MAG CENTRAL source",
                value=True,
                key="ship_update_write_mag_central",
            )
        with col_apply:
            apply_clicked = st.button(
                "Valider toutes les modifications",
                type="primary",
            )

        if apply_clicked:
            queue_path, deduped, ignored, prepare_error = _prepare_queue_apply(
                queue,
                queue_path=st.session_state.get("ship_update_queue_planning_path"),
                preview_path=preview_path,
            )
            if prepare_error or not queue_path:
                st.error(prepare_error or "Impossible de trouver le fichier planning à mettre à jour.")
                return

            dup_warning = _build_duplicate_be_warning(ignored)
            if dup_warning:
                st.warning(dup_warning)

            apply_result = _run_queue_apply_batch(
                queue_path=queue_path,
                deduped=deduped,
                queue_week=st.session_state.get("ship_update_queue_week", selected_week),
                queue_year=st.session_state.get("ship_update_queue_year", selected_year),
                selected_week=selected_week,
                selected_year=selected_year,
                df_vols=df_vols,
                df_parambenev=df_parambenev,
                df_dispos=df_dispos,
                df_paramdest=df_paramdest,
                increment_q1=increment_q1,
                write_mag_central=write_mag_central,
                tdb_source_path=get_tableau_de_bord_src(),
                apply_updates_fn=apply_planning_updates_batch,
                export_pdf_fn=export_first_sheet_to_pdf,
            )

            if apply_result["error"]:
                st.error(str(apply_result["error"]))
                return

            updated_path = apply_result["updated_path"]
            pdf_path = apply_result["pdf_path"]
            st.success(f"Planning Excel mis à jour : {updated_path.name}")
            if _should_show_mag_central_cleanup_info(
                write_mag_central=write_mag_central,
                deduped=deduped,
            ):
                st.info("MAG CENTRAL source nettoyé : colonnes L et W–Z vidées (date départ vol / bénévole / vol / heure).")
            if pdf_path:
                st.success(f"PDF généré : {pdf_path.name}")
                _open_file(updated_path)
                _open_file(pdf_path)
            elif apply_result["pdf_error"]:
                st.warning(f"PDF non généré automatiquement : {apply_result['pdf_error']}")

            payloads = apply_result["payloads"]
            st.session_state["ship_update_payloads"] = payloads
            _clear_queue_state(st.session_state, clear_payloads=False)
            st.success("Mises à jour validées. Choisissez qui prévenir ci-dessous.")

    payloads = st.session_state.get("ship_update_payloads")
    if not payloads:
        return

    st.divider()
    st.subheader("Notifications")

    week, year = _notification_period_from_payloads(
        payloads,
        default_week=selected_week,
        default_year=selected_year,
    )
    bene_emails = _collect_benevole_emails(payloads, df_parambenev)
    asf_draft = _build_asf_notification_draft(
        payloads,
        bene_emails,
        default_week=selected_week,
        default_year=selected_year,
        parse_version_from_name=_parse_version_from_name,
        export_pdf_fn=export_first_sheet_to_pdf,
    )
    week = int(asf_draft["week"])
    year = int(asf_draft["year"])

    col_asf, col_dest, col_exp = st.columns(3)

    with col_asf:
        if st.button("Prévenir ASF + Bénévole", key="btn_mail_asf"):
            create_outlook_draft(
                to_list=asf_draft["to_list"],
                cc_list=asf_draft["cc_list"],
                subject=asf_draft["subject"],
                body_html=asf_draft["body_html"],
                attachments=asf_draft["attachments"],
                use_signature=True,
            )
            st.success("Brouillon ASF ouvert.")

    with col_dest:
        dest_drafts = _build_destination_notification_drafts(
            payloads,
            df_paramdest,
            week=week,
            year=year,
            get_emails_for_destination=_get_emails_for_destination,
        )

        if st.button("Prévenir Escale", key="btn_mail_dest"):
            sent = []
            for draft in dest_drafts:
                create_outlook_draft(
                    to_list=draft["to_list"],
                    cc_list=draft["cc_list"],
                    subject=draft["subject"],
                    body_html=draft["body_html"],
                    attachments=draft["attachments"],
                    use_signature=True,
                )
                sent.append(str(draft["name"]))
            if sent:
                st.success(f"Brouillons Escale ouverts : {', '.join(sent)}")
            else:
                st.warning("Aucun email ParamDest trouvé.")

    with col_exp:
        exp_drafts = _build_expediteur_notification_drafts(
            payloads,
            df_paramexpediteur,
            week=week,
            year=year,
            get_emails_for_expediteur=_get_emails_for_expediteur,
        )

        if st.button("Prévenir Expéditeur", key="btn_mail_exp"):
            sent_exp = []
            for draft in exp_drafts:
                create_outlook_draft(
                    to_list=draft["to_list"],
                    cc_list=draft["cc_list"],
                    subject=draft["subject"],
                    body_html=draft["body_html"],
                    attachments=draft["attachments"],
                    use_signature=True,
                )
                sent_exp.append(str(draft["name"]))
            if sent_exp:
                st.success(f"Brouillons Expéditeur ouverts : {', '.join(sent_exp)}")
            else:
                st.warning("Aucun email expéditeur trouvé (ou expéditeur ASF).")
