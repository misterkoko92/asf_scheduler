# asf_app/ui_communication.py
# -*- coding: utf-8 -*-

import streamlit as st
import pandas as pd
from datetime import datetime
import streamlit.components.v1 as components
from pathlib import Path

from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Image, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm

from scheduler.config_paths import (
    TABLEAU_DE_BORD,
    PLANNING_BENEVOLES,
    SHEET_MAG_CENTRAL,
    SHEET_PARAM_DEST,
    SHEET_PARAM_EXP,
    OUTPUT_DIR,
    LOGO_HORIZONTAL,
)

# CLEAN + EXPORT
from asf_app.utils_clean_planning import clean_planning_df
from asf_app.utils_export_planning import export_planning_from_template

# WhatsApp
from asf_app.utils_whatsapp import construire_message_whatsapp, generer_url_whatsapp

# Mails
from asf_app.utils_mail_destinations import envoyer_mail_destination, envoyer_mails_destinations_tous
from asf_app.utils_mail_expediteurs import envoyer_mail_expediteur, envoyer_mails_expediteurs_tous
from asf_app.utils_mail_asf import envoyer_mail_asf



# ============================================================
#  PDF pour le mail ASF
# ============================================================
def generate_planning_pdf(df, file_path):

    pdf = SimpleDocTemplate(
        str(file_path),
        pagesize=A4,
        leftMargin=1.5*cm,
        rightMargin=1.5*cm,
        topMargin=1.5*cm,
        bottomMargin=1.5*cm
    )

    story = []

    if Path(LOGO_HORIZONTAL).exists():
        logo = Image(LOGO_HORIZONTAL, width=14*cm, height=3.5*cm)
        story.append(logo)
        story.append(Spacer(1, 0.5*cm))

    data = [list(df.columns)] + df.values.tolist()
    table = Table(data, repeatRows=1)

    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#e8e8e8")),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.black),
        ('BOX', (0, 0), (-1, -1), 0.50, colors.black)
    ]))

    story.append(table)
    pdf.build(story)



