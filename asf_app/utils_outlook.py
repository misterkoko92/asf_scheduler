# asf_app/utils_outlook.py
# -*- coding: utf-8 -*-

import platform
import subprocess
import os


# ======================================================================
# OUTLOOK WINDOWS — avec ou sans pièce jointe
# ======================================================================
def outlook_create_draft_windows(to, cc, bcc, subject, html_body, attachment_path=None):
    import win32com.client

    outlook = win32com.client.Dispatch("Outlook.Application")
    mail = outlook.CreateItem(0)

    mail.To = to or ""
    mail.CC = cc or ""
    mail.BCC = bcc or ""
    mail.Subject = subject or ""
    mail.HTMLBody = html_body

    if attachment_path and os.path.isfile(attachment_path):
        mail.Attachments.Add(attachment_path)

    mail.Display()
    mail.Save()
    return True


# ======================================================================
# OUTLOOK MAC — gestion pièces jointes + multi-destinataires
# ======================================================================
def outlook_create_draft_mac(to, cc, bcc, subject, html_body, attachment_path=None):

    def split_mails(s):
        if not s:
            return []
        return [m.strip() for m in s.replace(",", ";").split(";") if m.strip()]

    to_list = split_mails(to)
    cc_list = split_mails(cc)
    bcc_list = split_mails(bcc)

    make_to = "\n".join(
        f'make new recipient at newMessage with properties {{email address:{{address:"{addr}"}}}}'
        for addr in to_list
    )

    make_cc = "\n".join(
        f'make new cc recipient at newMessage with properties {{email address:{{address:"{addr}"}}}}'
        for addr in cc_list
    )

    make_bcc = "\n".join(
        f'make new bcc recipient at newMessage with properties {{email address:{{address:"{addr}"}}}}'
        for addr in bcc_list
    )

    attach_code = ""
    if attachment_path and os.path.isfile(attachment_path):
        # on échappe guillemets et backslashes pour AppleScript
        safe_path = attachment_path.replace("\\", "\\\\").replace('"', '\\"')
        attach_code = f'make new attachment at newMessage with properties {{file:"{safe_path}"}}\n'

    # on échappe les guillemets dans le sujet / corps AVANT la f-string
    safe_subject = (subject or "").replace('"', '\\"')
    # pour le corps, on échappe aussi les guillemets ; tu peux ajouter d'autres remplacements si besoin
    safe_body = (html_body or "").replace('"', '\\"')

    script = f'''
    set theSubject to "{safe_subject}"
    set theContent to "{safe_body}"

    tell application "Microsoft Outlook"
        set newMessage to make new outgoing message with properties {{subject:theSubject}}

        set content of newMessage to theContent

        {make_to}
        {make_cc}
        {make_bcc}

        {attach_code}

        open newMessage
        activate
        save newMessage
    end tell
    '''

    subprocess.run(["osascript", "-e", script])
    return True


# ======================================================================
# API 1 : fonction historique (utilisée par destinataires & expéditeurs)
# ======================================================================
def create_outlook_draft(to, cc, subject, html_body):
    """
    Fonction utilisée dans :
    - utils_mail_destinations
    - utils_mail_expediteurs

    Redirigée vers la nouvelle API complète (sans pièce jointe).
    """
    return create_outlook_draft_with_attachment(
        to=to,
        cc=cc,
        bcc="",
        subject=subject,
        html_body=html_body,
        attachment_path=None
    )


# ======================================================================
# API 2 : nouvelle fonction avec pièces jointes (utilisée pour mail ASF)
# ======================================================================
def create_outlook_draft_with_attachment(to, cc, bcc, subject, html_body, attachment_path=None):
    osname = platform.system()

    if osname == "Windows":
        return outlook_create_draft_windows(to, cc, bcc, subject, html_body, attachment_path)

    if osname == "Darwin":
        return outlook_create_draft_mac(to, cc, bcc, subject, html_body, attachment_path)

    raise RuntimeError("Unsupported OS")
