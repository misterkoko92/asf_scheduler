# scheduler/be_manager.py
# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Dict, List

import pandas as pd

from scheduler.models import Shipment
from scheduler.config_paths import (
    TABLEAU_DE_BORD,
    SHEET_PARAM_BE,
)

from loaders.universal_loader import load_and_normalize
from scheduler.column_map import column_map_param_be

# Nouvelles règles métier centralisées
from scheduler.be_rules import (
    ASF_EQUIV,
    is_expediteur_asf,
    compute_be_priority,
    compute_equiv_colis,
    is_planifiable_status,
    STATUS_PLANIFIABLE,
)


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
            except Exception:
                prio = 99
            try:
                equiv = int(equiv)
            except Exception:
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
            except Exception:
                prio = 99
            try:
                equiv = int(equiv)
            except Exception:
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
def load_param_be(use_cache: bool = True) -> Dict[str, Dict[str, int]]:
    """
    Charge ParamBE (normalisé via column_map_param_be).
    Format retourné :
      { "MM": {"Priorite_Type": 3, "Equiv": 1}, ... }
    """
    global _PARAM_BE_CACHE
    if use_cache and _PARAM_BE_CACHE is not None:
        return _PARAM_BE_CACHE

    print("=== PARAM_BE : Chargement ===")

    df = load_and_normalize(
        path=TABLEAU_DE_BORD,
        sheet_name=SHEET_PARAM_BE,
        mapping=column_map_param_be,
        header=0,
    )

    print(f"Colonnes ParamBE détectées : {list(df.columns)}")
    try:
        print(df.head(10))
    except Exception:
        print("(Impossible d'afficher l'aperçu ParamBE)")

    param_be = normalize_param_be(df)

    expected_types = ["MM", "CN", "FR", "MED", "FRE", "MOB", "AUTRE", "JOUET", "JOUETS", "LAIT"]
    found_types = sorted(param_be.keys())
    missing = [t for t in expected_types if t not in found_types]
    print("=== CHECK PARAM_BE ===")
    print("Types trouvés       :", found_types)
    print("Types manquants     :", missing)
    print("======================")
    if missing:
        print("⚠️ WARNING : ParamBE semble incomplet ! Vérifie column_map_param_be ou les noms de colonnes.")

    print("\n=== PARAM_BE FINAL ===")
    for t in sorted(param_be.keys()):
        p = param_be[t]["Priorite_Type"]
        e = param_be[t]["Equiv"]
        print(f"Type={t} → Priorité={p} | Coeff Equiv={e}")
    print("=================================\n")

    _PARAM_BE_CACHE = param_be
    return param_be


# ============================================================
# 5) Filtrer exclusions (compatibilité + statut)
# ============================================================

def filter_shipments(shipments: List[Shipment]) -> List[Shipment]:
    """
    Filtre les BE non planifiables selon leur statut.
    - Si Shipment.status est défini et != PLANIFIABLE → exclusion
    - Sinon (legacy) : on applique encore le filtre special == 'exclure'
    Ajoute une raison sur le Shipment (reason_not_planned).
    """
    out: List[Shipment] = []
    excluded = 0

    for s in shipments:
        status = getattr(s, "status", None)

        if status is not None:
            if not is_planifiable_status(status):
                reason = getattr(s, "reason_not_planned", None)
                if not reason:
                    s.reason_not_planned = f"Status={status}"
                excluded += 1
                continue
        else:
            # Legacy : si pas de statut, on conserve l'ancien comportement
            if str(s.special or "").lower().strip() == "exclure":
                s.reason_not_planned = "Spécial = Exclure"
                excluded += 1
                continue

        out.append(s)

    print("\n=== FILTRE BE : EXCLUSIONS / STATUT ===")
    print(f"Total entrées      : {len(shipments)}")
    print(f"Total exclues      : {excluded}")
    print(f"Total conservées   : {len(out)}")
    print("=================================\n")
    return out


# ============================================================
# 6) Tri final
# ============================================================

def sort_shipments(shipments: List[Shipment]) -> List[Shipment]:
    """
    Trie les BE :
      - par priorité (croissant)
      - puis par nb équiv-colis (décroissant)
    """
    sorted_list = sorted(
        shipments,
        key=lambda s: (
            s.priority,
            -int(getattr(s, "equiv_colis", s.nb_colis_physiques)),
        ),
    )

    print("\n=== TRI FINAL DES BE ===")
    for s in sorted_list:
        print(
            f" - BE {s.be_numero} | Priorité={s.priority} | Equiv={s.equiv_colis}"
        )
    print("=================================\n")

    return sorted_list