# ============================================================
# ONGLET COMMUNICATION
# ============================================================
def render_tab_communication():

    st.header("📣 Communications après validation du planning")

    if "planning_df" not in st.session_state or st.session_state.planning_df is None:
        st.warning("⚠️ Aucun planning détecté.")
        return

    # Chargement des tables sources
    be_df    = pd.read_excel(TABLEAU_DE_BORD, sheet_name=SHEET_MAG_CENTRAL, skiprows=5)
    benev_df = pd.read_excel(PLANNING_BENEVOLES, sheet_name="ParamBenev")
    dest_df  = pd.read_excel(TABLEAU_DE_BORD, sheet_name=SHEET_PARAM_DEST)
    exp_df   = pd.read_excel(TABLEAU_DE_BORD, sheet_name=SHEET_PARAM_EXP)

    # =======================================================
    # 1) NETTOYAGE / ENRICHISSEMENT
    # =======================================================
    st.subheader("🧹 Nettoyage & enrichissement")

    if st.button("🧹 Nettoyer & enrichir le planning", key="btn_clean"):
        planning_clean = clean_planning_df(
            st.session_state.planning_df,
            be_df=be_df,
            benev_df=benev_df,
            dest_df=dest_df,
        )
        st.session_state.planning_df_clean = planning_clean
        st.success("✔ Planning enrichi avec succès !")

    if "planning_df_clean" not in st.session_state:
        return

    df = st.session_state.planning_df_clean

    st.markdown("### 📋 Aperçu du planning enrichi")
    st.dataframe(df, use_container_width=True)



    # =======================================================
    # 2) EXPORT VIA MAQUETTE (NOUVEAU)
    # =======================================================
    st.subheader("📄 Générer le planning final (maquette ASF)")

    if st.button("📥 Générer le planning (.xlsx)", key="btn_export_template"):

        try:
            week = pd.to_datetime(df["Date_Vol"].iloc[0]).isocalendar().week
        except Exception:
            week = None

        week_label = f"{int(week):02d}" if week else "XX"

        # ---- NOUVEAU EXPORT ----
        filename = f"ASFmm - PLANNING SEMAINE N° {week_label} - 2025.xlsx"
        export_path = OUTPUT_DIR / filename

        # Détermination du numéro de semaine (week_label = "47")
        try:
            week = int(week_label)
        except Exception:
            week = 0

        # Export via la maquette
        final_file = export_planning_from_template(df, week, 2025)


        st.success("✔ Planning généré via la maquette !")

        st.download_button(
            "⬇ Télécharger le fichier",
            data=open(final_file, "rb").read(),
            file_name=final_file.name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )



    st.divider()

    # =======================================================
    # 3) WHATSAPP
    # =======================================================
    st.subheader("📱 WhatsApp bénévoles")

    if "wa_sent" not in st.session_state:
        st.session_state.wa_sent = {}

    for bene in df["Benevole"].unique():

        bloc = df[df["Benevole"] == bene]
        tel = bloc["Tel"].iloc[0]

        if not tel:
            st.error(f"❌ {bene} : pas de téléphone")
            continue

        msg = construire_message_whatsapp(bene, bloc)
        url = generer_url_whatsapp(tel, msg)

        c1, c2 = st.columns([2, 3])

        with c1:
            if st.button(f"📤 WhatsApp → {bene}", key=f"wa_{bene}"):

                components.html(
                    f'<script>window.open("{url}", "_blank");</script>',
                    height=0, width=0
                )
                st.session_state.wa_sent[bene] = datetime.now()
                st.success(f"WhatsApp ouvert pour {bene}")

        with c2:
            if bene in st.session_state.wa_sent:
                dt = st.session_state.wa_sent[bene]
                st.markdown(
                    f"<span style='color:green;'>"
                    f"✓ Envoyé le {dt:%d/%m/%Y à %Hh%M}</span>",
                    unsafe_allow_html=True
                )

    st.divider()



    # =======================================================
    # 4) MAILS DESTINATIONS
    # =======================================================
    st.subheader("🌍 Mails Destinations")

    if st.button("📤 Générer tous les mails destinations"):
        envoyer_mails_destinations_tous(df, dest_df)
        st.success("✔ Tous les mails destinations créés")

    for dest in df["Destination"].unique():
        nom = df[df["Destination"] == dest]["Destination_Nom"].iloc[0]
        if st.button(f"📤 Mail destination {nom}", key=f"dest_{dest}"):
            envoyer_mail_destination(df, dest_df, dest)
            st.success(f"Mail créé pour {nom}")

    st.divider()



    # =======================================================
    # 5) MAILS EXPEDITEURS
    # =======================================================
    st.subheader("📦 Mails Expéditeurs externes")

    if st.button("📤 Générer tous les mails expéditeurs"):
        envoyer_mails_expediteurs_tous(df, exp_df, dest_df)
        st.success("✔ Tous les mails expéditeurs créés")

    for exp in df["BE_Expediteur"].dropna().unique():
        if str(exp).upper() == "ASF":
            continue
        if st.button(f"📤 Mail expéditeur : {exp}", key=f"exp_{exp}"):
            envoyer_mail_expediteur(df, exp_df, dest_df, exp)
            st.success(f"Mail expéditeur créé")

    st.divider()



    # =======================================================
    # 6) MAIL ASF INTERNE
    # =======================================================
    st.subheader("👥 Mail interne ASF")

    if "asf_to" not in st.session_state:
        st.session_state.asf_to = "messmed@aviation-sans-frontieres-fr.org"

    if "asf_cci" not in st.session_state:
        st.session_state.asf_cci = "tousmessmed@asf-fr.net"

    st.text_input("Destinataire :", key="asf_to")
    st.text_input("CCI :", key="asf_cci")

    if st.button("📤 Générer mail interne ASF"):
        try:
            week = pd.to_datetime(df["Date_Vol"].iloc[0]).isocalendar().week
        except:
            week = ""
        envoyer_mail_asf(st.session_state.asf_to, st.session_state.asf_cci, week)
        st.success("Mail interne ASF créé !")

    st.divider()



    # =======================================================
    # 7) MAIL AIR FRANCE
    # =======================================================
    st.subheader("✈️ Air France")

    if "af_to" not in st.session_state:
        st.session_state.af_to = "nafontaine1@airfrance.fr; anchanet@airfrance.fr"

    if "af_cc" not in st.session_state:
        st.session_state.af_cc = (
            "messmed@aviation-sans-frontieres-fr.org; "
            "f.cottence@samsic.aero; m.dorigny@gsf.fr; "
            "a.joyeux@gsf.fr; s.chadli@samsic.aero; pestarland@airfrance.fr"
        )

    st.text_input("Destinataire AF :", key="af_to")
    st.text_input("CC AF :", key="af_cc")

    if st.button("📤 Générer mail Air France"):

        try:
            week = pd.to_datetime(df["Date_Vol"].iloc[0]).isocalendar().week
        except:
            week = ""

        from asf_app.utils_mail_airfrance import envoyer_mail_airfrance
        envoyer_mail_airfrance(
            to=st.session_state.af_to,
            cc=st.session_state.af_cc,
            week=week
        )

        st.success("Mail Air France créé !")
