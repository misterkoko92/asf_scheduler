# email_expediteurs_handler.py — Communication 3.0
# --------------------------------------------------
# Génère des mails par couple (Expéditeur, Destination).
#
# - To / CC : paramexpediteur (ParamExpediteur)
# - Coordonnées correspondant local : ParamDest
# - Tableau HTML commun (même que destinations)
# --------------------------------------------------

from pathlib import Path

import pandas as pd
from asf_app.ui.ui_communication.outlook import create_outlook_draft

from asf_app.ui.ui_communication.helpers_email_tables import build_comm_table_html
from asf_app.ui.ui_communication.pdf_attachments import (
    find_be_pdf_attachments,
    index_pdfs_by_be,
)



# --------------------------------------------------
# Sujet pour Expéditeur
# --------------------------------------------------
def build_subject_expediteur(expediteur: str, dest_ville: str, week: int) -> str:
    """
    Sujet : "Expéditeur" / Expédition BRAZZAVILLE / Semaine 46
    """
    e = str(expediteur).strip()
    d = str(dest_ville).strip().upper()
    return f"{e} / Expédition {d} / Semaine {week}"


# --------------------------------------------------
# Corps par défaut pour Expéditeur
# --------------------------------------------------
DEFAULT_BODY_EXPEDITEUR = (
    "Bonjour,<br><br>"
    "Nous tenons à vous informer des livraisons prévues la semaine prochaine pour vos colis :<br><br>"
    "{table_html}<br><br>"
    "Pouvez-vous demander à votre structure sur place de prendre contact avec notre correspondant "
    "afin d'organiser le transfert des colis ?<br><br>"
    "Coordonnées de notre correspondant :<br>{coord_correspondant}<br><br>"
    "Merci pour votre confiance.<br><br>"
    "Cordialement,<br><br>"
    "Edouard<br>"
)


# --------------------------------------------------
# ParamExpediteur : emails
# --------------------------------------------------
def _get_emails_for_expediteur(df_paramexpediteur: pd.DataFrame, expediteur: str):
    """
    Retourne (to_list, cc_list) pour un expéditeur donné
    via ParamExpediteur.
    """
    if df_paramexpediteur is None or df_paramexpediteur.empty:
        return [], []

    exp_up = str(expediteur).strip().upper()
    df = df_paramexpediteur.copy()
    df["Expediteur_UP"] = df["Expediteur_Nom"].astype(str).str.strip().str.upper()

    row = df[df["Expediteur_UP"] == exp_up]
    if row.empty:
        return [], []

    r0 = row.iloc[0]
    to_raw = str(r0.get("Expediteur_Email", "") or "")
    cc_raw = str(r0.get("Expediteur_Copie", "") or "")

    return to_raw, cc_raw


# --------------------------------------------------
# ParamDest : correspondant local pour une destination
# --------------------------------------------------
def _get_correspondant_for_destination(df_paramdest: pd.DataFrame, dest_ville: str) -> str:
    """
    Construit la chaîne :
    "Mr Titre Prénom NOM / email / tel1 [/ tel2] [/ tel3]"
    à partir de ParamDest.
    """
    if df_paramdest is None or df_paramdest.empty:
        return ""

    dest_up = str(dest_ville).strip().upper()
    df = df_paramdest.copy()
    df["Dest_Ville_UP"] = df["Dest_Ville"].astype(str).str.strip().str.upper()

    row = df[df["Dest_Ville_UP"] == dest_up]
    if row.empty:
        return ""

    r0 = row.iloc[0]
    titre = str(r0.get("Contact_Titre", "") or "").strip()
    prenom = str(r0.get("Contact_Prenom", "") or "").strip()
    nom = str(r0.get("Contact_Nom", "") or "").strip().upper()
    email = str(r0.get("Contact_Email", "") or "").strip()
    tel1 = str(r0.get("Contact_Tel1", "") or "").strip()
    tel2 = str(r0.get("Contact_Tel2", "") or "").strip()
    tel3 = str(r0.get("Contact_Tel3", "") or "").strip()

    parts = []

    ident = " ".join(p for p in [titre, prenom, nom] if p)
    if ident:
        parts.append(ident)
    if email:
        parts.append(email)
    if tel1:
        parts.append(tel1)
    if tel2:
        parts.append(tel2)
    if tel3:
        parts.append(tel3)

    return " / ".join(parts)


