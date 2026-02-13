# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("reportlab")
from asf_app.ui.ui_stats import stats_loader as sl  # noqa: E402


def test_load_all_plannings_returns_empty_when_no_matching_files(tmp_path):
    (tmp_path / "other.xlsx").write_text("x", encoding="utf-8")

    out = sl.load_all_plannings(tmp_path)

    assert out.empty


def test_load_all_plannings_skips_empty_and_parses_week_from_new_pattern(monkeypatch, tmp_path):
    f1 = tmp_path / "ASFmm - PLANNING SEMAINE 2026-05-03.xlsx"
    f2 = tmp_path / "ASFmm - PLANNING SEMAINE 2026-06-01.xlsx"
    f1.write_text("x", encoding="utf-8")
    f2.write_text("x", encoding="utf-8")
    monkeypatch.setattr(
        sl,
        "load_planning_xlsx",
        lambda path: pd.DataFrame() if Path(path).name.endswith("06-01.xlsx") else pd.DataFrame([{"x": 1}]),
    )

    out = sl.load_all_plannings(tmp_path)

    assert len(out) == 1
    assert int(out.iloc[0]["week"]) == 5
    assert out.iloc[0]["filename"] == f1.name


def test_load_all_plannings_parses_week_from_old_pattern(monkeypatch, tmp_path):
    f = tmp_path / "ASFmm - PLANNING SEMAINE N° 07 - 2026 v2.xlsx"
    f.write_text("x", encoding="utf-8")
    monkeypatch.setattr(sl, "load_planning_xlsx", lambda _path: pd.DataFrame([{"x": 1}]))

    out = sl.load_all_plannings(tmp_path)

    assert len(out) == 1
    assert int(out.iloc[0]["week"]) == 7
