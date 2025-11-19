# asf_app/utils_whatsapp.py
# -*- coding: utf-8 -*-

import urllib.parse
import pandas as pd

MOIS_MAP = {
    1: "janvier", 2: "février", 3: "mars", 4: "avril",
    5: "mai", 6: "juin", 7: "juillet", 8: "août",
    9: "septembre", 10: "octobre", 11: "novembre", 12: "décembre",
}

# ------------------------------------------------------------
# Construire message WhatsApp pour 1 bénévole
# ------------------------------------------------------------
def construire_message_whatsapp(benevole, df):

    # Prénom complet — robuste
    prenom = df["PrenomComplet"].iloc[0]
    if pd.isna(prenom):
        try:
            prenom = benevole.split(" ")[1]
        except:
            prenom = ""
    prenom = str(prenom).strip()

    msg = f"Bonjour {prenom}, voici tes mises à bord pour la semaine prochaine :\n\n"

    # Grouper par destination
    grouped = df.groupby("Destination")

    for dest, bloc in grouped:

        bloc = bloc.sort_values("Date_Vol")
        dest_nom = bloc["Destination_Nom"].iloc[0]

        total = bloc["BE_Nb_Colis"].sum()
        mode = bloc["Mode"].iloc[0]

        # Détection du co-bénévole
        autre = None
        if mode == "DOUBLE":
            b1 = bloc["Benevole_1"].iloc[0]
            b2 = bloc["Benevole_2"].iloc[0]
            autre = b2 if b1 == benevole else b1
            try:
                autre = df.loc[df["Benevole"] == autre, "PrenomComplet"].iloc[0]
            except:
                pass

        # Boucle sur les expéditions
        for _, row in bloc.iterrows():

            # Conversion string → date
            try:
                d = pd.to_datetime(row["Date_Vol"]).date()
                mois = MOIS_MAP[d.month]
                jour = d.day
            except Exception:
                mois = ""
                jour = ""
                d = None

            msg += (
                f"• {row['Jour']} {jour} {mois} : "
                f"{dest_nom.upper()} // {row['Vol']} // {row['Heure_Vol']} // "
                f"BE {row['BE_Numero']} // {row['BE_Nb_Colis']} colis {row['BE_Type']}\n"
            )

        # Total
        if mode == "DOUBLE" and autre:
            msg += f"Total {dest} : {total} colis en double avec {autre}\n\n"
        else:
            msg += f"Total {dest} : {total} colis en simple\n\n"

    msg += (
        "Merci de me confirmer si tu es OK. "
        "N'hésite pas à m'appeler si besoin pour ajuster.\n"
        "Merci beaucoup !"
    )

    return msg


# ------------------------------------------------------------
# Générer l'URL WhatsApp (pas d'ouverture automatique)
# ------------------------------------------------------------
def generer_url_whatsapp(numero, message):
    numero = str(numero)
    texte_encode = urllib.parse.quote(message)
    url = f"https://wa.me/{numero}?text={texte_encode}"
    return url
