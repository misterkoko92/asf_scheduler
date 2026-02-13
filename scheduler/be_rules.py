# scheduler/be_rules.py
# -*- coding: utf-8 -*-
"""
Règles métier des BE :
  - Statuts (planifiable ou non, et pourquoi)
  - Priorité
  - Équivalents colis
"""

from __future__ import annotations

import logging
from typing import Any, Dict

import pandas as pd

from scheduler.models import Shipment

logger = logging.getLogger("ASF-SCHEDULER")


# =============================================================================
#  STATUTS BE
# =============================================================================

STATUS_PLANIFIABLE = "PLANIFIABLE"
STATUS_EXCLUS_SPECIAL = "EXCLUS_SPECIAL"
STATUS_DEJA_PLANIFIE = "DEJA_PLANIFIE"
STATUS_INCOMPLET_DEST = "INCOMPLET_DEST"
STATUS_INCOMPLET_COND = "INCOMPLET_CONDITIONNEMENT"
STATUS_NON_PLANIFIABLE_AUTRE = "NON_PLANIFIABLE_AUTRE"


def is_empty_date(x: Any) -> bool:
    """
    Détection simple d'une "date vide".
    Utilisé pour compat éventuelle ailleurs, mais pour le statut on se base
    sur pd.isna(x) après conversion stricte (coerce) dans load_shipments_df.

    Ici, on considère vide uniquement NaN / NaT.
    """
    return pd.isna(x)


def compute_status_row(row: "pd.Series") -> str:
    """
    Calcule le statut d'un BE à partir d'une ligne normalisée de MAG CENTRAL.

    ⚠ IMPORTANT :
      - On suppose que :
          * BE_Date_Conditionnement a déjà été converti par pd.to_datetime(..., errors='coerce')
          * BE_Date_Vol a déjà été converti par pd.to_datetime(..., errors='coerce')
          * Destination est déjà strip()
          * BE_Special est déjà en minuscules, strip()

      - La logique est STRICTEMENT alignée sur test_mag_central.py / debug_planif.py.

    Règles (ordre de priorité pour la raison) :

      1) Plannification Spéciale == 'exclure' ou 'exclu'  → EXCLUS_SPECIAL
      2) Date de vol NON vide (BE_Date_Vol notna)        → DEJA_PLANIFIE
         (c'est la SEULE source fiable pour savoir si déjà planifié)
      3) Destination vide / "nan"                        → INCOMPLET_DEST
      4) Date de conditionnement vide (NaT)              → INCOMPLET_COND
      5) Sinon                                           → PLANIFIABLE
    """
    dest = str(row.get("Destination", "")).strip()
    date_cond = row.get("BE_Date_Conditionnement")
    date_vol = row.get("BE_Date_Vol")
    special = str(row.get("BE_Special", "")).strip().lower()

    # 1) EXCLURE
    if special in ("exclure", "exclu"):
        return STATUS_EXCLUS_SPECIAL

    # 2) Vol déjà planifié → on se base UNIQUEMENT sur le fait que la date
    #    de vol soit non nulle après conversion stricte (coerce).
    if pd.notna(date_vol):
        return STATUS_DEJA_PLANIFIE

    # 3) Destination manquante
    if dest == "" or dest.lower() == "nan":
        return STATUS_INCOMPLET_DEST

    # 4) Conditionnement manquant
    if pd.isna(date_cond):
        return STATUS_INCOMPLET_COND

    # 5) Tout est OK → planifiable
    return STATUS_PLANIFIABLE


def is_planifiable_status(status: str | None) -> bool:
    """Retourne True si le statut correspond à un BE planifiable."""
    return status == STATUS_PLANIFIABLE


# =============================================================================
#  PRIORITÉ & ÉQUIV COLIS (ParamBE)
# =============================================================================

# Normalisation expéditeur ASF
ASF_EQUIV = {
    "ASF", "A S F", "AS F", "A.S.F",
    "AVIATION SANS FRONTIERES", "AVIATION SANS FRONTIÈRES",
    "AVIATION SANS FRONTIERES FRANCE", "AVIATION SANS FRONTIÈRES FRANCE",
    "AVIATION SANS FRONTIERES - FRANCE",
    "",
}


def is_expediteur_asf(s: Shipment) -> bool:
    """True si l'expéditeur du Shipment est ASF (normalisé)."""
    v = (s.expediteur or "").upper().replace(".", "").strip()
    return v in ASF_EQUIV


def compute_be_priority(be: Shipment, param_be: Dict[str, Dict]) -> int:
    """
    Calcule la priorité finale d'un BE à partir de :
      - BE.special (OBLIGATOIRE)
      - expéditeur ASF / non-ASF
      - type colis (ParamBE.Priorite_Type)

    Règles :
      1) SPECIAL=OBLIGATOIRE → priorité 1
      2) Non ASF              → priorité 2
      3) Sinon, ParamBE[type] (ou AUTRE si inconnu)
    """
    # 1) Obligatoire
    special = (be.special or "").strip().upper()
    if special == "OBLIGATOIRE":
        prio = 1
        logger.info(
            "[PRIORITE] BE %s -> SPECIAL=OBLIGATOIRE -> Priorite=%s",
            be.be_numero,
            prio,
        )
        return prio

    # 2) Non ASF
    if not is_expediteur_asf(be):
        prio = 2
        logger.info("[PRIORITE] BE %s -> NON-ASF -> Priorite=%s", be.be_numero, prio)
        return prio

    # 3) Priorité par type
    t = (be.type_colis or "").strip().upper()
    if t in param_be:
        prio = int(param_be[t]["Priorite_Type"])
        logger.info("[PRIORITE] BE %s -> Type=%s -> Priorite=%s", be.be_numero, t, prio)
        return prio

    prio = int(param_be["AUTRE"]["Priorite_Type"])
    logger.info(
        "[PRIORITE] BE %s -> Type=%s (fallback) -> Priorite=%s",
        be.be_numero,
        t or "AUTRE",
        prio,
    )
    return prio


def compute_equiv_colis(be: Shipment, param_be: Dict[str, Dict]) -> int:
    """
    Calcule les "colis équivalents" (unités de capacité) pour un BE.

    Nouvelle règle (HF intégré dans ParamBE, plus de traitement spécifique HF) :

      - ParamBE.Equiv est un *coefficient multiplicateur* par colis réel.
        * Type = MM, Equiv = 1  → 10 colis réels = 10 équivalents
        * Type = FR, Equiv = 5  → 10 colis réels = 50 équivalents

    Formule :
        Equiv_total = nb_colis_physiques * coeff_equiv

    Si le résultat est <= 0, on force à 1 (BE minimal).
    """
    t = (be.type_colis or "").strip().upper()
    coeff = int(param_be.get(t, param_be["AUTRE"])["Equiv"])

    nb_colis = int(be.nb_colis_physiques or 0)

    equiv_total = nb_colis * coeff
    if equiv_total <= 0:
        equiv_total = 1

    logger.info(
        "[EQUIV] BE %s | Type=%s | Colis=%s | Coeff=%s -> Equiv_total=%s",
        be.be_numero,
        t,
        nb_colis,
        coeff,
        equiv_total,
    )

    return equiv_total
