# email_destinations_ui.py — Communication 3.0
# -------------------------------------------
# UI pour les mails par Destination :
# - Liste des destinations trouvées dans df_comm
# - Bouton "Générer tous les mails"
# - Bouton "Générer pour cette destination"

import pandas as pd
import streamlit as st

from asf_app.ui.ui_communication.email_destinations_handler import (
    DEFAULT_BODY_DEST,
    build_subject_destination,
    generate_all_destination_emails,
    generate_destination_email_for_destination,
)


def render_email_destinations_ui(
    df_comm: pd.DataFrame,
    df_paramdest: pd.DataFrame,
    week: int,
    year: int,
):
    st.subheader("📍 Mails Destinations")

    if df_comm is None or df_comm.empty:
        st.info("Aucun planning communication chargé.")
        return

    if df_paramdest is None or df_paramdest.empty:
        st.warning("ParamDest non chargé.")
        return

    destinations = (
        df_comm["Destination"]
        .dropna()
        .astype(str)
        .str.strip()
        .str.upper()
        .unique()
    )

    if len(destinations) == 0:
        st.info("Aucune destination trouvée dans le planning.")
        return

    st.markdown(f"**Destinations détectées :** {', '.join(destinations)}")

    # Bouton global
    if st.button("📤 Générer les mails pour toutes les destinations", type="primary"):
        nb = generate_all_destination_emails(
            df_comm=df_comm,
            df_paramdest=df_paramdest,
            week=week,
            year=year,
        )
        st.success(f"{nb} mails Destinations générés (brouillons Outlook).")

    st.divider()

    # Sélection individuelle
    dest_selected = st.selectbox(
        "Sélectionner une destination pour un envoi individuel",
        options=sorted(destinations)
    )

    if dest_selected:
        # Prévisualisation sujet / corps par défaut
        subject_default = build_subject_destination(dest_selected, week)
        body_default = DEFAULT_BODY_DEST.format(
            destination=dest_selected,
            table_html="..."
        )

        st.text_input("Sujet (preview)", value=subject_default, key="dest_subj_preview")
        st.text_area("Corps (preview, sans tableau)", value=body_default, height=120, key="dest_body_preview")

        if st.button(f"📤 Générer le mail pour {dest_selected}", type="primary"):
            ok = generate_destination_email_for_destination(
                df_comm=df_comm,
                df_paramdest=df_paramdest,
                destination=dest_selected,
                week=week,
                year=year,
            )
            if ok:
                st.success(f"Mail Destination pour {dest_selected} généré.")
            else:
                st.error(f"Échec pour la destination {dest_selected}.")
