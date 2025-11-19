# asf_app/utils_mail_airfrance.py
# -*- coding: utf-8 -*-

from asf_app.utils_outlook import create_outlook_draft


# ---------------------------------------------------------
# Corps du mail Air France
# ---------------------------------------------------------
def build_mail_af_body(week):
    return f"""
    <div style="font-family:Aptos, Arial, sans-serif; font-size:12pt;">
    Bonjour,<br><br>

    Comme convenu, veuillez trouver ci-joint notre planning des expéditions prévues
    pour la semaine {week}.<br>
    Nous vous tiendrons informés en cas de mise à jour le cas échéant.<br><br>

    Encore merci à tous pour votre aide,<br><br>

    Cordialement,<br>
    Edouard
    </div>
    """


# ---------------------------------------------------------
# Envoi du mail Air France
# ---------------------------------------------------------
def envoyer_mail_airfrance(to, cc, week):
    subject = f"Aviation Sans Frontières / Planning S{week}"

    body = build_mail_af_body(week)

    create_outlook_draft(
        to=to,
        cc=cc,
        subject=subject,
        html_body=body
    )

    return True
