# -*- coding: utf-8 -*-
from __future__ import annotations

from scheduler.solver_router import get_solver_version


def test_solver_router_env_switch(monkeypatch):
    monkeypatch.delenv("ASF_SOLVER_VERSION", raising=False)
    assert get_solver_version() == "v3"

    monkeypatch.setenv("ASF_SOLVER_VERSION", "v3")
    assert get_solver_version() == "v3"

    monkeypatch.setenv("ASF_SOLVER_VERSION", "2")
    assert get_solver_version() == "v2"
