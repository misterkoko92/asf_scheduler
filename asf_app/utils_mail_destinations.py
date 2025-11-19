# asf_app/utils_mail_destinations.py
# -*- coding: utf-8 -*-

import pandas as pd
from datetime import datetime
from asf_app.utils_outlook import create_outlook_draft


# -------------------------------------------------------------
# TABLEAU HTML AVEC BORDURES (Aptos 12)
# -------------------------------------------------------------
def build_html_table(df_dest):

    html = """
    <table cellspacing="0" cellpadding="4"
           style="
               border-collapse:collapse;
               table-layout:fixed;
               width:760px;
               font-family:Aptos, Arial, sans-serif;
               font-size:12pt;
               border:1px solid #000;
           ">
        <colgroup>
            <col style="width:90px;">
            <col style="width:130px;">
            <col style="width:75px;">
            <col style="width:85px;">
            <col style="width:100px;">
            <col style="width:110px;">
            <col style="width:140px;">
            <col style="width:140px;">
        </colgroup>

        <tr style="font-weight:bold; background-color:#e8e8e8; height:28px;">
            <td style="border:1px solid #000;">Date</td>
            <td style="border:1px solid #000;">Destination</td>
            <td style="border:1px solid #000;">N° Vol</td>
            <td style="border:1px solid #000;">N° BE</td>
            <td style="border:1px solid #000;">Colis</td>
            <td style="border:1px solid #000;">Type</td>
            <td style="border:1px solid #000;">Expéditeur</td>
            <td style="border:1px solid #000;">Destinataire</td>
        </tr>
    """

    for _, row in df_dest.iterrows():

        date_val = pd.to_datetime(row["Date_Vol"], errors="coerce")
        date_txt = date_val.strftime("%d/%m/%Y") if not pd.isna(date_val) else ""

        html += f"""
        <tr style="height:22px; white-space:nowrap;">
            <td style="border:1px solid #000;">{date_txt}</td>
            <td style="border:1px solid #000;">{row['Destination']}</td>
            <td style="border:1px solid #000;">{row['Vol']}</td>
            <td style="border:1px solid #000;">{row['BE_Numero']}</td>
            <td style="border:1px solid #000;">{row['BE_Nb_Colis']}</td>
            <td style="border:1px solid #000;">{row['BE_Type']}</td>
            <td style="border:1px solid #000;">{row['BE_Expediteur']}</td>
            <td style="border:1px solid #000;">{row['BE_Destinataire']}</td>
        </tr>
        """

    html += "</table>"
    return html



# -------------------------------------------------------------
# CORPS HTML DU MAIL
# -------------------------------------------------------------
def build_mail_body_destination(dest_name, df_dest):
    table = build_html_table(df_dest)

    html = f"""
    <div style="font-family:Aptos, Arial, sans-serif; font-size:12pt;">
    Bonjour,<br><br>

    J'espère que vous allez bien.<br><br>

    Voici les informations d'expédition pour la destination : 
    <b>{dest_name}</b><br><br>

    {table}

    <br><br>
    Cordialement,
    </div>
    """
    return html


# -------------------------------------------------------------
# ENVOYER 1 MAIL POUR UNE DEST
# -------------------------------------------------------------
def envoyer_mail_destination(df_clean, paramdest_df, dest_code):

    bloc = df_clean[df_clean["Destination"] == dest_code]
    if bloc.empty:
        return False

    bloc = bloc.copy()
    bloc["Date_Vol"] = pd.to_datetime(bloc["Date_Vol"], errors="coerce")

    dest_name = bloc["Destination_Nom"].iloc[0]

    # extraction semaine ISO
    week = bloc["Date_Vol"].dt.isocalendar().week.iloc[0]

    row = paramdest_df[paramdest_df["Destination"] == dest_code]

    def clean_mails(x):
        if not isinstance(x, str):
            return ""
        parts = [p.strip() for p in x.split(";") if p.strip()]
        return "; ".join(parts)

    to = clean_mails(row["Mail"].iloc[0]) if "Mail" in row else ""
    cc = clean_mails(row["Copie"].iloc[0]) if "Copie" in row else ""

    subject = f"ASF / Expédition {dest_name.upper()} / Semaine {week}"
    body = build_mail_body_destination(dest_name, bloc)

    create_outlook_draft(to, cc, subject, body)

    return True


# -------------------------------------------------------------
# ENVOYER POUR TOUTES LES DESTINATIONS
# -------------------------------------------------------------
def envoyer_mails_destinations_tous(df_clean, paramdest_df):
    for dest in df_clean["Destination"].unique():
        envoyer_mail_destination(df_clean, paramdest_df, dest)
    return True
