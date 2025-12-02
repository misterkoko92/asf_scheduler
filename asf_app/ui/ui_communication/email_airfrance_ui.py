# email_airfrance_ui.py — Communication 3.0
# -----------------------------------------
# UI Streamlit pour le mail Air France :
# - TO / CC modifiables
# - Sujet modifiable (avec valeur par défaut dynamique Semaine XX)
# - Corps modifiable (avec texte par défaut)
# - Utilise df_comm pour récupérer semaine/année si besoin

import streamlit as st
import pandas as pd
from datetime import datetime

from asf_app.ui.ui_communication.email_airfrance_handler import (
    generate_airfrance_email,
    build_subject_airfrance,
    DEFAULT_BODY_AIRFRANCE,
)
from asf_app.ui.ui_planning.state_planning import get_planning_state

def _detect_week_year_from_df(df_comm: pd.DataFrame):
    """
    Détecte semaine + année à partir de df_comm["DATE"].
    Fallback si le state ne fournit pas déjà la semaine.
    """
    if df_comm is None or df_comm.empty or "DATE" not in df_comm.columns:
        return None, None

    dates = pd.to_datetime(df_comm["DATE"], errors="coerce").dropna()
    if dates.empty:
        return None, None

    dt0 = dates.min()
    week = int(dt0.isocalendar().week)
    year = int(dt0.year)
    return week, year


def render_email_airfrance_ui(df_comm: pd.DataFrame, attachment_path=None, pdf_attachment_path=None):
    st.subheader("✈️ Mail Air France")

    # Détection semaine / année
    week = st.session_state.get("current_week")
    year = st.session_state.get("current_year")

    if week is None or year is None:
        w, y = _detect_week_year_from_df(df_comm)
        week = week or w
        year = year or y

    if week is None or year is None:
        st.error("Impossible de détecter la semaine / année. Vérifie le planning.")
        return

    col1, col2 = st.columns(2)

    with col1:
        to_default = (
            "nafontaine1@airfrance.fr; anchanet@airfrance.fr"
        )
        to_input = st.text_input(
            "Destinataires (To)",
            value=to_default,
            help="Sépare les adresses par ';' ou ','."
        )

    with col2:
        cc_default = (
            "messmed@aviation-sans-frontieres-fr.org; "
            "f.cottence@samsic.aero; m.dorigny@gsf.fr; "
            "a.joyeux@gsf.fr; s.chadli@samsic.aero; pestarland@airfrance.fr"
        )
        cc_input = st.text_input(
            "Copie (CC)",
            value=cc_default,
            help="Sépare les adresses par ';' ou ','."
        )

    # Sujet & corps modifiables
    subject_default = build_subject_airfrance(week, year)
    subject = st.text_input("Sujet", value=subject_default)

    body_default = DEFAULT_BODY_AIRFRANCE.format(week=week)
    body = st.text_area(
        "Corps du message (HTML simple)",
        value=body_default,
        height=180
    )
    body_preview = body.replace("<br>", "\n").replace("<br/>", "\n")
    with st.expander("Aperçu texte"):
        st.text(body_preview)

    attachments = None
    if pdf_attachment_path:
        st.info(f"Pièce jointe : {getattr(pdf_attachment_path, 'name', pdf_attachment_path)}")
        attachments = [str(pdf_attachment_path)]
    else:
        st.warning("Pas de planning PDF trouvé - ajouter le manuellement.")

    st.markdown(
        "_La signature par défaut d'Outlook sera ajoutée automatiquement à l'ouverture du brouillon._"
    )

    if st.button("📤 Générer le mail Air France", type="primary"):
        ok = generate_airfrance_email(
            to_list=to_input,
            cc_list=cc_input,
            week=week,
            year=year,
            custom_subject=subject,
            custom_body=body,
            attachments=attachments,
        )
        if ok:
            st.success("Brouillon Air France créé dans Outlook.")
        else:
            st.error("Échec de création du mail Air France.")
