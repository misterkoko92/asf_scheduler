# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

import asf_app.services.be_placement_service as be_service
from asf_app.services.be_placement_service import BEPlacementError, place_be
from scheduler import config


def _planning(rows):
    return pd.DataFrame(rows)


def test_place_be_auto_selects_lightest_flight(monkeypatch):
    monkeypatch.setattr(config, "MAX_BE_PER_FLIGHT", 5)
    monkeypatch.setattr(config, "MAX_EQUIV_PER_VOLUNTEER", 100)
    monkeypatch.setattr(config, "MAX_CAPACITE_PAR_VOL", 100)

    planning = _planning(
        [
            {
                "Date_Vol": dt.date(2025, 1, 1),
                "Heure_Vol": "10:00",
                "Numero_Vol": "100",
                "Destination": "DLA",
                "BE_Numero": "250001",
                "BE_Nb_Colis": 8,
                "BE_Nb_Equiv": 8,
                "Benevole": "A",
                "ID": "1",
            },
            {
                "Date_Vol": dt.date(2025, 1, 1),
                "Heure_Vol": "10:00",
                "Numero_Vol": "100",
                "Destination": "DLA",
                "BE_Numero": "250002",
                "BE_Nb_Colis": 4,
                "BE_Nb_Equiv": 4,
                "Benevole": "A",
                "ID": "1",
            },
            {
                "Date_Vol": dt.date(2025, 1, 2),
                "Heure_Vol": "11:00",
                "Numero_Vol": "200",
                "Destination": "DLA",
                "BE_Numero": "250010",
                "BE_Nb_Colis": 2,
                "BE_Nb_Equiv": 2,
                "Benevole": "B",
                "ID": "2",
            },
        ]
    )

    out = place_be(planning, "250003", 2, "DLA", None, None, "")
    added = out[out["BE_Numero"] == "250003"].iloc[0]
    assert added["Numero_Vol"] == "200"
    assert added["Benevole"] == "B"


def test_place_be_semi_auto_without_flight_creates_manual(monkeypatch):
    monkeypatch.setattr(config, "MAX_BE_PER_FLIGHT", 5)
    monkeypatch.setattr(config, "MAX_EQUIV_PER_VOLUNTEER", 100)
    monkeypatch.setattr(config, "MAX_CAPACITE_PAR_VOL", 100)

    planning = _planning(
        [
            {
                "Date_Vol": dt.date(2025, 1, 1),
                "Heure_Vol": "10:00",
                "Numero_Vol": "100",
                "Destination": "DLA",
                "BE_Numero": "250001",
                "BE_Nb_Colis": 2,
                "BE_Nb_Equiv": 2,
                "Benevole": "A",
                "ID": "1",
            }
        ]
    )

    out = place_be(
        planning,
        "250020",
        1,
        "DLA",
        dt.date(2025, 1, 3),
        dt.time(9, 0),
        "",
    )
    added = out[out["BE_Numero"] == "250020"].iloc[0]
    assert added["Date_Vol"] == dt.date(2025, 1, 3)
    assert added["Benevole"] == ""
    assert added["Numero_Vol"] == ""


def test_place_be_forced_benevole_missing_raises(monkeypatch):
    monkeypatch.setattr(config, "MAX_BE_PER_FLIGHT", 5)
    monkeypatch.setattr(config, "MAX_EQUIV_PER_VOLUNTEER", 100)
    monkeypatch.setattr(config, "MAX_CAPACITE_PAR_VOL", 100)

    planning = _planning(
        [
            {
                "Date_Vol": dt.date(2025, 1, 1),
                "Heure_Vol": "10:00",
                "Numero_Vol": "100",
                "Destination": "DLA",
                "BE_Numero": "250001",
                "BE_Nb_Colis": 2,
                "BE_Nb_Equiv": 2,
                "Benevole": "A",
                "ID": "1",
            }
        ]
    )

    with pytest.raises(BEPlacementError):
        place_be(planning, "250030", 1, "DLA", None, None, "Z")


def test_place_be_auto_respects_capacity(monkeypatch):
    monkeypatch.setattr(config, "MAX_BE_PER_FLIGHT", 1)
    monkeypatch.setattr(config, "MAX_EQUIV_PER_VOLUNTEER", 5)
    monkeypatch.setattr(config, "MAX_CAPACITE_PAR_VOL", 5)

    planning = _planning(
        [
            {
                "Date_Vol": dt.date(2025, 1, 1),
                "Heure_Vol": "10:00",
                "Numero_Vol": "100",
                "Destination": "DLA",
                "BE_Numero": "250001",
                "BE_Nb_Colis": 5,
                "BE_Nb_Equiv": 5,
                "Benevole": "A",
                "ID": "1",
            }
        ]
    )

    with pytest.raises(BEPlacementError):
        place_be(planning, "250040", 1, "DLA", None, None, "")


def test_norm_str_returns_empty_on_runtime_error():
    class _BadStr:
        def __str__(self):
            raise RuntimeError("boom")

    assert be_service._norm_str(_BadStr()) == ""
