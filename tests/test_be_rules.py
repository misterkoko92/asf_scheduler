# -*- coding: utf-8 -*-
from __future__ import annotations

import pandas as pd

from scheduler.be_rules import (
    STATUS_DEJA_PLANIFIE,
    STATUS_EXCLUS_SPECIAL,
    STATUS_INCOMPLET_COND,
    STATUS_INCOMPLET_DEST,
    STATUS_PLANIFIABLE,
    compute_be_priority,
    compute_equiv_colis,
    compute_status_row,
    is_expediteur_asf,
)
from scheduler.models import Shipment


def test_compute_status_row_precedence():
    row = pd.Series(
        {
            "Destination": "DLA",
            "BE_Date_Conditionnement": pd.to_datetime("2025-01-01"),
            "BE_Date_Vol": pd.NaT,
            "BE_Special": "exclure",
        }
    )
    assert compute_status_row(row) == STATUS_EXCLUS_SPECIAL

    row = pd.Series(
        {
            "Destination": "DLA",
            "BE_Date_Conditionnement": pd.to_datetime("2025-01-01"),
            "BE_Date_Vol": pd.to_datetime("2025-01-02"),
            "BE_Special": "",
        }
    )
    assert compute_status_row(row) == STATUS_DEJA_PLANIFIE

    row = pd.Series(
        {
            "Destination": "",
            "BE_Date_Conditionnement": pd.to_datetime("2025-01-01"),
            "BE_Date_Vol": pd.NaT,
            "BE_Special": "",
        }
    )
    assert compute_status_row(row) == STATUS_INCOMPLET_DEST

    row = pd.Series(
        {
            "Destination": "DLA",
            "BE_Date_Conditionnement": pd.NaT,
            "BE_Date_Vol": pd.NaT,
            "BE_Special": "",
        }
    )
    assert compute_status_row(row) == STATUS_INCOMPLET_COND

    row = pd.Series(
        {
            "Destination": "DLA",
            "BE_Date_Conditionnement": pd.to_datetime("2025-01-01"),
            "BE_Date_Vol": pd.NaT,
            "BE_Special": "",
        }
    )
    assert compute_status_row(row) == STATUS_PLANIFIABLE


def test_priority_and_equiv():
    param_be = {"MM": {"Priorite_Type": 3, "Equiv": 2}, "AUTRE": {"Priorite_Type": 99, "Equiv": 1}}

    be = Shipment(
        be_numero="250001",
        dest="DLA",
        nb_colis_physiques=2,
        nb_hf=0,
        priority=0,
        type_colis="MM",
        expediteur="ASF",
        special="OBLIGATOIRE",
    )
    assert compute_be_priority(be, param_be) == 1
    assert compute_equiv_colis(be, param_be) == 4

    be.special = ""
    be.expediteur = "Other"
    assert compute_be_priority(be, param_be) == 2

    be.expediteur = "ASF"
    be.type_colis = "UNKNOWN"
    assert compute_be_priority(be, param_be) == 99


def test_is_expediteur_asf():
    be = Shipment(
        be_numero="250001",
        dest="DLA",
        nb_colis_physiques=1,
        nb_hf=0,
        priority=0,
        type_colis="MM",
        expediteur="A.S.F",
    )
    assert is_expediteur_asf(be) is True
    be.expediteur = "Partner"
    assert is_expediteur_asf(be) is False


def test_priority_and_equiv_emit_logs(caplog):
    caplog.set_level("INFO", logger="ASF-SCHEDULER")
    param_be = {"MM": {"Priorite_Type": 3, "Equiv": 2}, "AUTRE": {"Priorite_Type": 99, "Equiv": 1}}
    be = Shipment(
        be_numero="260001",
        dest="RUN",
        nb_colis_physiques=2,
        nb_hf=0,
        priority=0,
        type_colis="MM",
        expediteur="ASF",
        special="",
    )

    assert compute_be_priority(be, param_be) == 3
    assert compute_equiv_colis(be, param_be) == 4
    assert "[PRIORITE] BE 260001" in caplog.text
    assert "[EQUIV] BE 260001" in caplog.text
