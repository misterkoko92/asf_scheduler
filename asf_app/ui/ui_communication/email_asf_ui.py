# email_asf_ui.py — Communication 3.0
# -----------------------------------
# UI Streamlit pour le mail ASF Interne :
# - TO / CC / BCC modifiables
# - Sujet / Corps modifiables
# - Utilise df_comm pour détecter la semaine / année

import streamlit as st
import pandas as pd

from asf_app.ui.ui_communication.email_asf_handler import (
    generate_asf_email,
    build_subject_asf,
    DEFAULT_BODY_ASF,
)
from asf_app.ui.ui_planning.state_planning import get_planning_state
from asf_app.ui.email_defaults import get_email_defaults

def _detect_week_year_from_df(df_comm: pd.DataFrame):
    if df_comm is None or df_comm.empty or "DATE" not in df_comm.columns:
        return None, None

    dates = pd.to_datetime(df_comm["DATE"], errors="coerce").dropna()
    if dates.empty:
        return None, None

    dt0 = dates.min()
    week = int(dt0.isocalendar().week)
    year = int(dt0.year)
    return week, year


def render_email_asf_ui(df_comm: pd.DataFrame, attachment_path=None, pdf_attachment_path=None):
    st.subheader("🏠 Mail ASF Interne")

    # Détection semaine / année
    week = st.session_state.get("current_week")
    year = st.session_state.get("current_year")

    if week is None or year is None:
        w, y = _detect_week_year_from_df(df_comm)
        week = week or w
        year = year or y

    if week is None or year is None:
        st.error("Impossible de détecter la semaine / année.")
        return

    defaults = get_email_defaults()
    asf_defaults = defaults.get("asf_interne", {})

    col1, col2 = st.columns(2)

    with col1:
        to_default = asf_defaults.get("to", "")
        to_input = st.text_input(
            "Destinataires (To)",
            value=to_default,
            key="asf_to",
            help="Sépare les adresses par ';' ou ','."
        )

    with col2:
        cc_default = asf_defaults.get("cc", "")
        cc_input = st.text_input(
            "Copie (CC)",
            value=cc_default,
            key="asf_cc",
            help="Sépare les adresses par ';' ou ','."
        )

    bcc_default = asf_defaults.get("bcc", "")
    bcc_input = st.text_input(
        "Copie cachée (CCI)",
        value=bcc_default,
        key="asf_bcc",
        help="Sépare les adresses par ';' ou ','."
    )

    subject_default = build_subject_asf(week, year)
    subject = st.text_input("Sujet", value=subject_default)

    body_default = DEFAULT_BODY_ASF.format(week=week)
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

    if st.button("📤 Générer le mail ASF Interne", type="primary"):
        ok = generate_asf_email(
            to_list=to_input,
            cc_list=cc_input,
            bcc_list=bcc_input,
            week=week,
            year=year,
            custom_subject=subject,
            custom_body=body,
            attachments=attachments,
        )
        if ok:
            st.success("Brouillon ASF Interne créé dans Outlook.")
        else:
            st.error("Échec de création du mail ASF.")
