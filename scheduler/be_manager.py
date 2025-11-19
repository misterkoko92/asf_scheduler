# scheduler/be_manager.py
# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Dict, List
from scheduler.models import Shipment

from scheduler.config_paths import TABLEAU_DE_BORD, SHEET_PARAM_BE
import pandas as pd


# ======================================================================
# 1) Chargement ParamBE (depuis TABLEAU_DE_BORD / ParamBE)
# ======================================================================
def load_param_be() -> Dict[str, Dict]:
    """
    Charge ParamBE depuis TABLEAU_DE_BORD.xlsx / ParamBE
    et renvoie :
        {
            "MM": {"Priorite_Type": 3, "Equiv": 1},
            "CN": {"Priorite_Type": 2, "Equiv": 1},
            ...
        }
    """

    df = pd.read_excel(
        TABLEAU_DE_BORD,
        sheet_name=SHEET_PARAM_BE,
        dtype=str
    ).fillna("")

    param_be = {}

    for _, row in df.iterrows():
        t = str(row.get("Type", "")).upper().strip()
        if not t:
            continue

        # Lecture sécurisée
        try:
            prio = int(row.get("Priorite_Type", "99"))
        except:
            prio = 99

        try:
            equiv = int(row.get("Equiv", "1"))
        except:
            equiv = 1

        param_be[t] = {
            "Priorite_Type": prio,
            "Equiv": equiv,
        }

    # Valeur par défaut
    if "AUTRE" not in param_be:
        param_be["AUTRE"] = {"Priorite_Type": 99, "Equiv": 1}

    return param_be


# ======================================================================
# 2) Calcul priorité finale BE
# ======================================================================
def compute_be_priority(be: Shipment, param_be: Dict[str, Dict]) -> int:
    """
    Calcule la priorité finale d'un BE selon la règle officielle d’Édouard :
      1. Plannification Spéciale = OBLIGATOIRE → priorité 1
      2. Expéditeur ≠ ASF → priorité 2
      3. Priorité type (ParamBE)
    """

    # 1) Spécial OBLIGATOIRE
    special = (be.special or "").strip().upper()
    if special == "OBLIGATOIRE":
        return 1

    # 2) Expéditeur ≠ ASF
    exped = (be.expediteur or "").strip().upper()
    if exped not in ("", "ASF", "AVIATION SANS FRONTIERES", "AVIATION SANS FRONTIÈRES"):
        return 2

    # 3) Priorité type
    t = (be.type_colis or "").upper().strip()
    if t in param_be:
        return param_be[t]["Priorite_Type"]

    return param_be["AUTRE"]["Priorite_Type"]


# ======================================================================
# 3) Filtrage BE
# ======================================================================
def filter_shipments(shipments: List[Shipment]) -> List[Shipment]:
    """
    Retire les BE dont la colonne 'Plannification Spéciale' = Exclure.
    """
    out = []
    for be in shipments:
        special = (be.special or "").strip().lower()
        if special == "exclure":
            be.reason_not_planned = "Plannification Spéciale = Exclure"
            continue
        out.append(be)
    return out


# ======================================================================
# 4) Tri BE
# ======================================================================
def sort_shipments(shipments: List[Shipment]) -> List[Shipment]:
    """
    Trie les BE :
      1) priorité croissante
      2) NB colis physiques décroissant
    """
    return sorted(
        shipments,
        key=lambda s: (s.priority, -s.nb_colis_physiques)
    )
