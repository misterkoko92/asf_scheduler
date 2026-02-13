# asf_app/ui/ui_communication/ui_communication.py
# -*- coding: utf-8 -*-
"""
Communication 4.0 — Version stable
Compatible avec enrich_planning() (planning enrichi complet).
"""

import fnmatch
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

import scheduler.config_paths as cp
from asf_app.config.runtime import (
    get_onedrive_root,
    get_output_remote_dir,
    get_tmp_dir,
    is_graph_onedrive,
)
from asf_app.state import get_excel_source_paths, get_state

# Loaders (nouveau)
from asf_app.ui.loader import load_parameters

# Build df_comm
from asf_app.ui.ui_communication.clean_planning_df import build_df_comm

# UI dédiées
from asf_app.ui.ui_communication.email_airfrance_ui import render_email_airfrance_ui
from asf_app.ui.ui_communication.email_asf_ui import render_email_asf_ui
from asf_app.ui.ui_communication.email_destinations_ui import render_email_destinations_ui
from asf_app.ui.ui_communication.email_expediteurs_ui import render_email_expediteurs_ui
from asf_app.ui.ui_communication.ui_communication_helpers import (
    build_communication_display_dataframe,
    build_destinataire_mapping,
    build_session_source_options,
    build_sim_mode_selector_data,
    fill_missing_destinataire,
    is_empty_dataframe,
    reset_onedrive_loaded_state_for_year,
    resolve_default_session_source,
)
from asf_app.ui.ui_communication.whatsapp_handler import (
    generate_whatsapp_messages,
    open_whatsapp_for_benevole,
)

# PlanningState
from asf_app.ui.ui_planning.state_planning import get_planning_state
from loaders.load_shipments import get_shipments_df_cached
from scheduler.planning_schema import normalize_planning_df
from utils.datetime_utils import coerce_datetime
from utils.logging_utils import get_logger
from utils.path_utils import safe_cache_path

# load_parameters() retourne :
#   df_paramdest, df_paramexpediteur, df_parambenev, df_parambe


logger = get_logger("ui_communication", console=False)

COMM_IO_ERRORS = (
    FileNotFoundError,
    OSError,
    PermissionError,
    ValueError,
    TypeError,
    RuntimeError,
    KeyError,
    pd.errors.ParserError,
    ImportError,
)


# ==========================================================
# Détecter semaine / année
# ==========================================================
def _detect_week_year(df_comm):
    if df_comm is None or df_comm.empty or "DATE" not in df_comm.columns:
        return None, None
    dates = coerce_datetime(df_comm["DATE"], errors="coerce").dropna()
    if dates.empty:
        return None, None
    dt = dates.min()
    return int(dt.isocalendar().week), int(dt.year)

def _parse_onedrive_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError):
        return None


