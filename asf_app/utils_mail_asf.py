# asf_app/utils_mail_asf.py
# -*- coding: utf-8 -*-

from asf_app.utils_outlook import create_outlook_draft


def build_mail_asf_body(week):
    return f"""
    <div style="font-family:Aptos, Arial, sans-serif; font-size:12pt;">
    Bonjour à tous,<br><br>

    J'espère que vous allez bien !<br><br>

    Voici le planning de la semaine {week}.<br><br>

    Bonne journée à tous,<br>
    Edouard
    </div>
    """


def envoyer_mail_asf(to, bcc, week):
    subject = f"Planning SEMAINE {week} - 2025"
    body = build_mail_asf_body(week)

    # Utilise la fonction standard (pas de pièce jointe)
    create_outlook_draft(
        to=to,
        cc=bcc,      # On met la CCI dans CC car la fonction d’origine ne gère pas BCC
        subject=subject,
        html_body=body
    )

    return True
