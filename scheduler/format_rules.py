# scheduler/format_rules.py
# -*- coding: utf-8 -*-
# ============================================================
# VERSION UNIFIÉE — Compatibilité totale Planning + Communication 3.0
# ============================================================

from __future__ import annotations

import pandas as pd
from datetime import datetime
import math
from typing import Any, Optional, Tuple


# ============================================================
# Helpers génériques
# ============================================================

def _to_str(v: Any) -> str:
    if v is None:
        return ""
    try:
        return str(v)
    except Exception:
        return ""


def _digits(v: Any) -> str:
    return "".join(ch for ch in _to_str(v) if ch.isdigit())


def _to_datetime(x):
    """Convertit robustement en datetime (Excel, str, datetime)."""
    if isinstance(x, datetime):
        return x

    if isinstance(x, float) and math.isnan(x):
        return None

    try:
        return pd.to_datetime(x)
    except Exception:
        return None


# ============================================================
# -------------------- PARTIE ORIGINALE -----------------------
# BE FORMAT (ancien système moteur) — compatibilité assurée
# ============================================================

def extract_be_suffix(raw_value: Any) -> Optional[int]:
    """
    Extrait un entier strict depuis la valeur brute du BE.
    1 → "1.0" → 1
    """
    if raw_value is None:
        return None
    s = str(raw_value).strip()
    if s == "" or s.lower() in ("nan", "none"):
        return None
    try:
        return int(float(s))
    except Exception:
        return None


def infer_be_year(date_impression: Any, fallback_latest: Any) -> int:
    """
    Détermine l'année (YYYY) pour le format BE.
    Priorité :
        1) date d'impression de la ligne
        2) dernière date d'impression valide du fichier
        3) année courante
    """
    for src in (date_impression, fallback_latest):
        try:
            if isinstance(src, pd.Timestamp) and pd.notna(src):
                return int(src.year)
            if hasattr(src, "year"):
                return int(src.year)
        except Exception:
            pass

    return datetime.today().year


def format_be_numero(
    raw_value: Any,
    date_impression: Any,
    fallback_latest_date: Any,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Formate un numéro de BE au format YYNNNN (6 chiffres).

    Retour :
        (numero_formate, suffix)
        Exemple :
            raw=4, année=2025 → ("250004", "0004")
    """
    suffix_int = extract_be_suffix(raw_value)
    if suffix_int is None or suffix_int < 0:
        return None, None

    suffix = f"{suffix_int:04d}"

    year = infer_be_year(date_impression, fallback_latest_date)
    yy = str(year)[-2:]

    formatted = f"{yy}{suffix}"

    return formatted, suffix


# ============================================================
# -------------------- PARTIE ORIGINALE -----------------------
# Numéro de vol (ancien système)
# ============================================================

def format_flight_number(company: str, raw_number: Any) -> str:
    comp = _to_str(company).strip().upper()
    digits = _digits(raw_number)
    if not digits:
        return comp
    try:
        num = int(digits)
    except Exception:
        num = 0
    if num <= 0:
        return comp
    return f"{comp}{num}"


# ============================================================
# -------------------- PARTIE ORIGINALE -----------------------
# Dates mode court/long/iso
# ============================================================

WEEKDAYS_FR = ["LUN", "MAR", "MER", "JEU", "VEN", "SAM", "DIM"]


def _to_dt(v: Any) -> Optional[datetime]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    try:
        if hasattr(v, "to_pydatetime"):
            return v.to_pydatetime()
    except:
        pass
    try:
        return datetime.fromisoformat(str(v))
    except Exception:
        return None


def format_date(date_obj: Any, mode="default") -> str:
    dt = _to_dt(date_obj)
    if dt is None:
        return ""
    if mode == "short":
        return dt.strftime("%d/%m")
    if mode == "iso":
        return dt.strftime("%Y-%m-%d")
    if mode == "long":
        wd = WEEKDAYS_FR[dt.weekday()]
        return f"{wd} {dt.strftime('%d/%m/%Y')}"
    return dt.strftime("%d/%m/%Y")


# ============================================================
# --------------- PARTIE COMMUNICATION 3.0 --------------------
# ============================================================

JOURS_FR = [
    "Lundi", "Mardi", "Mercredi", "Jeudi",
    "Vendredi", "Samedi", "Dimanche"
]

MOIS_FR = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre"
]


# ============================================================
# Format BE “simple” (Communication)
# ============================================================

def format_be_number(value):
    """
    Format BE en YYNNNN.
    Garde uniquement les chiffres.
    """
    if value is None:
        return ""
    return "".join(c for c in str(value) if c.isdigit())


# ============================================================
# Format Numéro de vol (Communication)
# ============================================================

def format_vol_number(value):
    """
    Format numéro de vol :
    AF768, AF918
    """
    if value is None:
        return ""
    s = str(value).strip().upper().replace(" ", "")
    return s


# ============================================================
# Dates Communication : "Lundi 13/11/2025"
# ============================================================

def format_date_fr_long_slash(x):
    dt = _to_datetime(x)
    if dt is None:
        return ""
    jour = JOURS_FR[dt.weekday()]
    return f"{jour} {dt.day:02d}/{dt.month:02d}/{dt.year}"


# ============================================================
# Dates WhatsApp : "Lundi 13 novembre"
# ============================================================

def format_date_fr_words(x):
    dt = _to_datetime(x)
    if dt is None:
        return ""
    jour = JOURS_FR[dt.weekday()]
    mois = MOIS_FR[dt.month - 1]
    return f"{jour} {dt.day} {mois}"


# ============================================================
# Format heures WhatsApp : 10h40
# ============================================================

def format_heure_hh_mm(x):
    if x is None:
        return ""
    if isinstance(x, str) and "h" in x:
        return x

    try:
        dt = pd.to_datetime(x)
        return f"{dt.hour}h{dt.minute:02d}"
    except Exception:
        pass

    return str(x).replace(":", "h")
