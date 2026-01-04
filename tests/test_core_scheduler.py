# -*- coding: utf-8 -*-
from __future__ import annotations

import pandas as pd
import pytest

import scheduler.core_scheduler as core_scheduler
from scheduler.core_scheduler import Scheduler
from scheduler.planning_schema import SCHEMA


def test_scheduler_run_normalizes(monkeypatch):
    planning_raw = pd.DataFrame(
        [
            {
                "DATE": "01/01/2025",
                "HEURE VOL": "10:00",
                "NUMERO VOL": "AF 1234",
                "IATA": "dla",
                "BE_Num": "250001",
                "NOMBRE COLIS": 2,
                "BE_Poids_Equiv": 2,
                "BENEVOLE": "Dupont",
                "ID": "1",
            }
        ]
    )
    bilan_raw = pd.DataFrame([{"ok": True}])
    stats = {"status": "OPTIMAL", "nb_be_total": 1, "nb_be_envoyes": 1}

    captured: dict = {}

    def _fake_solver(**kwargs):
        captured.update(kwargs)
        return planning_raw, bilan_raw, stats

    monkeypatch.setattr(core_scheduler, "solve_planning_ortools", _fake_solver)

    scheduler = Scheduler(data_source_name="excel")
    planning_df, _ = scheduler.run()

    assert list(planning_df.columns) == SCHEMA.columns
    assert planning_df.loc[0, "Numero_Vol"] == "1234"
    assert planning_df.loc[0, "Destination"] == "DLA"
    assert planning_df.loc[0, "BE_Numero"] == "250001"
    assert captured.get("data_source_name") == "excel"
    assert scheduler.run_stats["vols_with_be"] == 1
    assert scheduler.run_stats["benevoles_used"] == 1


def test_scheduler_requires_ortools(monkeypatch):
    monkeypatch.setattr(
        core_scheduler,
        "solve_planning_ortools",
        lambda **kwargs: (pd.DataFrame(), pd.DataFrame(), {"status": "ORTOOLS_MISSING"}),
    )

    scheduler = Scheduler()
    with pytest.raises(RuntimeError):
        scheduler.run()
