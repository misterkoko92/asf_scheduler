# asf_app/utils_clean_planning.py
# -*- coding: utf-8 -*-

import pandas as pd
import numpy as np

# ------------------------------------------------------------
# Jours en français (indépendant de la locale OS)
# ------------------------------------------------------------
JOUR_MAP = {
    0: "Lundi",
    1: "Mardi",
    2: "Mercredi",
    3: "Jeudi",
    4: "Vendredi",
    5: "Samedi",
    6: "Dimanche",
}

# ------------------------------------------------------------
# Normalisation des noms (évite les problèmes de merge)
# ------------------------------------------------------------
def normalize_name(s):
    if not isinstance(s, str):
        return s

    invisibles = ["\u202A", "\u202C", "\u202B", "\u200E",
                  "\u200F", "\u00A0", "\u202F"]
    for bad in invisibles:
        s = s.replace(bad, " ")

    for t in ["–", "—", "−"]:
        s = s.replace(t, "-")

    return " ".join(s.split()).strip().upper()

# ------------------------------------------------------------
# Nettoyage téléphone
# ------------------------------------------------------------
def clean_phone(num):
    if pd.isna(num):
        return None

    s = str(num)
    for bad in ["\u202A", "\u202C", "\u202B", "\u200E",
                "\u200F", "\u00A0", "\u202F"]:
        s = s.replace(bad, "")

    s = "".join(c for c in s if c.isdigit())
    return s if len(s) >= 9 else None

# ------------------------------------------------------------
# Formatage du numéro de vol : AF + 3 derniers chiffres
# ------------------------------------------------------------
def clean_vol(vol):
    s = str(vol).strip()
    digits = "".join(c for c in s if c.isdigit())

    if len(digits) >= 3:
        return "AF" + digits[-3:]
    elif len(digits) > 0:
        return "AF" + digits
    return None


# ============================================================
#           FONCTION PRINCIPALE : CLEAN DU PLANNING
# ============================================================
def clean_planning_df(planning_df, be_df, benev_df, dest_df):

    df = planning_df.copy()

    # --------------------------------------------------------
    # DATE + JOUR
    # --------------------------------------------------------
    df["Date_Vol"] = pd.to_datetime(df["Date_Vol"], errors="coerce")
    df["Jour"] = df["Date_Vol"].dt.dayofweek.map(JOUR_MAP)

    # --------------------------------------------------------
    # Destination_Nom via ParamDest
    # --------------------------------------------------------
    dest_df = dest_df.rename(columns={
        "Destination": "Destination",
        "Ville": "Destination_Nom"
    })

    df = df.merge(dest_df[["Destination", "Destination_Nom"]],
                  on="Destination", how="left")

    # --------------------------------------------------------
    # Format N° de vol
    # --------------------------------------------------------
    df["Vol"] = df["Vol"].apply(clean_vol)

    # --------------------------------------------------------
    # Harmonisation BE_Numero + MAG CENTRAL
    # --------------------------------------------------------
    df["BE_Numero"] = df["BE_Numero"].astype(str).str.strip()
    be_df["N° BE"] = be_df["N° BE"].astype(str).str.strip()

    be_df = be_df.rename(columns={
        "N° BE": "BE_Numero",
        "NB": "BE_Nb_Colis",
        "TYPE": "BE_Type",
        "EXP": "BE_Expediteur",
        "DESTINATAIRE": "BE_Destinataire"
    })

    # --------------------------------------------------------
    # SUPPRESSION DES BE SANS DATE IMPRESSION (règle ASF)
    # --------------------------------------------------------
    if "DATE IMPRESSION BE" in be_df.columns:
        be_df["DATE IMPRESSION BE"] = pd.to_datetime(
            be_df["DATE IMPRESSION BE"], errors="coerce"
        )
        be_df = be_df[~be_df["DATE IMPRESSION BE"].isna()].copy()

    # Récupération année impression
    if "DATE IMPRESSION BE" in be_df.columns:
        be_df["BE_Annee"] = be_df["DATE IMPRESSION BE"].dt.year % 100

    # Merge MAG CENTRAL (type, expéditeur…)
    df = df.merge(
        be_df[["BE_Numero", "BE_Type", "BE_Expediteur", "BE_Destinataire", "BE_Annee"]],
        on="BE_Numero", how="left"
    )

    # --------------------------------------------------------
    # Construction du numéro BE final : AA + NNNN
    # --------------------------------------------------------
    def formater_be(num, annee):
        if pd.isna(num) or pd.isna(annee):
            return num

        try:
            brut = int(str(num).strip())
            an = int(annee)
            return f"{an:02d}{brut:04d}"
        except:
            return num

    df["BE_Numero"] = df.apply(
        lambda r: formater_be(r["BE_Numero"], r.get("BE_Annee")),
        axis=1
    )

    # --------------------------------------------------------
    # ParamBenev (prénom complet + tel)
    # --------------------------------------------------------
    benev_df = benev_df.rename(columns={
        "BENEVOLE": "Benevole",
        "PRENOM": "PrenomComplet",
        "Telephone": "Tel"
    })

    df["Benevole"] = df["Benevole"].apply(normalize_name)
    benev_df["Benevole"] = benev_df["Benevole"].apply(normalize_name)
    benev_df["Tel"] = benev_df["Tel"].apply(clean_phone)

    df = df.merge(
        benev_df[["Benevole", "PrenomComplet", "Tel"]],
        on="Benevole", how="left"
    )

    # --------------------------------------------------------
    # FUSION DES BE IDENTIQUES (anti-duplication)
    # --------------------------------------------------------
    group_cols = [
        "Date_Vol", "Jour", "Heure_Vol",
        "Vol", "Destination", "BE_Numero"
    ]

    df = (
        df.groupby(group_cols, dropna=False)
        .agg({
            "Destination_Nom": "first",
            "BE_Nb_Colis": "max",
            "BE_Nb_Equiv": "max",
            "BE_Type": lambda x: "/".join(sorted(set(
                str(v).strip().upper()
                for v in x.dropna()
                if str(v).strip() != ""
            ))),
            "BE_Expediteur": "first",
            "BE_Destinataire": "first",
            "Benevole": "first",
            "PrenomComplet": "first",
            "Tel": "first"
        })
        .reset_index()
    )

    df = df.drop_duplicates()

    # --------------------------------------------------------
    # SIMPLE / DOUBLE
    # --------------------------------------------------------
    key = ["Date_Vol", "Vol", "Heure_Vol", "Destination"]

    df["Nb_Benevoles"] = df.groupby(key)["Benevole"].transform("nunique")
    df["Mode"] = np.where(df["Nb_Benevoles"] > 1, "DOUBLE", "SIMPLE")

    # --------------------------------------------------------
    # Benevole_1, Benevole_2
    # --------------------------------------------------------
    def extraire(g):
        u = list(g["Benevole"].unique())
        return pd.Series({
            "Benevole_1": u[0],
            "Benevole_2": u[1] if len(u) > 1 else None
        })

    pairs = df.groupby(key).apply(extraire).reset_index()
    df = df.merge(pairs, on=key, how="left")

    # --------------------------------------------------------
    # Format final date → YYYY-MM-DD
    # --------------------------------------------------------
    df["Date_Vol"] = df["Date_Vol"].dt.strftime("%Y-%m-%d")

    return df
