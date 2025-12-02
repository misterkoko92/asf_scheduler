# clean_planning_df.py — Version Communication 3.4 ULTRA ROBUSTE
# ---------------------------------------------------------------
# Tolère toutes les variantes de colonnes venant du planning.
# Compatible enrich_planning → df_comm → WhatsApp / Emails

import pandas as pd
from datetime import datetime

from scheduler.format_rules import (
    format_be_number,
    format_vol_number,
    format_date_fr_long_slash,
    format_date_fr_words
)


# ============================================================
# OUTIL : safe uppercase
# ============================================================
def _u(x):
    if pd.isna(x):
        return ""
    return str(x).strip().upper()


# ============================================================
# VARIANTES DE COLONNES ACCEPTÉES
# ============================================================

COLUMN_VARIANTS = {
    "NUMERO VOL": [
        "NUMERO VOL", "NUMERO_VOL", "Numero_Vol", "Numero VOL",
        "Numero Vol", "VOL_NUM", "NUMERO_VOL", "Vol"
    ],
    "HEURE VOL": [
        "HEURE VOL", "HEURE_VOL", "Heure_Vol", "Heure VOL",
        "Heure Vol", "HEUREVOL"
    ],
    "DESTINATION": [
        "DESTINATION", "Destination", "dest", "VILLE", "Dest_Ville"
    ],
    "NOMBRE COLIS": [
        "NOMBRE COLIS", "NB_COLIS", "NB COLIS", "BE_Nb_Colis"
    ],
    "TYPE": [
        "TYPE", "BE_Type", "TYPE_COLIS"
    ],
    "EXPEDITEUR": [
        "EXPEDITEUR", "BE_Expediteur", "EXP", "EXPED"
    ],
    "DESTINATAIRE": [
        "DESTINATAIRE", "BE_Destinataire", "RECEPT"
    ],
    "NUMERO BE": [
        "NUMERO BE", "BE_Numero", "NUM_BE"
    ],
}


def _normalize_column(df: pd.DataFrame, target: str):
    """
    Créé df[target] en recherchant dans les variantes possibles.
    Si aucune colonne n’existe → colonne vide.
    """
    variants = COLUMN_VARIANTS.get(target, [])

    for v in variants:
        if v in df.columns:
            df[target] = df[v]
            return

    df[target] = ""  # fallback


