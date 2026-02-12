from html import escape
import pandas as pd

from utils.identifiers import format_vol_display

# asf_app/ui/ui_communication/helpers_email_tables.py
# -----------------------------------------------------
# Génère un tableau HTML propre pour les emails Destinations / Expéditeurs

def build_comm_table_html(df):
    """
    Construit un tableau HTML (sans CSS externe)
    avec en-têtes + lignes du DF fourni.

    Colonnes attendues dans df_comm :
        Date_Affichage
        Destination
        Numero_Vol_Aff
        Numero_BE_Aff
        Nb_Colis
        Type_Colis
        Expediteur
        Destinataire
    """

    if df is None or df.empty:
        return "<p><i>Aucun colis cette semaine.</i></p>"

    df = df.copy()

    # Format numéro de vol AF XXX (supprime .0 éventuel)
    def _fmt_vol(v):
        out = format_vol_display(v)
        if out:
            return out
        s = str(v).strip()
        if not s:
            return ""
        if s.upper().startswith("AF"):
            suf = s[2:].strip()
            return f"AF {suf}"
        return f"AF {s}"

    df["Numero_Vol_Aff"] = df.get("Numero_Vol_Aff", df.get("NUMERO VOL", "")).apply(_fmt_vol)

    # Sélection des colonnes
    cols = [
        "Date_Affichage",
        "Destination",
        "Numero_Vol_Aff",
        "Numero_BE_Aff",
        "Nb_Colis",
        "Type_Colis",
        "Expediteur",
        "Destinataire",
    ]

    # En-têtes lisibles
    headers = {
        "Date_Affichage": "Date",
        "Destination": "Destination",
        "Numero_Vol_Aff": "N° Vol",
        "Numero_BE_Aff": "N° BE",
        "Nb_Colis": "Colis",
        "Type_Colis": "Type",
        "Expediteur": "Expéditeur",
        "Destinataire": "Destinataire",
    }

    # Construction HTML
    border_style = "border:1px solid #999;"
    html = [f'<table cellpadding="6" cellspacing="0" style="border-collapse:collapse; table-layout:auto; {border_style}">']

    # Ligne en-tête
    html.append("<tr>")
    for c in cols:
        html.append(f"<th style='background:#e6e6e6; white-space:nowrap; {border_style}'>{headers[c]}</th>")
    html.append("</tr>")

    # Lignes
    for _, row in df[cols].iterrows():
        html.append("<tr>")
        for c in cols:
            value = row[c]
            if pd.isna(value):
                safe_value = ""
            else:
                safe_value = escape(str(value), quote=True)
            html.append(f"<td style='white-space:nowrap; {border_style}'>{safe_value}</td>")
        html.append("</tr>")

    html.append("</table>")

    return "\n".join(html)
