# scheduler/be_manager.py
# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict

import pandas as pd

from loaders.universal_loader import load_and_normalize
from scheduler.column_map import column_map_param_be
from scheduler.config_paths import (
    SHEET_PARAM_BE,
    TABLEAU_DE_BORD,
)

logger = logging.getLogger("ASF-SCHEDULER")



# ------------------------------------------------------------
# Cache interne ParamBE (évite relecture multiple)
# ------------------------------------------------------------
_PARAM_BE_CACHE: Dict[str, Dict[str, int]] | None = None


# ============================================================
# 1) Normalisation ParamBE (DataFrame ou dict) — partagé moteur/UI
# ============================================================
def normalize_param_be(param_be_raw) -> Dict[str, Dict[str, int]]:
    """
    Accepte :
      - un DataFrame (colonnes Type / Priorite_Type / Equiv)
      - un dict {type: {Priorite_Type, Equiv}}
    Retourne toujours un dict normalisé :
      { "CN": {"Priorite_Type": 4, "Equiv": 1}, ... }
    """
    param_be: Dict[str, Dict[str, int]] = {}

    if isinstance(param_be_raw, pd.DataFrame):
        df = param_be_raw
        for _, row in df.iterrows():
            t = str(row.get("Type", "")).upper().strip()
            if not t:
                continue
            prio = row.get("Priorite_Type", 99)
            equiv = row.get("Equiv", 1)
            try:
                prio = int(prio)
            except (TypeError, ValueError, OverflowError):
                prio = 99
            try:
                equiv = int(equiv)
            except (TypeError, ValueError, OverflowError):
                equiv = 1
            param_be[t] = {"Priorite_Type": prio, "Equiv": equiv}

    elif isinstance(param_be_raw, dict):
        for t, vals in param_be_raw.items():
            key = str(t).upper().strip()
            if not isinstance(vals, dict):
                vals = {}
            prio = vals.get("Priorite_Type", vals.get("priorite_type", 99))
            equiv = vals.get("Equiv", vals.get("equiv", 1))
            try:
                prio = int(prio)
            except (TypeError, ValueError, OverflowError):
                prio = 99
            try:
                equiv = int(equiv)
            except (TypeError, ValueError, OverflowError):
                equiv = 1
            param_be[key] = {"Priorite_Type": prio, "Equiv": equiv}
    else:
        raise TypeError(f"ParamBE non supporté : type={type(param_be_raw)}")

    if "AUTRE" not in param_be:
        param_be["AUTRE"] = {"Priorite_Type": 99, "Equiv": 1}

    return param_be


# ============================================================
# 2) Chargement ParamBE depuis Excel (avec cache)
# ============================================================
def load_param_be(
    use_cache: bool = True,
    *,
    tdb_path: Path | None = None,
) -> Dict[str, Dict[str, int]]:
    """
    Charge ParamBE (normalisé via column_map_param_be).
    Format retourné :
      { "MM": {"Priorite_Type": 3, "Equiv": 1}, ... }
    """
    global _PARAM_BE_CACHE
    if tdb_path is not None:
        use_cache = False

    if use_cache and _PARAM_BE_CACHE is not None:
        return _PARAM_BE_CACHE

    logger.info("=== PARAM_BE : Chargement ===")

    df = load_and_normalize(
        path=(tdb_path or TABLEAU_DE_BORD),
        sheet_name=SHEET_PARAM_BE,
        mapping=column_map_param_be,
        header=0,
    )

    logger.info("Colonnes ParamBE détectées : %s", list(df.columns))
    try:
        logger.debug("Aperçu ParamBE:\n%s", df.head(10).to_string(index=False))
    except (AttributeError, KeyError, TypeError, ValueError):
        logger.debug("(Impossible d'afficher l'aperçu ParamBE)")

    param_be = normalize_param_be(df)

    expected_types = ["MM", "CN", "FR", "MED", "FRE", "MOB", "AUTRE", "JOUET", "JOUETS", "LAIT"]
    found_types = sorted(param_be.keys())
    missing = [t for t in expected_types if t not in found_types]
    logger.info("=== CHECK PARAM_BE ===")
    logger.info("Types trouvés       : %s", found_types)
    logger.info("Types manquants     : %s", missing)
    logger.info("======================")
    if missing:
        logger.warning(
            "ParamBE semble incomplet ; verifier column_map_param_be ou les noms de colonnes."
        )

    logger.info("=== PARAM_BE FINAL ===")
    for t in sorted(param_be.keys()):
        p = param_be[t]["Priorite_Type"]
        e = param_be[t]["Equiv"]
        logger.info("Type=%s -> Priorite=%s | Coeff Equiv=%s", t, p, e)
    logger.info("=================================")

    _PARAM_BE_CACHE = param_be
    return param_be


def reset_param_be_cache() -> None:
    global _PARAM_BE_CACHE
    _PARAM_BE_CACHE = None
