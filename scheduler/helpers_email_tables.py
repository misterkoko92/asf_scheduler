# helpers_email_tables.py (optionnel)
# Si tu ne veux pas de fichier séparé, tu peux coller ce code
# en haut de email_destinations_handler.py et l'importer dans expéditeurs.

import pandas as pd
from format_rules import format_date_fr_long_slash

def build_comm_table_html(df_subset: pd.DataFrame) -> str:
    """
    Construit le tableau HTML commun pour les mails Destinations & Expéditeurs.
    Colonnes :
    - Date (Lundi 22/11/25)
    - Destination (ABIDJAN)
    - N° Vol (AF345)
    - N° BE (BE 250678)
    - Nombre de Colis
    - Type Colis
    - Expéditeur
    - Destinataire
    """

    if df_subset is None or df_subset.empty:
        return "<p>Aucun colis pour cette sélection.</p>"

    rows_html = []

    # Entête
    header = (
        "<tr>"
        "<th>Date</th>"
        "<th>Destination</th>"
        "<th>N° Vol</th>"
        "<th>N° BE</th>"
        "<th>Nombre de Colis</th>"
        "<th>Type Colis</th>"
        "<th>Expéditeur</th>"
        "<th>Destinataire</th>"
        "</tr>"
    )
    rows_html.append(header)

    for _, row in df_subset.iterrows():
        # Date : Lundi 22/11/25 → on part de format_date_fr_long_slash ("Lundi 22/11/2025")
        raw_date = format_date_fr_long_slash(row["DATE"])
        # convertir 2025 → 25 si possible
        date_aff = raw_date
        parts = raw_date.split("/")
        if len(parts) == 3 and len(parts[-1]) == 4:
            parts[-1] = parts[-1][-2:]
            date_aff = "/".join(parts)

        dest_aff = str(row["Destination"]).upper()
        vol_aff = row["Numero_Vol_Aff"]
        be_aff = f"BE {row['Numero_BE_Aff']}"
        nb_colis = row["Nb_Colis"]
        type_colis = str(row["Type_Colis"]).upper()
        expediteur = str(row["Expediteur"]).upper()
        destinataire = str(row["Destinataire"]).upper()

        tr = (
            "<tr>"
            f"<td>{date_aff}</td>"
            f"<td>{dest_aff}</td>"
            f"<td>{vol_aff}</td>"
            f"<td>{be_aff}</td>"
            f"<td>{nb_colis}</td>"
            f"<td>{type_colis}</td>"
            f"<td>{expediteur}</td>"
            f"<td>{destinataire}</td>"
            "</tr>"
        )
        rows_html.append(tr)

    table_html = (
        "<table border='1' cellspacing='0' cellpadding='4'>"
        + "".join(rows_html) +
        "</table>"
    )

    return table_html