# --------------------------------------------------
# Mail pour UN couple (Expéditeur, Destination)
# --------------------------------------------------
def generate_expediteur_email_for_pair(
    df_comm: pd.DataFrame,
    df_paramdest: pd.DataFrame,
    df_paramexpediteur: pd.DataFrame,
    expediteur: str,
    destination: str,
    week: int,
    year: int,
    custom_subject: str | None = None,
    custom_body: str | None = None,
    pdf_index: dict[str, list[Path]] | None = None,
):
    """
    Génère un mail brouillon pour un couple (Expéditeur, Destination),
    contenant uniquement les colis de cet expéditeur vers cette destination.
    """

    if df_comm is None or df_comm.empty:
        return False

    exp_up = str(expediteur).strip().upper()
    dest_up = str(destination).strip().upper()

    df_subset = df_comm[
        (df_comm["Expediteur"].str.upper() == exp_up) &
        (df_comm["Destination"].str.upper() == dest_up)
    ].copy()

    if df_subset.empty:
        print(f"[Expéditeurs] Aucun colis pour {expediteur} vers {destination}")
        # On permet quand même la création du mail pour édition manuelle
        table_html = "<p><i>Aucun colis cette semaine.</i></p>"
    else:
        table_html = build_comm_table_html(df_subset)

    # Emails ParamExpediteur
    to_list, cc_list = _get_emails_for_expediteur(df_paramexpediteur, expediteur)

    # Sujet
    subject = custom_subject or build_subject_expediteur(expediteur, destination, week)

    # Coordonnées correspondant local (ParamDest)
    coord_corr = _get_correspondant_for_destination(df_paramdest, destination)

    # Corps
    body = custom_body or DEFAULT_BODY_EXPEDITEUR.format(
        table_html=table_html,
        coord_correspondant=coord_corr
    )

    attachments = find_be_pdf_attachments(df_subset, pdf_index=pdf_index)

    # Création du brouillon Outlook
    result = create_outlook_draft(
        to_list=to_list,
        cc_list=cc_list,
        bcc_list=None,
        subject=subject,
        body_html=body,
        attachments=attachments or None,
        use_signature=True
    )

    return result


# --------------------------------------------------
# Mail pour TOUS les couples (Expéditeur != ASF, Destination)
# --------------------------------------------------
def generate_all_expediteurs_emails(
    df_comm: pd.DataFrame,
    df_paramdest: pd.DataFrame,
    df_paramexpediteur: pd.DataFrame,
    week: int,
    year: int,
):
    """
    Parcourt tous les couples (Expéditeur != ASF, Destination) présents
    dans df_comm et génère un mail par couple.
    """

    if df_comm is None or df_comm.empty:
        return 0

    df_filtered = df_comm.copy()
    df_filtered["Expediteur_UP"] = df_filtered["Expediteur"].astype(str).str.strip().str.upper()
    df_filtered["Destination_UP"] = df_filtered["Destination"].astype(str).str.strip().str.upper()

    # Exclure ASF
    df_filtered = df_filtered[df_filtered["Expediteur_UP"] != "ASF"]

    pairs = (
        df_filtered[["Expediteur_UP", "Destination_UP"]]
        .drop_duplicates()
        .itertuples(index=False, name=None)
    )

    pdf_index = index_pdfs_by_be()
    count = 0
    for exp_up, dest_up in pairs:
        # récupérer labels originaux (tels qu'affichés dans df_comm)
        exp_label = df_filtered[df_filtered["Expediteur_UP"] == exp_up]["Expediteur"].iloc[0]
        dest_label = df_filtered[df_filtered["Destination_UP"] == dest_up]["Destination"].iloc[0]

        ok = generate_expediteur_email_for_pair(
            df_comm=df_comm,
            df_paramdest=df_paramdest,
            df_paramexpediteur=df_paramexpediteur,
            expediteur=exp_label,
            destination=dest_label,
            week=week,
            year=year,
            pdf_index=pdf_index,
        )
        if ok:
            count += 1

    return count
