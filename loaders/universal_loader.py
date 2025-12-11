# scheduler/loaders/universal_loader.py
# -*- coding: utf-8 -*-

import pandas as pd

def _warn_unmapped_columns(df: pd.DataFrame, mapping: dict, context: str = ""):
    """Log en console les colonnes non mappées pour diagnostic."""
    source_cols = set(df.columns)
    mapped_sources = set(mapping.keys())
    unmapped = sorted(source_cols - mapped_sources)
    if unmapped:
        prefix = f"[UNMAPPED {context}] " if context else "[UNMAPPED] "
        print(prefix + ", ".join(map(str, unmapped)))
import unicodedata


# -------------------------------------------------------------------
# Helpers : normalisation des en-têtes Excel
# -------------------------------------------------------------------

def strip_accents(s: str) -> str:
    """Supprime les accents pour faciliter les comparaisons."""
    return ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
    )


def normalize_header(col):
    """
    Nettoyage intelligent :
    - Majuscules
    - Suppression espaces insécables
    - Suppression accents
    - Uniformisation séparateurs
    - Réduction doubles espaces
    """
    if not isinstance(col, str):
        return ""

    s = str(col).upper().strip()

    # espaces insécables & invisibles
    for bad in ["\u202F", "\u00A0", "\u2009", "\u2007", "\u200B",
                "\u202A", "\u202C", "\u200E", "\u200F"]:
        s = s.replace(bad, " ")

    # suppression accents
    s = strip_accents(s)

    # normalisation tirets
    s = s.replace("–", "-").replace("—", "-").replace("−", "-")

    # doubles espaces
    s = " ".join(s.split())

    return s


# -------------------------------------------------------------------
# Fuzzy matching des colonnes Excel → mapping interne
# -------------------------------------------------------------------

def fuzzy_match_columns(df: pd.DataFrame, mapping: dict):
    """
    Mapping robuste :
    - match exact après normalisation
    - match partiel
    - match inversé
    - colonnes inconnues ignorées sans erreur
    """
    original_cols = list(df.columns)

    # colonnes Excel → colonnes normalisées
    norm_cols = {normalize_header(c): c for c in df.columns}

    new_cols = {}  # old_column_name → mapped_column_name

    for raw_key, final_name in mapping.items():
        # Colonnes explicitement ignorées
        if final_name is None:
            continue

        nk = normalize_header(raw_key)

        # 1) Correspondance exacte après normalisation
        if nk in norm_cols:
            new_cols[norm_cols[nk]] = final_name
            continue

        # 2) Correspondance partielle / fuzzy
        best_match = None
        for col_norm, orig in norm_cols.items():
            if nk in col_norm or col_norm in nk:
                best_match = orig
                break

        if best_match:
            new_cols[best_match] = final_name
        else:
            # Ici on ignore simplement — robustesse maximale
            print(f"[INFO] Colonne '{raw_key}' absente dans Excel — ignorée.")
            continue

    # Renommage partiel
    return df.rename(columns=new_cols)


# -------------------------------------------------------------------
# LOADER PRINCIPAL — ROBUSTE
# -------------------------------------------------------------------

def load_and_normalize(path, sheet_name, mapping: dict, header=0):
    """
    Charge un Excel + feuille + normalisation robuste :
    ✓ mapping fuzzy intelligent
    ✓ colonnes inconnues ignorées (jamais d'erreur)
    ✓ colonnes manquantes ajoutées automatiquement
    ✓ NaN remplis
    """
    try:
        df = pd.read_excel(path, sheet_name=sheet_name, header=header)
    except Exception as e:
        print(f"[ERROR] load_and_normalize : impossible de lire {path}\n{e}")
        return pd.DataFrame()

    # Retire les colonnes vides type "Unnamed: xx"
    df = df.loc[:, [c for c in df.columns if not str(c).lower().startswith("unnamed")]]

    # Alerte colonnes non mappées (diagnostic)
    _warn_unmapped_columns(df, mapping, context=str(sheet_name))

    # Mapping intelligent
    df = fuzzy_match_columns(df, mapping)

    # Supprimer les colonnes marquées comme ignorées (nom cible qui commence par "_IGNORE")
    df = df[[c for c in df.columns if not str(c).startswith("_IGNORE")]]

    # Ajout des colonnes manquantes (hors colonnes ignorées)
    for target in mapping.values():
        if target is None:
            continue
        if isinstance(target, str) and target.startswith("_IGNORE"):
            continue
        if target not in df.columns:
            print(f"[WARN] Colonne manquante ajoutée : {target}")
            df[target] = ""

    # Remplir NaN pour éviter toute erreur en aval
    df = df.fillna("")

    # Colonnes "telephone" forcées en texte pour éviter les erreurs Arrow
    for col in df.columns:
        if "telephone" in str(col).lower() or "phone" in str(col).lower():
            df[col] = df[col].astype(str)

    return df
