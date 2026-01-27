# asf_app/ui/ui_communication/ui_communication.py
# -*- coding: utf-8 -*-
"""
Communication 4.0 — Version stable
Compatible avec enrich_planning() (planning enrichi complet).
"""

import streamlit as st
import pandas as pd
from utils.datetime_utils import coerce_datetime
import re
import fnmatch
from pathlib import Path

# PlanningState
from asf_app.ui.ui_planning.state_planning import get_planning_state

# Build df_comm
from asf_app.ui.ui_communication.clean_planning_df import build_df_comm

# UI dédiées
from asf_app.ui.ui_communication.email_airfrance_ui import render_email_airfrance_ui
from asf_app.ui.ui_communication.email_asf_ui import render_email_asf_ui
from asf_app.ui.ui_communication.email_destinations_ui import render_email_destinations_ui
from asf_app.ui.ui_communication.email_expediteurs_ui import render_email_expediteurs_ui
from asf_app.ui.ui_communication.whatsapp_ui import render_whatsapp_ui
from asf_app.ui.ui_communication.whatsapp_handler import (
    generate_whatsapp_messages,
    open_whatsapp_for_benevole
)
from scheduler.format_rules import format_be_number, format_vol_display
from utils.identifiers import normalize_be_number
from loaders.load_shipments import get_shipments_df_cached
from scheduler.planning_schema import normalize_planning_df
from asf_app.state import get_state, get_excel_source_paths

# Loaders (nouveau)
from asf_app.ui.loader import load_parameters
import scheduler.config_paths as cp
from asf_app.config.runtime import get_onedrive_root, get_output_remote_dir, get_tmp_dir, is_graph_onedrive
# load_parameters() retourne :
#   df_paramdest, df_paramexpediteur, df_parambenev, df_parambe


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


