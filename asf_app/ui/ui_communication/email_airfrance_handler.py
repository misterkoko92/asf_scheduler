# email_airfrance_handler.py — Version Communication 3.0
# --------------------------------------------------------
# Génère un email Air France en brouillon dans Outlook,
# compatible Windows (COM) et macOS (AppleScript),
# avec signature automatique Outlook.
#
# Le texte, le sujet, les adresses TO/CC/BCC sont fournis par l’UI.
# --------------------------------------------------------

from asf_app.ui.ui_communication.outlook import create_outlook_draft


# --------------------------------------------------------
# Sujet dynamique basé sur la semaine
# --------------------------------------------------------
def build_subject_airfrance(week: int, year: int) -> str:
    return f"Aviation Sans Frontires / Planning S{week}"


# --------------------------------------------------------
# Corps du mail Air France (valeurs par défaut)
# --------------------------------------------------------
DEFAULT_BODY_AIRFRANCE = (
    "Bonjour,<br><br>"
    "Comme convenu, veuillez trouver ci-joint notre planning des expéditions prévues pour la semaine {week}.<br>"
    "Nous vous tiendrons informés en cas de mise à jour le cas échéant.<br><br>"
    "Encore merci à tous pour votre aide,<br><br>"
    "Cordialement,<br>"
    "Edouard<br>"
)


# --------------------------------------------------------
# Fonction principale
# --------------------------------------------------------
def generate_airfrance_email(
    to_list,
    cc_list,
    week,
    year,
    bcc_list=None,
    custom_subject=None,
    custom_body=None,
    attachments=None,
):
    """
    to_list : liste d’adresses email
    cc_list : liste d’adresses email
    week    : numéro de semaine (int)
    year    : année (int)
    bcc_list : liste d’adresses email
    custom_subject : sujet custom, sinon sujet par défaut
    custom_body    : corps HTML custom, sinon texte par défaut
    """

    # Sujet final
    subject = custom_subject or build_subject_airfrance(week, year)

    # Corps final (HTML léger)
    body = custom_body or DEFAULT_BODY_AIRFRANCE.format(week=week)

    # ----------------------------------------------------
    # On délègue à outlook.py (cross-platform)
    # ----------------------------------------------------
    result = create_outlook_draft(
        to_list=to_list,
        cc_list=cc_list,
        bcc_list=bcc_list,
        subject=subject,
        body_html=body,
        attachments=attachments or None,
        use_signature=True       # ⚠ force la signature Outlook
    )

    return result
