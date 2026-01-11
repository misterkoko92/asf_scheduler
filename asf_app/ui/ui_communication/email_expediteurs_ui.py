# email_expediteurs_ui.py — Communication 3.0
# ------------------------------------------
# UI pour les mails Expéditeurs :
# - Un bouton "Générer tous les mails Expéditeurs"
# - Un bouton par expéditeur (génère tous ses mails par destination)

import streamlit as st
import pandas as pd

from asf_app.ui.ui_communication.email_expediteurs_handler import (
    generate_expediteur_email_for_pair,
    generate_all_expediteurs_emails,
    build_subject_expediteur,
    DEFAULT_BODY_EXPEDITEUR,
)
from asf_app.ui.ui_communication.pdf_attachments import index_pdfs_by_be
from asf_app.ui.ui_planning.state_planning import get_planning_state

def render_email_expediteurs_ui(
    df_comm: pd.DataFrame,
    df_paramdest: pd.DataFrame,
    df_paramexpediteur: pd.DataFrame,
    week: int,
    year: int,
):
    st.subheader("📦 Mails Expéditeurs")

    if df_comm is None or df_comm.empty:
        st.info("Aucun planning communication chargé.")
        return

    if df_paramexpediteur is None or df_paramexpediteur.empty:
        st.warning("ParamExpediteur non chargé.")
        return

    df = df_comm.copy()
    df["Expediteur_UP"] = df["Expediteur"].astype(str).str.strip().str.upper()

    # Exclure ASF
    df = df[df["Expediteur_UP"] != "ASF"]

    if df.empty:
        st.info("Aucun expéditeur externe trouvé (hors ASF).")
        return

    exp_list = (
        df[["Expediteur", "Expediteur_UP"]]
        .drop_duplicates()
        .sort_values("Expediteur")
        .to_records(index=False)
    )

    st.markdown(
        f"**Expéditeurs détectés (hors ASF) :** "
        + ", ".join(str(e[0]) for e in exp_list)
    )

    # Bouton global
    if st.button("📤 Générer tous les mails Expéditeurs", type="primary"):
        nb = generate_all_expediteurs_emails(
            df_comm=df_comm,
            df_paramdest=df_paramdest,
            df_paramexpediteur=df_paramexpediteur,
            week=week,
            year=year,
        )
        st.success(f"{nb} mails Expéditeurs générés (brouillons Outlook).")

    st.divider()

    # Sélection d'un expéditeur pour envoi ciblé
    exp_noms = [e[0] for e in exp_list]
    exp_selected = st.selectbox(
        "Sélectionner un expéditeur pour un envoi ciblé (toutes ses destinations)",
        options=exp_noms
    )

    if exp_selected:
        # Destinations pour cet expéditeur
        df_exp = df[df["Expediteur"] == exp_selected]
        dests = (
            df_exp["Destination"]
            .dropna()
            .astype(str)
            .str.strip()
            .str.upper()
            .unique()
        )

        st.markdown(
            f"**Destinations pour {exp_selected} :** " + ", ".join(dests)
        )

        # Preview sujet / corps générique (sans tableau)
        # On prend la première destination pour l'example
        dest0 = dests[0] if len(dests) > 0 else ""
        subj_preview = build_subject_expediteur(exp_selected, dest0 or "DESTINATION", week)
        body_preview = DEFAULT_BODY_EXPEDITEUR.format(
            table_html="...",
            coord_correspondant="Mr Titre Prénom NOM / email / +tel"
        )
        st.text_input("Sujet (preview)", value=subj_preview, key="exp_subj_preview")
        st.text_area("Corps (preview, sans tableau)", value=body_preview, height=140, key="exp_body_preview")

        if st.button(f"📤 Générer les mails pour {exp_selected}", type="primary"):
            # On génère un mail par destination de cet expéditeur
            count = 0
            pdf_index = index_pdfs_by_be()
            for dest in dests:
                ok = generate_expediteur_email_for_pair(
                    df_comm=df_comm,
                    df_paramdest=df_paramdest,
                    df_paramexpediteur=df_paramexpediteur,
                    expediteur=exp_selected,
                    destination=dest,
                    week=week,
                    year=year,
                    pdf_index=pdf_index,
                )
                if ok:
                    count += 1

            st.success(f"{count} mails générés pour {exp_selected}.")