# ============================================================
# MAIN FUNCTION
# ============================================================
def build_df_comm(df_planning: pd.DataFrame,
                  df_paramdest: pd.DataFrame,
                  df_parambenev: pd.DataFrame) -> pd.DataFrame:

    if df_planning is None or df_planning.empty:
        return pd.DataFrame()

    df_planning = df_planning.copy()

    # --------------------------------------------------------
    # 0) COLONNES ESSENTIELLES — PATCHES DE SÉCURITÉ
    # --------------------------------------------------------

    # DATE
    df_planning["DATE"] = df_planning.get("DATE", df_planning.get("Date_Vol", ""))

    # BENEVOLE
    df_planning["BENEVOLE"] = df_planning.get("BENEVOLE", df_planning.get("Benevole", ""))

    # BENEVOLE_ID
    df_planning["BENEVOLE_ID"] = (
        df_planning.get("BENEVOLE_ID",
        df_planning.get("ID_BENEVOLE",
        df_planning.get("ID", "")))
    )

    # DESTINATION
    df_planning["DESTINATION"] = df_planning.get(
        "DESTINATION",
        df_planning.get("Dest_Ville",
        df_planning.get("Destination", ""))
    )

    # DESTINATAIRE (fallbacks depuis différentes colonnes)
    if "DESTINATAIRE" not in df_planning.columns:
        df_planning["DESTINATAIRE"] = ""
    df_planning["DESTINATAIRE"] = df_planning["DESTINATAIRE"].fillna("")
    for alt in ["BE_Destinataire", "BE_DESTINATAIRE", "Destinataire"]:
        if alt in df_planning.columns:
            mask_empty = df_planning["DESTINATAIRE"].astype(str).str.strip().eq("") | df_planning["DESTINATAIRE"].isna()
            df_planning.loc[mask_empty, "DESTINATAIRE"] = df_planning[alt]

    # --------------------------------------------------------
    # 1) Normalisation des variantes
    # --------------------------------------------------------
    for col in COLUMN_VARIANTS.keys():
        _normalize_column(df_planning, col)

    # --------------------------------------------------------
    # 2) Normalisation destinations (ville + IATA)
    # --------------------------------------------------------

    # Forcer présence colonnes ParamDest
    if "Dest_Ville" not in df_paramdest.columns:
        df_paramdest["Dest_Ville"] = ""
    if "Dest_IATA" not in df_paramdest.columns:
        df_paramdest["Dest_IATA"] = ""

    df_paramdest_local = df_paramdest.copy()
    df_paramdest_local["Dest_Ville_UP"] = (
        df_paramdest_local["Dest_Ville"].astype(str).str.strip().str.upper()
    )
    df_paramdest_local["Dest_IATA_UP"] = (
        df_paramdest_local["Dest_IATA"].astype(str).str.strip().str.upper()
    )

    df_planning["Destination_UP"] = (
        df_planning["DESTINATION"].astype(str).str.strip().str.upper()
    )

    # Cartographies IATA <-> Ville (uppercase)
    dedup = df_paramdest_local.drop_duplicates(subset=["Dest_IATA_UP"])
    map_iata_to_ville = dedup.set_index("Dest_IATA_UP")["Dest_Ville"].str.upper().to_dict()
    map_ville_to_iata = dedup.set_index("Dest_Ville_UP")["Dest_IATA"].str.upper().to_dict()

    # Base DF : on part du planning seul
    df = df_planning.copy()

    # Ajout colonnes vides si manquantes
    for col in ["Dest_Ville", "Dest_IATA"]:
        if col not in df.columns:
            df[col] = ""

    # Détection : IATA (3 lettres) vs Ville
    is_iata = df["Destination_UP"].str.len() == 3

    # --- Cas Destination = code IATA ---
    df.loc[is_iata, "Dest_IATA"] = df.loc[is_iata, "Destination_UP"]
    df.loc[is_iata, "Dest_Ville"] = (
        df.loc[is_iata, "Dest_IATA"]
        .map(map_iata_to_ville)
        .fillna(df.loc[is_iata, "Dest_IATA"])
    )

    # --- Cas Destination = ville ---
    df.loc[~is_iata, "Dest_Ville"] = df.loc[~is_iata, "DESTINATION"]
    df.loc[~is_iata, "Dest_IATA"] = (
        df.loc[~is_iata, "Dest_Ville"]
        .str.upper()
        .map(map_ville_to_iata)
        .fillna("")
    )

    # Harmonisation uppercase
    df["Dest_Ville_UP"] = df["Dest_Ville"].astype(str).str.strip().str.upper()
    df["Dest_IATA_UP"] = df["Dest_IATA"].astype(str).str.strip().str.upper()

    # Fallback : ville manquante → via IATA, sinon Destination brute
    mask_city_empty = df["Dest_Ville_UP"].eq("") | df["Dest_Ville_UP"].isna()
    df.loc[mask_city_empty, "Dest_Ville"] = (
        df.loc[mask_city_empty, "Dest_IATA_UP"].map(map_iata_to_ville).fillna(df.loc[mask_city_empty, "DESTINATION"])
    )
    df["Dest_Ville_UP"] = df["Dest_Ville"].astype(str).str.strip().str.upper()

    # Fallback : IATA manquant → via ville
    mask_iata_empty = df["Dest_IATA_UP"].eq("") | df["Dest_IATA_UP"].isna()
    df.loc[mask_iata_empty, "Dest_IATA"] = df.loc[mask_iata_empty, "Dest_Ville_UP"].map(map_ville_to_iata).fillna("")
    df["Dest_IATA_UP"] = df["Dest_IATA"].astype(str).str.strip().str.upper()

    # Destination canonique pour communication (ville en majuscules sinon code)
    df["Destination"] = df["Dest_Ville_UP"].where(df["Dest_Ville_UP"].ne(""), df["Dest_IATA_UP"])

    # Sécurité : si colonnes absentes, créer vides
    for col in ["Dest_Ville", "Dest_IATA"]:
        if col not in df.columns:
            df[col] = ""

    # --------------------------------------------------------
    # 3) Normalisation ParamBenev + Merge via ID puis fallback via nom
    # --------------------------------------------------------
    df_parambenev_local = df_parambenev.copy()

    # === A) Forcer les types en STRING ===
    df_parambenev_local["ID"] = df_parambenev_local["ID"].astype(str).str.strip()
    df["BENEVOLE_ID"] = df["BENEVOLE_ID"].astype(str).str.strip()

    # === B) Uppercase pour matching
    df_parambenev_local["ID_UP"] = df_parambenev_local["ID"].str.upper()
    df["BENEVOLE_ID_UP"] = df["BENEVOLE_ID"].str.upper()

    df_parambenev_local["Benevole_UP"] = (
        df_parambenev_local["Benevole"].astype(str).str.strip().str.upper()
    )
    df["BENEVOLE_UP"] = (
        df["BENEVOLE"].astype(str).str.strip().str.upper()
    )

    # === C) MERGE PRINCIPAL via ID
    df = df.merge(
        df_parambenev_local,
        how="left",
        left_on="BENEVOLE_ID_UP",
        right_on="ID_UP",
        suffixes=("", "_PB")
    )

    # === D) Fallback : ceux où l'ID n'a rien donné → on matche le nom
    missing_mask = df["ID"].isna()

    if missing_mask.any():

        df_fallback = df.loc[missing_mask].merge(
            df_parambenev_local,
            how="left",
            left_on="BENEVOLE_UP",
            right_on="Benevole_UP",
            suffixes=("", "_FB"),
        )

        # Colonnes bénévole à patcher
        for col in ["Telephone", "Prenom", "Prenom_Court", "Nom", "ID"]:
            if col in df_fallback.columns:
                df.loc[missing_mask, col] = df_fallback[col]

    # Éviter valeurs NaN
    for c in ["Telephone", "Prenom", "Prenom_Court", "Nom"]:
        df[c] = df[c].fillna("")

    # Normalisation IDs bénévoles en str (sans .0)
    df["BENEVOLE_ID"] = df["BENEVOLE_ID"].astype(str).str.replace(r"\\.0$", "", regex=True).replace("nan", "").str.strip()
    if "ID_BENEVOLE" in df.columns:
        df["ID_BENEVOLE"] = df["ID_BENEVOLE"].astype(str).str.replace(r"\\.0$", "", regex=True).replace("nan", "").str.strip()

    # Fallback si ID bénévole manquant : appariement sur le nom complet (BENEVOLE ou Benevole)
    if df_parambenev is not None and not getattr(df_parambenev, "empty", True):
        df_parambenev_local["Benevole_UP"] = df_parambenev_local["Benevole"].astype(str).str.strip().str.upper()
        map_name_to_fields = df_parambenev_local.set_index("Benevole_UP")[["ID", "Prenom", "Prenom_Court", "Nom", "Telephone"]]
        bene_name_up = df.get("BENEVOLE", df.get("Benevole", pd.Series([""]))).astype(str).str.strip().str.upper()
        mask_no_id = df["BENEVOLE_ID"].astype(str).str.strip().eq("")
        df.loc[mask_no_id, "BENEVOLE_ID"] = bene_name_up[mask_no_id].map(map_name_to_fields["ID"]).fillna(df.loc[mask_no_id, "BENEVOLE_ID"])
        df.loc[mask_no_id, "Prenom"] = bene_name_up[mask_no_id].map(map_name_to_fields["Prenom"]).fillna(df.loc[mask_no_id, "Prenom"])
        df.loc[mask_no_id, "Prenom_Court"] = bene_name_up[mask_no_id].map(map_name_to_fields["Prenom_Court"]).fillna(df.loc[mask_no_id, "Prenom_Court"])
        df.loc[mask_no_id, "Nom"] = bene_name_up[mask_no_id].map(map_name_to_fields["Nom"]).fillna(df.loc[mask_no_id, "Nom"])
        df.loc[mask_no_id, "Telephone"] = bene_name_up[mask_no_id].map(map_name_to_fields["Telephone"]).fillna(df.loc[mask_no_id, "Telephone"])

    # --------------------------------------------------------
    # 4) Formats métiers
    # --------------------------------------------------------
    df["Date_Affichage"] = df["DATE"].apply(format_date_fr_long_slash)
    df["Date_Affichage_WA"] = df["DATE"].apply(format_date_fr_words)

    def _fmt_be_with_date(val, date_val):
        digits = "".join(c for c in str(val) if c.isdigit())
        if not digits:
            return ""
        if len(digits) >= 6:
            return digits[-6:]
        year_hint = None
        try:
            year_hint = pd.to_datetime(date_val, errors="coerce").year
        except Exception:
            year_hint = None
        prefix = f"{int(year_hint)%100:02d}" if year_hint else ""
        return f"{prefix}{digits.zfill(4)}"

    df["Numero_BE_Aff"] = df.apply(
        lambda r: _fmt_be_with_date(
            r.get("NUMERO BE", r.get("BE_Numero", "")),
            r.get("DATE", r.get("Date_Vol", "")),
        ),
        axis=1,
    )
    df["Numero_Vol_Aff"] = df["NUMERO VOL"].apply(format_vol_number)

    # Destination (ville + IATA)
    df["Destination"] = df["Dest_Ville"].fillna("").astype(str).str.upper()
    mask_dest = df["Destination"].str.strip().eq("")
    if "DESTINATION" in df.columns:
        df.loc[mask_dest, "Destination"] = df.loc[mask_dest, "DESTINATION"].astype(str).str.upper()
    df["Destination"] = df["Destination"].replace("NAN", "").str.strip()
    df["Code_IATA"] = df["Dest_IATA"].fillna("").astype(str).str.upper()

    # BE
    # Colis toujours en entier
    df["Nb_Colis"] = (
        pd.to_numeric(df["NOMBRE COLIS"], errors="coerce")
        .fillna(0)
        .astype(int)
    )
    df["Type_Colis"] = df["TYPE"].fillna("").astype(str)
    df["Expediteur"] = df["EXPEDITEUR"].fillna("").astype(str)
    df["Destinataire"] = df["DESTINATAIRE"].fillna("").astype(str)
    if "BE_Destinataire" in df.columns:
        mask_dest_vide = df["Destinataire"].str.strip().eq("") | df["Destinataire"].isna()
        df.loc[mask_dest_vide, "Destinataire"] = df.loc[mask_dest_vide, "BE_Destinataire"].fillna("")
    if "BE_Destinataire" in df.columns:
        mask_dest_vide = df["Destinataire"].str.strip().eq("") | df["Destinataire"].isna()
        df.loc[mask_dest_vide, "Destinataire"] = df.loc[mask_dest_vide, "BE_Destinataire"].fillna("")
    if "BE_Destinataire" in df.columns:
        mask_dest_vide = df["Destinataire"].str.strip().eq("") | df["Destinataire"].isna()
        df.loc[mask_dest_vide, "Destinataire"] = df.loc[mask_dest_vide, "BE_Destinataire"].fillna("")

    # Bénévoles
    df["Benevole"] = df["BENEVOLE"].fillna("").astype(str)
    df["Benevole_Tel"] = df["Telephone"].fillna("").astype(str)
    df["Benevole_Prenom"] = df["Prenom"].fillna("").astype(str)
    df["Benevole_Prenom_Court"] = df["Prenom_Court"].fillna("").astype(str)
    df["Benevole_Nom"] = df["Nom"].fillna("").astype(str).str.upper()

    df["Heure_Vol_Aff"] = df["HEURE VOL"].astype(str).str.strip()

    # --------------------------------------------------------
    # 5) Colonnes finales — WhatsApp & Emails
    # --------------------------------------------------------
    colonnes_finales = [
        # Métier
        "Destination",
        "Date_Affichage",
        "Date_Affichage_WA",   # <=== MANQUANTE AVANT = 0 messages WA
        "Numero_Vol_Aff",
        "Heure_Vol_Aff",
        "Numero_BE_Aff",
        "Nb_Colis",
        "Type_Colis",
        "Expediteur",
        "Destinataire",

        # Bénévoles
        "Benevole",
        "Benevole_Tel",
        "Code_IATA",
        "Dest_Ville",

        # Techniques
        "BENEVOLE_ID",
        "Benevole_Prenom",
        "Benevole_Prenom_Court",
        "Benevole_Nom",

        # Brutes utiles
        "DATE",
        "HEURE VOL",
        "NUMERO VOL",
        "DESTINATION",
        "Destination_UP",
    ]

    # Sécurité : si colonne manquante → créer vide
    for col in colonnes_finales:
        if col not in df.columns:
            df[col] = ""

    return df[colonnes_finales].copy()
