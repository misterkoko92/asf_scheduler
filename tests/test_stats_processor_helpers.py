# -*- coding: utf-8 -*-
from __future__ import annotations

import pandas as pd
import pytest

pytest.importorskip("reportlab")
from asf_app.ui.ui_stats import stats_processor as sp  # noqa: E402


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": "2026-01-19",
                "heure": "11:00",
                "date_transfert": "2026-01-19 08:00",
                "nb_colis": 10,
                "destination_iata": "DLA",
                "expediteur": "ASF",
                "vol_info": "AF822",
                "nom": "ALICE DUPONT",
                "be": "260001",
                "week": 4,
            },
            {
                "date": "2026-01-19",
                "heure": "13:00",
                "date_transfert": "2026-01-19 10:30",
                "nb_colis": 5,
                "destination_iata": "RUN",
                "expediteur": "MEDILAB",
                "vol_info": "AF652",
                "nom": "BOB MARTIN",
                "be": "260002",
                "week": 4,
            },
            {
                "date": "2026-01-20",
                "heure": "14:30",
                "date_transfert": "2026-01-20 13:00",
                "nb_colis": 7,
                "destination_iata": "DLA",
                "expediteur": "ASF",
                "vol_info": "AF948",
                "nom": "ALICE DUPONT",
                "be": "260003",
                "week": 4,
            },
        ]
    )


def test_compute_kpis_daily_load_and_groupings():
    df = _sample_df()

    kpis = sp.compute_kpis(df)
    assert kpis["total_be"] == 3
    assert kpis["total_colis"] == 22
    assert kpis["nb_dest"] == 2
    assert kpis["nb_expediteurs"] == 2
    assert kpis["nb_vols"] == 3
    assert abs(float(kpis["colis_par_be"]) - (22 / 3)) < 1e-9

    per_day = sp.daily_load(df)
    assert int(per_day.loc[pd.Timestamp("2026-01-19").date()]) == 15
    assert int(per_day.loc[pd.Timestamp("2026-01-20").date()]) == 7

    per_flight = sp.load_per_flight(df)
    assert int(per_flight.loc[("DLA", "AF822")]) == 10
    assert int(per_flight.loc[("RUN", "AF652")]) == 5

    by_dest = sp.group_by_destination(df)
    assert by_dest.index.tolist()[0] == "DLA"
    assert int(by_dest.loc["DLA"]) == 17

    by_exp = sp.group_by_expediteur(df)
    assert int(by_exp.loc["ASF"]) == 17
    assert int(by_exp.loc["MEDILAB"]) == 5

    by_bene = sp.group_by_benevole(df)
    assert int(by_bene.loc["ALICE DUPONT"]) == 2
    assert int(by_bene.loc["BOB MARTIN"]) == 1

    by_week = sp.group_by_week(df)
    assert int(by_week.loc[4]) == 22


def test_pivot_helpers_build_expected_tables():
    df = _sample_df()

    piv_dest_week = sp.pivot_dest_week(df)
    assert int(piv_dest_week.loc["DLA", 4]) == 17
    assert int(piv_dest_week.loc["RUN", 4]) == 5

    piv_day_dest = sp.pivot_day_dest(df)
    assert "DLA" in piv_day_dest.columns
    assert "RUN" in piv_day_dest.columns
    assert int(piv_day_dest["DLA"].sum()) == 17
    assert int(piv_day_dest["RUN"].sum()) == 5


def test_compute_transfer_delay_valid_series_hours():
    df = _sample_df()
    out = sp.compute_transfer_delay(df)

    assert isinstance(out, pd.Series)
    assert len(out) == len(df)
    # 11:00 - 08:00 = 3h
    assert abs(float(out.iloc[0]) - 3.0) < 1e-9
    # 13:00 - 10:30 = 2.5h
    assert abs(float(out.iloc[1]) - 2.5) < 1e-9


def test_compute_transfer_delay_missing_required_columns_returns_empty():
    out = sp.compute_transfer_delay(pd.DataFrame({"date": ["2026-01-01"]}))
    assert isinstance(out, pd.Series)
    assert out.empty


def test_compute_transfer_delay_returns_empty_when_invalid():
    df = pd.DataFrame(
        {
            "date": ["not-a-date"],
            "heure": ["bad-time"],
            "date_transfert": ["also-bad"],
        }
    )

    out = sp.compute_transfer_delay(df)

    assert isinstance(out, pd.Series)
    assert out.empty or out.isna().all()
