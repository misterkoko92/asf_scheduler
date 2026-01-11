# email_destinations_handler.py — Communication 3.0
# --------------------------------------------------
# Génère un mail par destination, contenant uniquement
# les colis pour cette destination, avec tableau HTML.
#
# Utilise :
# - df_comm (planning communication)
# - df_paramdest (ParamDest normalisé)
# - outlook.create_outlook_draft()
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
# Sujet pour Destination
# --------------------------------------------------
def build_subject_destination(dest_ville: str, week: int) -> str:
    """
    Sujet : ASF / Expédition BRAZZAVILLE / Semaine 46
    """
    dest_ville = str(dest_ville).upper()
    return f"ASF / Expédition {dest_ville} / Semaine {week}"


# --------------------------------------------------
# Corps par défaut pour Destination
# --------------------------------------------------
DEFAULT_BODY_DEST = (
    "Bonjour,<br><br>"
    "J'espère que vous allez bien.<br><br>"
    "Voici les informations d'expédition pour la destination : {destination}.<br><br>"
    "{table_html}<br><br>"
    "Cordialement,<br><br>"
    "Edouard<br>"
)


# --------------------------------------------------
# Récupération emails ParamDest pour une destination
# --------------------------------------------------
def _get_emails_for_destination(df_paramdest: pd.DataFrame, dest_ville: str):
    """
    Retourne (to_list, cc_list) pour une destination donnée,
    en se basant sur les colonnes Contact_Email & Contact_Copie.
    """
    if df_paramdest is None or df_paramdest.empty:
        return [], []

    dest_ville_up = str(dest_ville).strip().upper()
    df = df_paramdest.copy()
    df["Dest_Ville_UP"] = df["Dest_Ville"].astype(str).str.strip().str.upper()
    df["Dest_IATA_UP"] = df["Dest_IATA"].astype(str).str.strip().str.upper() if "Dest_IATA" in df.columns else ""

    # 1) Match ville exacte
    row = df[df["Dest_Ville_UP"] == dest_ville_up]
    # 2) Match IATA exacte si len == 3
    if row.empty and len(dest_ville_up) == 3:
        row = df[df["Dest_IATA_UP"] == dest_ville_up]
    # 3) Match contient IATA dans routing (tolérance)
    if row.empty and len(dest_ville_up) == 3:
        row = df[df["Dest_IATA_UP"].str.contains(dest_ville_up, na=False)]
    # 4) Match contient ville
    if row.empty:
        row = df[df["Dest_Ville_UP"].str.contains(dest_ville_up, na=False)]
    if row.empty:
        return [], []

    r0 = row.iloc[0]
    to_raw = str(r0.get("Contact_Email", "") or "")
    cc_raw = str(r0.get("Contact_Copie", "") or "")

    # Laisse outlook._clean_list gérer le parsing ("," ";" etc.),
    # en passant simplement les strings.
    return to_raw, cc_raw


# --------------------------------------------------
# Mail pour UNE destination
# --------------------------------------------------
def generate_destination_email_for_destination(
    df_comm: pd.DataFrame,
    df_paramdest: pd.DataFrame,
    destination: str,
    week: int,
    year: int,
    custom_subject: str | None = None,
    custom_body: str | None = None,
    pdf_index: dict[str, list[Path]] | None = None,
):
    """
    Génère un mail en brouillon pour une destination donnée,
    contenant uniquement les colis de cette destination.
    """

    if df_comm is None or df_comm.empty:
        return False

    dest_up = str(destination).strip().upper()
    df_subset = df_comm[df_comm["Destination"].str.upper() == dest_up].copy()

    if df_subset.empty:
        print(f"[Destinations] Aucun colis pour {destination}")
        return False

    # Emails ParamDest
    to_list, cc_list = _get_emails_for_destination(df_paramdest, dest_up)
    if not to_list:
        print(f"[Destinations] Aucun email 'To' trouvé pour {destination}")
        return False

    # Sujet
    subject = custom_subject or build_subject_destination(dest_up, week)

    # Tableau HTML
    table_html = build_comm_table_html(df_subset)

    # Corps
    body = custom_body or DEFAULT_BODY_DEST.format(
        destination=dest_up,
        table_html=table_html
    )

    attachments = find_be_pdf_attachments(df_subset, pdf_index=pdf_index)

    # Envoi brouillon Outlook
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
# Mail pour TOUTES les destinations présentes dans df_comm
# --------------------------------------------------
def generate_all_destination_emails(
    df_comm: pd.DataFrame,
    df_paramdest: pd.DataFrame,
    week: int,
    year: int,
):
    """
    Parcourt toutes les destinations présentes dans df_comm
    et génère un mail par destination.
    """
    if df_comm is None or df_comm.empty:
        return 0

    destinations = (
        df_comm["Destination"]
        .dropna()
        .astype(str)
        .str.strip()
        .str.upper()
        .unique()
    )

    pdf_index = index_pdfs_by_be()
    count = 0
    for dest in destinations:
        ok = generate_destination_email_for_destination(
            df_comm=df_comm,
            df_paramdest=df_paramdest,
            destination=dest,
            week=week,
            year=year,
            pdf_index=pdf_index,
        )
        if ok:
            count += 1

    return count
