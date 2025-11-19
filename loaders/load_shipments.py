# loaders/load_shipments.py
# -*- coding: utf-8 -*-

import pandas as pd
from typing import Dict, List, Tuple

from scheduler.models import Shipment
from scheduler.config_paths import (
    TABLEAU_DE_BORD,
    SHEET_PARAM_BE,
    SHEET_MAG_CENTRAL,
)


# ======================================================================
# 1) Chargement ParamBE (depuis TABLEAU_DE_BORD, feuille ParamBE)
# ======================================================================
def load_param_be() -> Dict[str, Tuple[int, int]]:
    """
    Charge ParamBE (dans TABLEAU_DE_BORD.xlsx / ParamBE) et renvoie :
        { TYPE_UPPER : (priorite_type, equiv) }
    """

    df = pd.read_excel(
        TABLEAU_DE_BORD,
        sheet_name=SHEET_PARAM_BE,
        dtype=str
    ).fillna("")

    mapping: Dict[str, Tuple[int, int]] = {}

    for _, r in df.iterrows():
        type_colis = str(r.get("Type", "")).upper().strip()
        if not type_colis:
            continue

        raw_prio = str(r.get("Priorite_Type", "")).strip()
        raw_equiv = str(r.get("Equiv", "")).strip()

        try:
            prio = int(raw_prio) if raw_prio else 99
        except:
            prio = 99

        try:
            equiv = int(raw_equiv) if raw_equiv else 1
        except:
            equiv = 1

        mapping[type_colis] = (prio, equiv)

    return mapping


# ======================================================================
# 2) Chargement des BE depuis TABLEAU_DE_BORD / MAG CENTRAL
# ======================================================================
def load_shipments() -> List[Shipment]:
    """
    Charge les BE directement depuis :
        TABLEAU_DE_BORD.xlsx / MAG CENTRAL
    + ParamBE (dans TABLEAU_DE_BORD aussi)

    Colonnes attendues :
        N° BE | NB | DEST | TYPE | Douane ? | EXP | Plannification Spéciale
        DATE CONDITIONNEMENT | DATE DE DEPART VOL
    """

    # ParamBE
    type_rules = load_param_be()

    # Tableau de bord (MAG CENTRAL)
    df = pd.read_excel(
        TABLEAU_DE_BORD,
        sheet_name=SHEET_MAG_CENTRAL,
        header=5,
        dtype=str
    ).fillna("")

    # Filtrer : planifiables
    df = df[
        (df["DATE CONDITIONNEMENT"].astype(str).str.strip() != "") &
        (df["DATE DE DEPART VOL"].astype(str).str.strip() == "")
    ]

    shipments: List[Shipment] = []

    for _, r in df.iterrows():
        be_numero = str(r.get("N° BE", "")).strip()
        if not be_numero:
            continue

        dest = str(r.get("DEST", "")).upper().strip()
        if not dest:
            continue

        # Nombre de colis physiques
        nb_raw = str(r.get("NB", "")).strip()
        try:
            nb_colis = int(float(nb_raw.replace(",", "."))) if nb_raw else 0
        except:
            nb_colis = 0

        type_colis = str(r.get("TYPE", "")).upper().strip()
        expediteur = str(r.get("EXP", "")).strip()
        special = str(r.get("Plannification Spéciale", "")).strip()
        douane_raw = str(r.get("Douane ?", "")).strip().upper()

        customs = douane_raw in ("OUI", "YES", "X")

        # ---- Priorité du type ----
        prio_type, equiv = type_rules.get(type_colis, (99, 1))

        # ---- Priorité finale ----
        special_upper = special.upper()
        expediteur_upper = expediteur.upper()

        if special_upper == "OBLIGATOIRE":
            priority = 1
        elif expediteur_upper not in ("", "ASF"):
            priority = 2
        else:
            priority = prio_type

        # ---- Équivalence ----
        equiv_colis = nb_colis * equiv

        # HF = colis hors format
        nb_hf = nb_colis if type_colis == "HF" else 0

        sh = Shipment(
            be_numero=be_numero,
            dest=dest,
            nb_colis_physiques=nb_colis,
            nb_hf=nb_hf,
            priority=priority,
            type_colis=type_colis,
            expediteur=expediteur,
            customs=customs,
            special=special if special else None,
            status="D",
            equiv_colis=equiv_colis,
        )

        shipments.append(sh)

    return shipments
