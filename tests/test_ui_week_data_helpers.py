# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timedelta, date

import pandas as pd

from asf_app.ui.ui_week_data_helpers import (
    _time_to_minutes,
    _minutes_to_hhmm,
    _compute_week_dates,
    _build_day_labels,
    _build_benev_week_table,
    _build_benev_ranges_by_date,
    _build_flights_week_table,
)


def _week_4_2026_dates() -> list[datetime]:
    monday = datetime.fromisocalendar(2026, 4, 1)
    return [monday + timedelta(days=i) for i in range(7)]


def test_time_minutes_helpers():
    assert _time_to_minutes("10h30") == 630
    assert _time_to_minutes("invalid") is None
    assert _minutes_to_hhmm(630) == "10h30"
    assert _minutes_to_hhmm(None) == ""


def test_compute_week_dates_from_api_start_date():
    out = _compute_week_dates(
        api_start_date="2026-01-23",
        week=None,
        df_benev=None,
        df_flights=None,
    )
    assert len(out) == 7
    assert out[0].date() == date(2026, 1, 19)
    assert out[-1].date() == date(2026, 1, 25)


def test_compute_week_dates_week_fallback_uses_today_year():
    out = _compute_week_dates(
        api_start_date=None,
        week=5,
        df_benev=pd.DataFrame(),
        df_flights=pd.DataFrame(),
        today=pd.Timestamp("2026-02-01"),
    )
    assert len(out) == 7
    assert out[0].date() == date(2026, 1, 26)
    assert out[-1].date() == date(2026, 2, 1)


def test_build_benev_week_table_aggregates_ranges_and_mask():
    week_dates = _week_4_2026_dates()
    day_labels = _build_day_labels(week_dates)
    df_benev = pd.DataFrame(
        [
            {"Nom": "ALICE", "Date": "19/01/26", "Arrivée": "10:00", "Départ": "12:00"},
            {"Nom": "ALICE", "Date": "19/01/26", "Arrivée": "09:30", "Départ": "13:15"},
            {"Nom": "BOB", "Date": "20/01/26", "Arrivée": "", "Départ": "11:00"},
        ]
    )
    table, mask = _build_benev_week_table(
        df_benev,
        week_dates=week_dates,
        day_labels=day_labels,
    )
    monday = day_labels[0]
    assert table.loc["ALICE (1)", (monday, "Début")] == "09h30"
    assert table.loc["ALICE (1)", (monday, "Fin")] == "13h15"
    assert bool(mask.loc["ALICE (1)", (monday, "Début")]) is True
    assert bool(mask.loc["ALICE (1)", (monday, "Fin")]) is True
    # Bob présent mais sans créneau valide -> compteur 0, cellules vides
    assert "BOB (0)" in table.index


def test_build_benev_ranges_by_date_keeps_only_valid_ranges():
    df_benev = pd.DataFrame(
        [
            {"Nom": "ALICE", "Date": "19/01/26", "Arrivée": "10:00", "Départ": "12:00"},
            {"Nom": "BOB", "Date": "20/01/26", "Arrivée": "", "Départ": "11:00"},
        ]
    )
    out = _build_benev_ranges_by_date(df_benev)
    assert list(out.keys()) == [date(2026, 1, 19)]
    assert out[date(2026, 1, 19)] == [(600, 720)]


def test_build_flights_week_table_compatibility_and_counts():
    week_dates = _week_4_2026_dates()
    day_labels = _build_day_labels(week_dates)
    df_flights = pd.DataFrame(
        [
            {
                "Destination": "RUN",
                "Date": "19/01/26",
                "Heure": "10:30",
                "Routing": "CDG-RUN",
                "Numero_Vol": "AF652",
            },
            {
                "Destination": "RUN",
                "Date": "19/01/26",
                "Heure": "18:00",
                "Routing": "CDG-RUN",
                "Numero_Vol": "AF654",
            },
            {
                "Destination": "DLA",
                "Date": "20/01/26",
                "Heure": "08:00",
                "Routing": "CDG-DLA",
                "Numero_Vol": "AF968",
            },
        ]
    )
    df_be = pd.DataFrame(
        [
            {"Destination": "RUN", "Nb_Colis": 3},
            {"Destination": "DLA", "Nb_Colis": 1},
        ]
    )
    benev_by_date = {date(2026, 1, 19): [(600, 720)]}

    table, status = _build_flights_week_table(
        df_flights,
        df_be=df_be,
        week_dates=week_dates,
        day_labels=day_labels,
        benev_by_date=benev_by_date,
    )
    monday = day_labels[0]
    tuesday = day_labels[1]
    assert "RUN (3)" in table.index
    assert "DLA (1)" in table.index
    assert status.loc["RUN (3)", monday] == "compatible"
    assert status.loc["DLA (1)", tuesday] == "incompatible"
    assert "AF 652 - RUN" in table.loc["RUN (3)", monday]


def test_build_flights_week_table_empty_input():
    table, status = _build_flights_week_table(
        pd.DataFrame(),
        df_be=pd.DataFrame(),
        week_dates=_week_4_2026_dates(),
        day_labels=_build_day_labels(_week_4_2026_dates()),
        benev_by_date={},
    )
    assert table.empty
    assert status.empty
