# asf_app/utils_mail_expediteurs.py
# -*- coding: utf-8 -*-

import pandas as pd
from datetime import datetime
from asf_app.utils_outlook import create_outlook_draft


# -------------------------------------------------------------
# Convertir valeurs vers string safe
# -------------------------------------------------------------
def safe(v):
    if pd.isna(v):
        return ""
    return str(v).strip()


# -------------------------------------------------------------
# TABLEAU HTML (ville au lieu du code)
# -------------------------------------------------------------
def build_html_table(df_exp):

    html = """
    <table cellspacing="0" cellpadding="4"
           style="border-collapse:collapse; font-family:Aptos, Arial, sans-serif; font-size:12pt; border:1px solid #000;">
        <tr style="font-weight:bold; background-color:#e8e8e8;">
            <td style="border:1px solid #000;">Date</td>
            <td style="border:1px solid #000;">Destination</td>
            <td style="border:1px solid #000;">N° Vol</td>
            <td style="border:1px solid #000;">N° BE</td>
            <td style="border:1px solid #000;">Nb colis</td>
            <td style="border:1px solid #000;">Type colis</td>
            <td style="border:1px solid #000;">Expéditeur</td>
            <td style="border:1px solid #000;">Destinataire</td>
        </tr>
    """

    for _, row in df_exp.iterrows():

        try:
            d = pd.to_datetime(row["Date_Vol"])
            date_txt = d.strftime("%d/%m/%Y")
        except:
            date_txt = safe(row["Date_Vol"])

        html += f"""
        <tr>
            <td style="border:1px solid #000;">{date_txt}</td>
            <td style="border:1px solid #000;">{row['Destination_Nom']}</td>
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
# Corps HTML du mail expéditeur
# -------------------------------------------------------------
def build_mail_body_expediteur(expediteur, df_exp, correspondant):

    table_html = build_html_table(df_exp)

    # Contact correspondant formaté
    contact = " / ".join([
        safe(correspondant.get("Titre", "")),
        safe(correspondant.get("Prenom", "")),
        safe(correspondant.get("Nom", "")),
        safe(correspondant.get("Mail", "")),
        safe(correspondant.get("Tel1", "")),
        safe(correspondant.get("Tel2", "")),
        safe(correspondant.get("Tel3", "")),
    ]).replace(" /  /", " / ").replace("//", "/")

    # Ville (Destination_Nom)
    ville = df_exp["Destination_Nom"].iloc[0]

    html = f"""
    <div style="font-family:Aptos, Arial, sans-serif; font-size:12pt;">
    Bonjour,<br><br>

    Nous tenons à vous informer des livraisons prévues la semaine prochaine pour vos colis :<br><br>

    {table_html}

    <br><br>
    Pouvez-vous demander à votre structure sur place de prendre contact avec notre correspondant afin d'organiser le transfert des colis ?<br><br>

    <b>Coordonnées du correspondant :</b><br>
    {contact}<br><br>

    Merci pour votre confiance.<br>
    </div>
    """
    return html


# -------------------------------------------------------------
# ENVOYER 1 MAIL EXPÉDITEUR
# -------------------------------------------------------------
def envoyer_mail_expediteur(df_clean, param_exp_df, param_dest_df, expediteur):

    bloc = df_clean[df_clean["BE_Expediteur"] == expediteur]

    if bloc.empty:
        return False

    # Ville (Destination_Nom)
    ville = bloc["Destination_Nom"].iloc[0]

    # Semaine
    try:
        week = pd.to_datetime(bloc["Date_Vol"]).dt.isocalendar().week.iloc[0]
    except:
        week = ""

    # Correspondant (via ParamDest)
    dest = bloc["Destination"].iloc[0]
    row_dest = param_dest_df[param_dest_df["Destination"] == dest]

    correspondant = {
        "Titre": safe(row_dest["Titre"].iloc[0]) if "Titre" in row_dest else "",
        "Nom": safe(row_dest["Nom"].iloc[0]) if "Nom" in row_dest else "",
        "Prenom": safe(row_dest["Prénom"].iloc[0]) if "Prénom" in row_dest else "",
        "Mail": safe(row_dest["Mail"].iloc[0]) if "Mail" in row_dest else "",
        "Tel1": safe(row_dest["Telephone 1"].iloc[0]) if "Telephone 1" in row_dest else "",
        "Tel2": safe(row_dest["Telephone 2"].iloc[0]) if "Telephone 2" in row_dest else "",
        "Tel3": safe(row_dest["Telephone 3"].iloc[0]) if "Telephone 3" in row_dest else "",
    }

    # ParamExpediteur
    row_exp = param_exp_df[param_exp_df["Association"] == expediteur]

    to = safe(row_exp["Mail ASSO"].iloc[0]) if not row_exp.empty else ""
    cc = safe(row_exp["Mail ASSO COPIE"].iloc[0]) if not row_exp.empty else ""

    # Multi-adresses propre
    to = "; ".join([a.strip() for a in to.split(";") if a.strip()])
    cc = "; ".join([a.strip() for a in cc.split(";") if a.strip()])

    # Sujet AVEC NOM DE LA VILLE
    subject = f"{expediteur} / Expédition {ville} / Semaine {week}"

    body = build_mail_body_expediteur(expediteur, bloc, correspondant)

    create_outlook_draft(to, cc, subject, body)

    return True


# -------------------------------------------------------------
# ENVOYER MAILS À TOUS LES EXPÉDITEURS (sauf ASF)
# -------------------------------------------------------------
def envoyer_mails_expediteurs_tous(df_clean, param_exp_df, param_dest_df):

    expediteurs = df_clean["BE_Expediteur"].dropna().unique()

    for exp in expediteurs:
        if str(exp).strip().upper() == "ASF":
            continue

        envoyer_mail_expediteur(df_clean, param_exp_df, param_dest_df, exp)

    return True