def _list_local_planning_files(year: int) -> list[Path]:
    base_dir = get_onedrive_root() / "Planning MAB" / f"ASFmm PLANNING {year}"
    if not base_dir.exists():
        return []
    files = [p for p in base_dir.glob("*.xls*") if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files


def _list_onedrive_planning_files(year: int) -> list[dict]:
    remote_dir = get_output_remote_dir(year)
    items = cp.list_onedrive_files(remote_dir, recursive=False, suffixes=[".xlsx", ".xlsm", ".xls"])
    files = []
    for item in items:
        name = item.get("name", "")
        if not name.lower().endswith((".xlsx", ".xlsm", ".xls")):
            continue
        if "folder" in item:
            continue
        files.append(
            {
                "name": name,
                "path": item.get("path", ""),
                "modified": _parse_onedrive_datetime(item.get("lastModifiedDateTime"))
                or _parse_onedrive_datetime(item.get("createdDateTime")),
            }
        )
    files.sort(key=lambda f: f["modified"] or datetime.min, reverse=True)
    return files


def _read_export_planning(path: Path) -> pd.DataFrame:
    try:
        df_raw = pd.read_excel(path, sheet_name="Export planning", dtype=object)
    except COMM_IO_ERRORS as exc:
        logger.warning("Lecture export planning impossible (%s): %s", path, exc)
        return pd.DataFrame()
    if df_raw is None or df_raw.empty:
        return pd.DataFrame()
    return normalize_planning_df(df_raw)


def _load_session_planning_ui() -> pd.DataFrame | None:
    planning_state = get_planning_state()
    df_plan_main = normalize_planning_df(planning_state.planning)

    # OR-Tools V2 dans l'onglet simulation : stocké dans sim_results
    sim_res_modes = st.session_state.get("sim_results") or {}
    sim_active = st.session_state.get("sim_active_mode")
    df_plan_sim = None
    if sim_res_modes:
        if sim_active and sim_active in sim_res_modes:
            df_plan_sim = normalize_planning_df(sim_res_modes[sim_active].get("planning_df"))
        else:
            # premier mode disponible
            df_plan_sim = normalize_planning_df(next(iter(sim_res_modes.values())).get("planning_df"))

    if is_empty_dataframe(df_plan_main) and is_empty_dataframe(df_plan_sim):
        st.warning("⚠️ Aucun planning principal. Génère un planning dans l'onglet Planning pour alimenter la communication.")
        return None

    options = build_session_source_options(df_plan_main=df_plan_main, sim_res_modes=sim_res_modes)
    if not options:
        st.warning("⚠️ Aucun planning disponible. Génère un planning (onglet Planning).")
        return None

    default_source = resolve_default_session_source(options)
    source = st.radio(
        "Source session",
        options=options,
        format_func=lambda x: "Moteur principal" if x == "planning" else "Planning (OR-Tools)",
        index=options.index(default_source),
        horizontal=True,
    )

    df_planning = df_plan_main if source == "planning" else df_plan_sim
    # Si source = simulation et plusieurs modes, proposer un choix
    if source == "simulation" and sim_res_modes:
        mode_values, mode_labels = build_sim_mode_selector_data(sim_res_modes)
        selected_idx = mode_values.index(sim_active) if sim_active in mode_values else 0
        sel_mode = st.radio(
            "Mode OR-Tools",
            options=mode_values,
            format_func=lambda m: mode_labels.get(m, m),
            index=selected_idx,
            horizontal=True,
        )
        st.session_state["sim_active_mode"] = sel_mode
        df_planning = normalize_planning_df(sim_res_modes[sel_mode].get("planning_df"))
    if is_empty_dataframe(df_planning):
        st.warning("⚠️ Le planning choisi est vide.")
        return None

    st.info("✔ Planning chargé depuis : " + ("Moteur principal" if source == "planning" else "Planning OR-Tools"))
    return df_planning


def _load_onedrive_planning_ui() -> pd.DataFrame | None:
    year_default = datetime.now().year
    year = int(
        st.number_input(
            "Année du planning",
            min_value=2024,
            max_value=2100,
            value=year_default,
            step=1,
            key="comm_onedrive_year",
        )
    )

    reset_onedrive_loaded_state_for_year(st.session_state, year=year)

    if is_graph_onedrive():
        remote_files = _list_onedrive_planning_files(year)
        if not remote_files:
            st.warning("⚠️ Aucun fichier Excel trouvé dans OneDrive pour cette année.")
        else:
            labels = [f["name"] for f in remote_files]
            choice = st.radio("Fichiers Excel disponibles", options=labels, index=0, key="comm_onedrive_file")
            if st.button("✅ Valider ce planning", type="primary"):
                chosen = remote_files[labels.index(choice)]
                remote_path = chosen.get("path", "")
                if not remote_path:
                    st.error("Chemin OneDrive invalide.")
                else:
                    cache_root = get_tmp_dir() / "onedrive_cache" / "planning_xlsx"
                    try:
                        local_path = safe_cache_path(cache_root, remote_path)
                    except ValueError:
                        st.error(f"Chemin OneDrive invalide : {remote_path}")
                        local_path = None
                    if local_path:
                        ok = cp.download_onedrive_file(remote_path, local_path, interactive=False)
                        if not ok and not local_path.exists():
                            st.error("Téléchargement OneDrive impossible.")
                        else:
                            df_loaded = _read_export_planning(local_path)
                            if df_loaded.empty:
                                st.error("Feuille 'Export planning' introuvable ou vide.")
                            else:
                                st.session_state["comm_onedrive_df"] = df_loaded
                                st.session_state["comm_onedrive_file_label"] = chosen.get("name", "")
                                st.session_state["comm_onedrive_file_path"] = remote_path
                                st.session_state["comm_onedrive_loaded_year"] = year
    else:
        local_files = _list_local_planning_files(year)
        if not local_files:
            st.warning("⚠️ Aucun fichier Excel trouvé dans OneDrive pour cette année.")
        else:
            labels = [f.name for f in local_files]
            choice = st.radio("Fichiers Excel disponibles", options=labels, index=0, key="comm_onedrive_file")
            if st.button("✅ Valider ce planning", type="primary"):
                chosen_local = local_files[labels.index(choice)]
                df_loaded = _read_export_planning(chosen_local)
                if df_loaded.empty:
                    st.error("Feuille 'Export planning' introuvable ou vide.")
                else:
                    st.session_state["comm_onedrive_df"] = df_loaded
                    st.session_state["comm_onedrive_file_label"] = chosen_local.name
                    st.session_state["comm_onedrive_file_path"] = str(chosen_local)
                    st.session_state["comm_onedrive_loaded_year"] = year

    df_planning = st.session_state.get("comm_onedrive_df")
    file_label = st.session_state.get("comm_onedrive_file_label", "")
    if is_empty_dataframe(df_planning):
        st.info("Sélectionne un fichier puis clique sur “Valider ce planning” pour continuer.")
        return None
    st.info(f"✔ Planning chargé depuis OneDrive : {file_label}")
    return df_planning


def _select_communication_planning_source() -> pd.DataFrame | None:
    source_mode = st.radio(
        "Source du planning pour la communication",
        options=["session", "onedrive"],
        format_func=lambda x: "Planning de la session" if x == "session" else "Planning OneDrive",
        index=0,
        horizontal=True,
        key="comm_source_mode",
    )
    if source_mode == "session":
        return _load_session_planning_ui()
    return _load_onedrive_planning_ui()


def _load_communication_parameters(paths):
    return load_parameters(
        tdb_path=paths.tableau_de_bord,
        benev_path=paths.planning_benevoles,
    )


def _build_enriched_comm_dataframe(
    *,
    df_planning: pd.DataFrame,
    df_paramdest: pd.DataFrame,
    df_parambenev: pd.DataFrame,
    tdb_path,
) -> pd.DataFrame:
    df_comm = build_df_comm(
        df_planning=df_planning,
        df_paramdest=df_paramdest,
        df_parambenev=df_parambenev,
    )
    try:
        df_be = get_shipments_df_cached(tdb_path=tdb_path)
    except COMM_IO_ERRORS as exc:
        logger.warning("Chargement MAG CENTRAL impossible: %s", exc)
        df_be = pd.DataFrame()
    map_dest_be = build_destinataire_mapping(df_be=df_be, df_planning=df_planning)
    return fill_missing_destinataire(df_comm, map_dest_be)


def _resolve_pdf_candidates_from_graph(week: int, year: int) -> list[dict]:
    remote_dir = get_output_remote_dir(year)
    items = cp.list_onedrive_files(remote_dir, recursive=False, suffixes=[".pdf"])
    pattern_old = f"ASFmm - PLANNING SEMAINE N° {week:02d} - {year}*.pdf"
    pattern_new = f"ASFmm - PLANNING SEMAINE {year}-{week:02d}-*.pdf"
    return [
        i
        for i in items
        if fnmatch.fnmatch(i.get("name", ""), pattern_old)
        or fnmatch.fnmatch(i.get("name", ""), pattern_new)
    ]


def _resolve_pdf_candidates_from_local(week: int, year: int) -> list[Path]:
    pattern_old = f"ASFmm - PLANNING SEMAINE N° {week:02d} - {year}*.pdf"
    pattern_new = f"ASFmm - PLANNING SEMAINE {year}-{week:02d}-*.pdf"
    base_pdf_dir = get_onedrive_root() / "Planning MAB" / f"ASFmm PLANNING {year}"
    if not base_pdf_dir.exists():
        return []
    return sorted(
        list(base_pdf_dir.glob(pattern_old)) + list(base_pdf_dir.glob(pattern_new)),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def _resolve_pdf_attachment_path(week: int, year: int):
    try:
        if is_graph_onedrive():
            candidates = _resolve_pdf_candidates_from_graph(week, year)
            if not candidates:
                return None
            labels = [c.get("name", "") for c in candidates]
            pdf_choice = st.radio(
                "Choisir la version PDF à utiliser",
                options=labels,
                index=0,
                horizontal=True,
            )
            chosen = candidates[labels.index(pdf_choice)]
            remote_path = chosen.get("path", "")
            if not remote_path:
                return None
            cache_root = get_tmp_dir() / "onedrive_cache" / "planning_pdf"
            try:
                local_path = safe_cache_path(cache_root, remote_path)
            except ValueError:
                st.error(f"Chemin OneDrive invalide : {remote_path}")
                return None
            if not local_path.exists():
                cp.download_onedrive_file(remote_path, local_path, interactive=False)
            return local_path if local_path.exists() else None

        candidates_local = _resolve_pdf_candidates_from_local(week, year)
        if not candidates_local:
            return None
        labels = [c.name for c in candidates_local]
        pdf_choice = st.radio(
            "Choisir la version PDF à utiliser",
            options=labels,
            index=0,
            horizontal=True,
        )
        return candidates_local[labels.index(pdf_choice)]
    except COMM_IO_ERRORS as exc:
        logger.warning("Recherche PDF communication impossible: %s", exc)
        return None


def _render_whatsapp_section(df_comm: pd.DataFrame) -> None:
    if st.button("Générer les messages WhatsApp", type="primary"):
        msgs = generate_whatsapp_messages(df_comm)
        st.session_state["whatsapp_messages"] = msgs
        if msgs:
            st.success(f"{len(msgs)} messages générés.")
        else:
            st.warning("Aucun message généré.")

    msgs = st.session_state.get("whatsapp_messages", [])
    if not msgs:
        st.info("Aucun message WhatsApp généré.")
        return

    for idx, msg in enumerate(msgs):
        bene = msg["benevole"]
        tel = msg["telephone"]
        st.markdown(f"**{bene} — {tel}**")
        st.code(msg["message"])
        if st.button(f"📲 Envoyer WhatsApp à {bene}", key=f"wa_{idx}_{bene}", type="primary"):
            open_whatsapp_for_benevole(msg["url"])


def _render_comm_sections_bar() -> str:
    section = st.session_state.get("comm_section", "whatsapp")
    cols = st.columns(5)
    labels = [
        ("whatsapp", "💬 WhatsApp"),
        ("airfrance", "✈️ Air France"),
        ("asf", "🏠 ASF Interne"),
        ("dest", "📍 Destinations"),
        ("exp", "📦 Expéditeurs"),
    ]
    for col, (key, label) in zip(cols, labels):
        if col.button(label, type="primary" if section == key else "secondary"):
            section = key
            st.session_state["comm_section"] = key
    return section


def _render_selected_communication_section(
    *,
    section: str,
    df_comm: pd.DataFrame,
    df_paramdest: pd.DataFrame,
    df_paramexpediteur: pd.DataFrame,
    week: int,
    year: int,
    pdf_attach_path,
) -> None:
    if section == "whatsapp":
        _render_whatsapp_section(df_comm)
        return
    if section == "airfrance":
        render_email_airfrance_ui(
            df_comm=df_comm,
            attachment_path=None,
            pdf_attachment_path=pdf_attach_path,
        )
        return
    if section == "asf":
        render_email_asf_ui(
            df_comm=df_comm,
            attachment_path=None,
            pdf_attachment_path=pdf_attach_path,
        )
        return
    if section == "dest":
        render_email_destinations_ui(
            df_comm=df_comm,
            df_paramdest=df_paramdest,
            week=week,
            year=year,
        )
        return
    if section == "exp":
        render_email_expediteurs_ui(
            df_comm=df_comm,
            df_paramdest=df_paramdest,
            df_paramexpediteur=df_paramexpediteur,
            week=week,
            year=year,
        )


def _build_communication_payload(paths):
    df_planning = _select_communication_planning_source()
    if is_empty_dataframe(df_planning):
        return None

    df_paramdest, df_paramexpediteur, df_parambenev, _ = _load_communication_parameters(paths)
    df_comm = _build_enriched_comm_dataframe(
        df_planning=df_planning,
        df_paramdest=df_paramdest,
        df_parambenev=df_parambenev,
        tdb_path=paths.tableau_de_bord,
    )
    if df_comm.empty:
        st.error("❌ Impossible de générer df_comm (problème données).")
        return None

    week, year = _detect_week_year(df_comm)
    if week is None:
        st.error("Impossible de détecter la semaine depuis df_comm.")
        return None

    return {
        "df_comm": df_comm,
        "df_paramdest": df_paramdest,
        "df_paramexpediteur": df_paramexpediteur,
        "week": week,
        "year": year,
    }


def _render_pdf_attachment_status(pdf_attach_path) -> None:
    if pdf_attach_path:
        st.info(f"📎 PDF joint détecté : {Path(pdf_attach_path).name}")
    else:
        st.warning("📎 Pas de planning PDF trouvé - ajouter le manuellement.")


def _render_communication_preview(df_comm: pd.DataFrame) -> None:
    with st.expander("📋 Aperçu Planning (Enrichi)", expanded=False):
        df_display = build_communication_display_dataframe(df_comm)
        st.dataframe(df_display, hide_index=True, width="stretch", height=320)


# ==========================================================
# UI PRINCIPALE
# ==========================================================
def render_tab_communication():

    st.title("📨 Communication")
    state = get_state()
    paths = get_excel_source_paths(state)

    payload = _build_communication_payload(paths)
    if payload is None:
        return

    df_comm = payload["df_comm"]
    df_paramdest = payload["df_paramdest"]
    df_paramexpediteur = payload["df_paramexpediteur"]
    week = payload["week"]
    year = payload["year"]

    st.success(f"📅 Communication pour S{week} – {year}")

    pdf_attach_path = _resolve_pdf_attachment_path(week, year)
    _render_pdf_attachment_status(pdf_attach_path)

    st.divider()
    _render_communication_preview(df_comm)

    st.divider()

    section = _render_comm_sections_bar()

    st.divider()

    _render_selected_communication_section(
        section=section,
        df_comm=df_comm,
        df_paramdest=df_paramdest,
        df_paramexpediteur=df_paramexpediteur,
        week=week,
        year=year,
        pdf_attach_path=pdf_attach_path,
    )
