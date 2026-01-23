# email_asf_handler.py — Version Communication 3.0
# --------------------------------------------------------
# Génère un email ASF Interne en brouillon dans Outlook,
# compatible Windows (COM) et macOS (AppleScript),
# avec signature automatique.
#
# Le texte, le sujet, les adresses TO/CC/BCC sont fournis par l’UI.
# --------------------------------------------------------

from asf_app.ui.ui_communication.outlook import create_outlook_draft



# --------------------------------------------------------
# Sujet dynamique basé sur la semaine et l'année
# --------------------------------------------------------
def build_subject_asf(week: int, year: int) -> str:
    return f"Planning SEMAINE {week} - {year}"


# --------------------------------------------------------
# Corps du mail ASF Interne (par défaut)
# --------------------------------------------------------
DEFAULT_BODY_ASF = (
    "Bonjour à tous,<br><br>"
    "J'espère que vous allez bien !<br><br>"
    "Voici en pièce jointe le planning de la semaine {week}.<br><br>"
    "Bonne journée à tous,<br>"
    "Edouard<br>"
)


# --------------------------------------------------------
# Fonction principale
# --------------------------------------------------------
def generate_asf_email(
    to_list,
    bcc_list,
    week,
    year,
    custom_subject=None,
    custom_body=None,
    attachments=None,
    cc_list=None,
):
    """
    to_list : liste des adresses email destinataires
    bcc_list : liste BCC
    cc_list : liste CC (optionnel)
    week : numéro de semaine
    year : année
    custom_subject : sujet custom si fourni par l'UI
    custom_body : corps HTML custom si fourni par l'UI
    """

    # Sujet final
    subject = custom_subject or build_subject_asf(week, year)

    # Corps HTML final
    body = custom_body or DEFAULT_BODY_ASF.format(week=week)

    # ----------------------------------------------------
    # Délégation à outlook.py (cross-platform)
    # ----------------------------------------------------
    result = create_outlook_draft(
        to_list=to_list,
        cc_list=cc_list,
        bcc_list=bcc_list,
        subject=subject,
        body_html=body,
        attachments=attachments or None,
        use_signature=True       # ⚠ insère signature Outlook auto
    )

    return result
