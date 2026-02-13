# -*- coding: utf-8 -*-
from __future__ import annotations

import pandas as pd
import pytest

pytest.importorskip("reportlab")
from asf_app.ui.ui_stats import stats_loader as sl  # noqa: E402


def test_load_all_plannings_keeps_week_none_when_parse_fails(monkeypatch, tmp_path):
    planning_file = tmp_path / "ASFmm - PLANNING SEMAINE weird.xlsx"
    planning_file.write_text("x", encoding="utf-8")

    monkeypatch.setattr(sl, "load_planning_xlsx", lambda path: pd.DataFrame([{"a": 1}]))

    def _raise(*args, **kwargs):
        raise ValueError("regex error")

    monkeypatch.setattr(sl.re, "search", _raise)

    out = sl.load_all_plannings(tmp_path)

    assert len(out) == 1
    assert "week" in out.columns
    assert out.iloc[0]["week"] is None
