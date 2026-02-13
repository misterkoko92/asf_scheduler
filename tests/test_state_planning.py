# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from asf_app.ui.ui_planning import state_planning


def test_planning_state_setters_and_getters():
    ps = state_planning.PlanningState()
    planning_df = pd.DataFrame([{"BE_Numero": "260001"}])
    bilan_df = pd.DataFrame([{"BE_Numero": "260001", "Partant": "OUI"}])

    ps.set_planning(planning_df, bilan_df)
    ps.set_last_export_path("/tmp/planning.xlsx")

    assert ps.planning.equals(planning_df)
    assert ps.bilan.equals(bilan_df)
    assert ps.last_export_path == "/tmp/planning.xlsx"


def test_planning_state_set_planning_rejects_invalid_payload():
    ps = state_planning.PlanningState()
    with pytest.raises(ValueError):
        ps.set_planning("not-a-dataframe")


def test_get_planning_state_initializes_when_missing(monkeypatch):
    fake_st = SimpleNamespace(session_state={})
    monkeypatch.setattr(state_planning, "st", fake_st)

    ps = state_planning.get_planning_state()
    assert isinstance(ps, state_planning.PlanningState)
    assert fake_st.session_state["planning_state"] is ps


def test_get_planning_state_reuses_existing_object(monkeypatch):
    existing = state_planning.PlanningState()
    fake_st = SimpleNamespace(session_state={"planning_state": existing})
    monkeypatch.setattr(state_planning, "st", fake_st)

    ps = state_planning.get_planning_state()
    assert ps is existing


def test_get_planning_state_upgrades_legacy_object(monkeypatch):
    legacy = SimpleNamespace(foo="bar")
    fake_st = SimpleNamespace(session_state={"planning_state": legacy})
    monkeypatch.setattr(state_planning, "st", fake_st)

    ps = state_planning.get_planning_state()
    assert isinstance(ps, state_planning.PlanningState)
    assert ps is fake_st.session_state["planning_state"]
