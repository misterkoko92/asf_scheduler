# outlook.py — Version Communication 3.0
# ---------------------------------------------------------
# Création d'emails Outlook en brouillon (Windows + macOS)
# avec support des signatures automatiques, To/CC/BCC,
# HTML minimal, pièces jointes et ouverture en premier plan.
# ---------------------------------------------------------

import platform
import subprocess
from typing import List, Optional

from utils.logging_utils import get_logger

logger = get_logger("ui_communication_outlook", console=False)

OUTLOOK_WINDOWS_ERRORS: tuple[type[BaseException], ...] = (
    AttributeError,
    ImportError,
    OSError,
    PermissionError,
    RuntimeError,
    TypeError,
    ValueError,
)

try:
    import pywintypes

    com_error = getattr(pywintypes, "com_error", Exception)
    if isinstance(com_error, type) and issubclass(com_error, BaseException):
        OUTLOOK_WINDOWS_ERRORS = OUTLOOK_WINDOWS_ERRORS + (com_error,)
except (ImportError, AttributeError):
    pass

# ============================================================
# Helper : nettoyage liste d'emails
# ============================================================
def _clean_list(value):
    if not value:
        return []
    if isinstance(value, str):
        # format "a@b.com ; c@d.com"
        parts = [p.strip() for p in value.replace(",", ";").split(";")]
        return [p for p in parts if p]
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return []


# ============================================================
# Fonction principale
# ============================================================
def create_outlook_draft(
    to_list: List[str],
    cc_list: Optional[List[str]] = None,
    bcc_list: Optional[List[str]] = None,
    subject: str = "",
    body_html: str = "",
    attachments: Optional[List[str]] = None,
    use_signature: bool = True,
):
    """
    Crée un mail brouillon Outlook.

    to_list, cc_list, bcc_list : listes d'adresses
    subject : sujet
    body_html : contenu HTML léger (important pour signature)
    attachments : liste de chemins vers fichiers
    use_signature : Outlook insère signature automatiquement
    """

    system = platform.system().lower()

    if "windows" in system:
        return _create_outlook_windows(
            to_list=_clean_list(to_list),
            cc_list=_clean_list(cc_list),
            bcc_list=_clean_list(bcc_list),
            subject=subject,
            body_html=body_html,
            attachments=attachments,
            use_signature=use_signature,
        )

    elif "darwin" in system:
        return _create_outlook_mac(
            to_list=_clean_list(to_list),
            cc_list=_clean_list(cc_list),
            bcc_list=_clean_list(bcc_list),
            subject=subject,
            body_html=body_html,
            attachments=attachments,
            use_signature=use_signature,
        )

    else:
        raise RuntimeError("Outlook non supporté sur ce système.")


# ============================================================
# WINDOWS — COM
# ============================================================
def _create_outlook_windows(to_list, cc_list, bcc_list,
                            subject, body_html, attachments,
                            use_signature):

    try:
        import win32com.client
        outlook = win32com.client.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)

        # Destinataires
        mail.To = "; ".join(to_list)
        if cc_list:
            mail.CC = "; ".join(cc_list)
        if bcc_list:
            mail.BCC = "; ".join(bcc_list)

        mail.Subject = subject

        # HTML + signature :
        # IMPORTANT : pour Windows, Outlook ajoute automatiquement la signature
        # après Display() si HTMLBody est vide ou minimal.
        if use_signature:
            # charger signature utilisateur
            try:
                sig = mail.HTMLBody  # déjà la signature Outlook
            except OUTLOOK_WINDOWS_ERRORS:
                sig = ""

            mail.HTMLBody = body_html + "<br>" + sig
        else:
            mail.HTMLBody = body_html

        # Pièces jointes
        if attachments:
            for f in attachments:
                try:
                    mail.Attachments.Add(f)
                except OUTLOOK_WINDOWS_ERRORS as exc:
                    logger.warning("Piece jointe Outlook ignoree (%s): %s", f, exc)

        mail.Display(True)  # premier plan
        return True

    except OUTLOOK_WINDOWS_ERRORS as e:
        logger.error("ERREUR Outlook Windows: %s", e)
        return False


# ============================================================
# MAC — AppleScript
# ============================================================
def _create_outlook_mac(to_list, cc_list, bcc_list,
                        subject, body_html, attachments,
                        use_signature):

    def _recipients_block(kind, lst):
        if not lst:
            return ""
        block = ""
        for addr in lst:
            addr = str(addr).replace('"', '\\"')
            block += f'\n                make new recipient at end of {kind} recipients with properties {{email address:{{address:"{addr}"}}}}'
        return block

    # IMPORTANT : corps minimal → permet signature auto
    body = body_html.replace('"', '\\"')

    # AppleScript pour Outlook macOS (retour d'erreur explicite)
    script = f'''
        tell application "Microsoft Outlook"
            set newMessage to make new outgoing message with properties {{subject:"{subject}", content:"{body}\\n\\n"}}
            tell newMessage
                {_recipients_block("to", to_list)}
                {_recipients_block("cc", cc_list)}
                {_recipients_block("bcc", bcc_list)}
    '''

    # Attachements
    if attachments:
        for f in attachments:
            f = str(f).replace('"', '\\"')
            script += f'''
                make new attachment at end of attachments with properties {{file:(POSIX file "{f}")}}
            '''

    script += '''
            end tell
            open newMessage
            activate
        end tell
    '''

    try:
        res = subprocess.run(
            ["osascript", "-s", "o", "-e", script],
            capture_output=True,
            text=True,
        )
        if res.returncode != 0:
            logger.error("ERREUR Outlook Mac: %s", (res.stderr or res.stdout).strip())
            return False
        return True
    except (OSError, ValueError, TypeError, RuntimeError, subprocess.SubprocessError) as e:
        logger.error("ERREUR Outlook Mac: %s", e)
        return False
