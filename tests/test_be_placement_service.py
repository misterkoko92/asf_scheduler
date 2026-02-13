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


def test_extract_flights_returns_empty_schema_when_planning_is_empty():
    out = be_service._extract_flights_from_planning(pd.DataFrame())
    assert list(out.columns) == [
        "Date_Vol",
        "Heure_Vol",
        "Numero_Vol",
        "Destination",
        "nb_be",
        "total_equiv",
        "benevoles",
    ]
    assert out.empty


def test_extract_flights_uses_nb_colis_when_equiv_column_missing():
    planning = _planning(
        [
            {
                "Date_Vol": dt.date(2025, 1, 1),
                "Heure_Vol": "10:00",
                "Numero_Vol": "100",
                "Destination": "DLA",
                "BE_Numero": "250001",
                "BE_Nb_Colis": 3,
                "Benevole": "A",
            }
        ]
    )
    out = be_service._extract_flights_from_planning(planning)
    assert float(out.iloc[0]["total_equiv"]) == 3.0


def test_choose_best_benevole_returns_empty_when_none_on_flight():
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
                "Benevole": "",
            }
        ]
    )
    out = be_service._choose_best_benevole_on_flight(planning, dt.date(2025, 1, 1), "10:00", "100", 1)
    assert out == ""


def test_place_be_without_number_raises():
    with pytest.raises(BEPlacementError, match="sans numéro"):
        place_be(pd.DataFrame(), "", 1, "DLA", None, None, "")


def test_place_be_manual_reuses_existing_flight_number_on_same_day_and_destination(monkeypatch):
    monkeypatch.setattr(config, "MAX_BE_PER_FLIGHT", 5)
    monkeypatch.setattr(config, "MAX_EQUIV_PER_VOLUNTEER", 100)
    monkeypatch.setattr(config, "MAX_CAPACITE_PAR_VOL", 100)

    planning = _planning(
        [
            {
                "Date_Vol": dt.date(2025, 1, 3),
                "Heure_Vol": "09:00",
                "Numero_Vol": "200",
                "Destination": "RUN",
                "BE_Numero": "250010",
                "BE_Nb_Colis": 1,
                "BE_Nb_Equiv": 1,
                "Benevole": "A",
                "ID": "1",
            }
        ]
    )

    out = place_be(
        planning,
        "250011",
        1,
        "RUN",
        dt.date(2025, 1, 3),
        dt.time(9, 30),
        "B",
    )
    added = out[out["BE_Numero"] == "250011"].iloc[0]
    assert added["Numero_Vol"] == "200"
    assert added["Benevole"] == "B"


def test_place_be_auto_raises_when_no_flight_exists(monkeypatch):
    monkeypatch.setattr(config, "MAX_BE_PER_FLIGHT", 5)
    monkeypatch.setattr(config, "MAX_EQUIV_PER_VOLUNTEER", 100)
    monkeypatch.setattr(config, "MAX_CAPACITE_PAR_VOL", 100)

    with pytest.raises(BEPlacementError, match="Aucun vol existant"):
        place_be(pd.DataFrame(), "250050", 1, "DLA", None, None, "")


def test_place_be_semi_auto_raises_when_capacity_on_day_is_exceeded(monkeypatch):
    monkeypatch.setattr(config, "MAX_BE_PER_FLIGHT", 5)
    monkeypatch.setattr(config, "MAX_EQUIV_PER_VOLUNTEER", 2)
    monkeypatch.setattr(config, "MAX_CAPACITE_PAR_VOL", 2)

    planning = _planning(
        [
            {
                "Date_Vol": dt.date(2025, 1, 4),
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

    with pytest.raises(BEPlacementError, match="Pas de vol compatible en capacité"):
        place_be(
            planning,
            "250060",
            1,
            "DLA",
            dt.date(2025, 1, 4),
            dt.time(10, 0),
            "",
        )


def test_place_be_forced_benevole_capacity_error(monkeypatch):
    monkeypatch.setattr(config, "MAX_BE_PER_FLIGHT", 5)
    monkeypatch.setattr(config, "MAX_EQUIV_PER_VOLUNTEER", 2)
    monkeypatch.setattr(config, "MAX_CAPACITE_PAR_VOL", 2)

    planning = _planning(
        [
            {
                "Date_Vol": dt.date(2025, 1, 5),
                "Heure_Vol": "11:00",
                "Numero_Vol": "300",
                "Destination": "DLA",
                "BE_Numero": "250070",
                "BE_Nb_Colis": 2,
                "BE_Nb_Equiv": 2,
                "Benevole": "A",
                "ID": "1",
            }
        ]
    )

    with pytest.raises(BEPlacementError, match="capacité requise"):
        place_be(planning, "250071", 1, "DLA", None, None, "A")
