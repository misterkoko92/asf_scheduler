# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("reportlab")
import asf_app.ui.ui_stats.ui_stats as ui_stats  # noqa: E402


def test_extract_week_version_variants():
    assert ui_stats.extract_week_version("ASFmm - PLANNING SEMAINE 2026-47-02.xlsx") == (47, 2)
    assert ui_stats.extract_week_version("ASFmm - PLANNING SEMAINE N° 03 - 2025 v12.xlsx") == (3, 12)
    assert ui_stats.extract_week_version("ASFmm - PLANNING SEMAINE N° 03 - 2025.xlsx") == (3, 1)
    assert ui_stats.extract_week_version("no-week-here.txt") == (None, None)


def test_filter_latest_keeps_highest_version_per_week(tmp_path):
    files = [
        tmp_path / "ASFmm - PLANNING SEMAINE 2026-05-01.xlsx",
        tmp_path / "ASFmm - PLANNING SEMAINE 2026-05-03.xlsx",
        tmp_path / "ASFmm - PLANNING SEMAINE 2026-06-01.xlsx",
    ]
    for f in files:
        f.touch()

    out = ui_stats.filter_latest(files)
    names = sorted([p.name for p in out])
    assert names == [
        "ASFmm - PLANNING SEMAINE 2026-05-03.xlsx",
        "ASFmm - PLANNING SEMAINE 2026-06-01.xlsx",
    ]


def test_load_all_plannings_fallbacks_when_config_detection_fails(monkeypatch, tmp_path):
    base_root = tmp_path / "onedrive"
    planning_dir = base_root / "Planning MAB" / "ASFmm PLANNING 2025"
    planning_dir.mkdir(parents=True, exist_ok=True)
    planning_file = planning_dir / "ASFmm - PLANNING SEMAINE 2025-04-01.xlsx"
    planning_file.touch()

    monkeypatch.setattr("scheduler.config_paths.detect_onedrive_asf", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(ui_stats, "get_onedrive_root", lambda: base_root)
    monkeypatch.setattr(ui_stats, "get_output_planning_dir", lambda: tmp_path / "output")

    def _fake_loader(path: Path, default_year: int | None = None):
        return pd.DataFrame(
            [
                {
                    "date": "2025-01-23",
                    "nom": "ALICE DUPONT",
                    "vol_info": "AF652",
                    "nb_colis": 2,
                    "be": "250001",
                    "destination_iata": "RUN",
                    "destination_nom": "SAINT DENIS",
                    "expediteur": "ASF",
                }
            ]
        )

    monkeypatch.setattr(ui_stats, "load_planning_xlsx", _fake_loader)

    out = ui_stats._load_all_plannings()
    assert not out.empty
    assert set(["week", "year", "date_dt", "vol_day"]).issubset(out.columns)
    assert int(out.iloc[0]["week"]) == 4
    assert int(out.iloc[0]["year"]) == 2025