# ==========================================================
# UI PRINCIPALE
# ==========================================================
def render_tab_communication():

    st.title("📨 Communication")
    state = get_state()
    paths = get_excel_source_paths(state)

    # -------------------------------------------------------
    # 1) Choix de la source (moteur principal ou simulation OR-Tools)
    # -------------------------------------------------------
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

    if (df_plan_main is None or getattr(df_plan_main, "empty", True)) and (df_plan_sim is None or getattr(df_plan_sim, "empty", True)):
        st.warning("⚠️ Aucun planning principal. Lance une simulation OR-Tools pour alimenter la communication.")
        return

    options = []
    if df_plan_main is not None and not df_plan_main.empty:
        options.append("planning")
    if sim_res_modes:
        options.append("simulation")
    if not options:
        st.warning("⚠️ Aucun planning disponible. Lance une simulation (onglet Planning V2 / OR-Tools).")
        return
    default_source = "planning" if "planning" in options else options[0]
    source = st.radio(
        "Source du planning pour la communication",
        options=options,
        format_func=lambda x: "Moteur principal" if x == "planning" else "Planning V2 (OR-Tools)",
        index=options.index(default_source),
        horizontal=True,
    )

    df_planning = df_plan_main if source == "planning" else df_plan_sim
    # Si source = simulation et plusieurs modes, proposer un choix
    if source == "simulation" and sim_res_modes:
        mode_labels = []
        mode_values = []
        for key, res in sim_res_modes.items():
            stats_mode = res.get("statistiques", {})
            label = "Priorité Colis" if key == "colis" else "Priorité Bénévoles"
            extra = f" ({stats_mode.get('nb_colis_expedies', 0)} colis / {stats_mode.get('nb_benevoles_mobilises', 0)} bénév)"
            mode_labels.append(f"{label}{extra}")
            mode_values.append(key)
        sel_mode = st.radio(
            "Mode OR-Tools",
            options=mode_values,
            format_func=lambda m: mode_labels[mode_values.index(m)],
            index=mode_values.index(sim_active) if sim_active in mode_values else 0,
            horizontal=True,
        )
        st.session_state["sim_active_mode"] = sel_mode
        df_planning = normalize_planning_df(sim_res_modes[sel_mode].get("planning_df"))
        df_plan_sim = df_planning
    if df_planning is None or getattr(df_planning, "empty", True):
        st.warning("⚠️ Le planning choisi est vide.")
        return

    st.info("✔ Planning chargé depuis : " + ("Moteur principal" if source == "planning" else "Simulation OR-Tools"))

    # -------------------------------------------------------
    # 2) Charger ParamDest / ParamBenev / ParamExp / ParamBE
    # -------------------------------------------------------
    df_paramdest, df_paramexpediteur, df_parambenev, df_parambe = load_parameters(
        tdb_path=paths.tableau_de_bord,
        benev_path=paths.planning_benevoles,
    )

    # Pièce jointe par défaut : recherche du PDF officiel uniquement
    pdf_attach_path = None

    # -------------------------------------------------------
    # 3) Construction du fichier Communication
    # -------------------------------------------------------
    df_comm = build_df_comm(
        df_planning=df_planning,
        df_paramdest=df_paramdest,
        df_parambenev=df_parambenev
    )

    # Compléter Destinataire via mapping BE (MAG CENTRAL + planning), avec tolérance format
    try:
        df_be = get_shipments_df_cached(tdb_path=paths.tableau_de_bord)
    except Exception:
        df_be = pd.DataFrame()

    def _norm_be(val):
        return normalize_be_number(val) or str(val).strip()

    def _keys_from_be(val):
        d = _norm_be(val)
        keys = {d}
        for n in [6, 5, 4, 3]:
            if len(d) >= n:
                keys.add(d[-n:])
        return [k for k in keys if k]

    def _collect_map(df_source):
        mapping = {}
        if df_source is None or df_source.empty:
            return mapping
        for _, row in df_source.iterrows():
            dest_val = row.get("BE_Destinataire", "")
            if pd.isna(dest_val) or str(dest_val).strip() == "":
                continue
            for k in _keys_from_be(row.get("BE_Numero", "")):
                if k not in mapping:
                    mapping[k] = dest_val
        return mapping

    map_dest_be = {}
    map_dest_be.update(_collect_map(df_be))
    if "BE_Destinataire" in df_planning.columns:
        map_dest_be.update(_collect_map(df_planning))

    if map_dest_be:
        if "Destinataire" not in df_comm.columns:
            df_comm["Destinataire"] = ""
        df_comm["Destinataire"] = df_comm["Destinataire"].replace("", pd.NA)
        # Chercher un numéro de BE exploitable dans df_comm
        def _key_from_row(r):
            for col in ["NUMERO BE", "BE_Numero", "Numero_BE_Aff", "Numero_BE"]:
                if col in r and str(r[col]).strip():
                    return _norm_be(r[col])
            return ""
        def _lookup_dest(row):
            keys = _keys_from_be(_key_from_row(row))
            for k in keys:
                if k in map_dest_be:
                    return map_dest_be[k]
            return ""
        mask_dest_empty = df_comm["Destinataire"].isna() | df_comm["Destinataire"].astype(str).str.strip().eq("")
        df_comm.loc[mask_dest_empty, "Destinataire"] = df_comm.loc[mask_dest_empty].apply(_lookup_dest, axis=1)

    if df_comm.empty:
        st.error("❌ Impossible de générer df_comm (problème données).")
        return

    # -------------------------------------------------------
    # 4) Détection semaine
    # -------------------------------------------------------
    week, year = _detect_week_year(df_comm)
    if week is None:
        st.error("Impossible de détecter la semaine depuis df_comm.")
        return

    st.success(f"📅 Communication pour S{week} – {year}")

    # Recherche du PDF dans OneDrive (format avec versions)
    pdf_attach_path = None
    try:
        pattern_old = f"ASFmm - PLANNING SEMAINE N° {week:02d} - {year}*.pdf"
        pattern_new = f"ASFmm - PLANNING SEMAINE {year}-{week:02d}-*.pdf"
        if is_graph_onedrive():
            remote_dir = get_output_remote_dir(year)
            items = cp.list_onedrive_files(remote_dir, recursive=False, suffixes=[".pdf"])
            candidates = [
                i for i in items
                if fnmatch.fnmatch(i.get("name", ""), pattern_old)
                or fnmatch.fnmatch(i.get("name", ""), pattern_new)
            ]
            if candidates:
                labels = [c.get("name", "") for c in candidates]
                pdf_choice = st.radio(
                    "Choisir la version PDF à utiliser",
                    options=labels,
                    index=0,
                    horizontal=True,
                )
                chosen = candidates[labels.index(pdf_choice)]
                remote_path = chosen.get("path", "")
                if remote_path:
                    local_path = get_tmp_dir() / "onedrive_cache" / "planning_pdf" / remote_path
                    if not local_path.exists():
                        cp.download_onedrive_file(remote_path, local_path, interactive=False)
                    if local_path.exists():
                        pdf_attach_path = local_path
        else:
            base_pdf_dir = get_onedrive_root() / "Planning MAB" / f"ASFmm PLANNING {year}"
            if base_pdf_dir.exists():
                candidates = sorted(
                    list(base_pdf_dir.glob(pattern_old)) + list(base_pdf_dir.glob(pattern_new)),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                if candidates:
                    labels = [c.name for c in candidates]
                    pdf_choice = st.radio(
                        "Choisir la version PDF à utiliser",
                        options=labels,
                        index=0,
                        horizontal=True,
                    )
                    pdf_attach_path = candidates[labels.index(pdf_choice)]
    except Exception:
        pdf_attach_path = None

    if pdf_attach_path:
        st.info(f"📎 PDF joint détecté : {Path(pdf_attach_path).name}")
    else:
        st.warning("📎 Pas de planning PDF trouvé - ajouter le manuellement.")

    st.divider()

    # ----------------------------------------------------------------------
    # 📋 Aperçu planning enrichi (formats BE/Vol/Heure)
    # ----------------------------------------------------------------------
    with st.expander("📋 Aperçu Planning (Enrichi)", expanded=False):
        df_display = df_comm.copy()
        # Formats
        # BE format YYNNNN avec fallback (si ajout manuel)
        df_display["Numero_BE_Aff"] = (
            df_display.get("Numero_BE_Aff", df_display.get("NUMERO BE", df_display.get("BE_Numero", ""))))
        df_display["Numero_BE_Aff"] = df_display["Numero_BE_Aff"].apply(format_be_number)
        df_display["Numero_Vol_Aff"] = df_display.get("Numero_Vol_Aff", df_display.get("NUMERO VOL", "")).apply(format_vol_display)
        df_display["Heure_Vol_Aff"] = (
            df_display.get("Heure_Vol_Aff", df_display.get("HEURE VOL", ""))
            .astype(str)
            .str.slice(0, 5)
            .str.replace(":", "h", 1)
        )
        # Destinataire / Expéditeur : fallbacks depuis différentes colonnes
        def _fill_from_candidates(df, target, keywords):
            if target not in df.columns:
                df[target] = ""
            df[target] = df[target].replace("", pd.NA)
            for col in df.columns:
                if any(k.lower() in col.lower() for k in keywords):
                    df[target] = df[target].fillna(df[col]).replace("", pd.NA)
            df[target] = df[target].fillna("").astype(str)
            return df

        df_display = _fill_from_candidates(df_display, "Destinataire", ["destinataire"])
        df_display = _fill_from_candidates(df_display, "Expediteur", ["expediteur", "expéditeur"])

        st.dataframe(df_display, hide_index=True, width="stretch", height=320)

    st.divider()

    # Barre de boutons (comme onglet Paramètres)
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

    st.divider()

    # Rendu du bloc sélectionné sur toute la largeur
    if section == "whatsapp":
        if st.button("Générer les messages WhatsApp", type="primary"):
            msgs = generate_whatsapp_messages(df_comm)
            st.session_state["whatsapp_messages"] = msgs

            if msgs:
                st.success(f"{len(msgs)} messages générés.")
            else:
                st.warning("Aucun message généré.")

        msgs = st.session_state.get("whatsapp_messages", [])
        if msgs:
            for idx, msg in enumerate(msgs):
                bene = msg["benevole"]
                tel = msg["telephone"]
                st.markdown(f"**{bene} — {tel}**")
                st.code(msg["message"])
                if st.button(f"📲 Envoyer WhatsApp à {bene}", key=f"wa_{idx}_{bene}", type="primary"):
                    open_whatsapp_for_benevole(msg["url"])
        else:
            st.info("Aucun message WhatsApp généré.")

    elif section == "airfrance":
        render_email_airfrance_ui(
            df_comm=df_comm,
            attachment_path=None,
            pdf_attachment_path=pdf_attach_path,
        )

    elif section == "asf":
        render_email_asf_ui(
            df_comm=df_comm,
            attachment_path=None,
            pdf_attachment_path=pdf_attach_path,
        )

    elif section == "dest":
        render_email_destinations_ui(
            df_comm=df_comm,
            df_paramdest=df_paramdest,
            week=week,
            year=year
        )

    elif section == "exp":
        render_email_expediteurs_ui(
            df_comm=df_comm,
            df_paramdest=df_paramdest,
            df_paramexpediteur=df_paramexpediteur,
            week=week,
            year=year
        )
