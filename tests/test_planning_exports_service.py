# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import pandas as pd

import scheduler.config_paths as cp
from asf_app.services.planning_exports_service import (
    available_weeks_from_exports,
    find_planning_files_for_week,
    load_planning_preview_with_path,
    load_planning_xlsx,
    parse_version_from_name,
)


def test_parse_version_from_name():
    assert parse_version_from_name(Path("ASFmm - PLANNING SEMAINE 2026-05-03.xlsx")) == (3, 0)
    assert parse_version_from_name(Path("ASFmm - PLANNING SEMAINE N° 05 - 2026 v12-2.xlsx")) == (12, 2)
    assert parse_version_from_name(Path("planning_sans_version.xlsx")) == (1, 0)


def test_available_weeks_from_exports_local(tmp_path, monkeypatch):
    root = tmp_path / "onedrive"
    base_dir = root / "Planning MAB" / "ASFmm PLANNING 2026"
    base_dir.mkdir(parents=True, exist_ok=True)
    (base_dir / "ASFmm - PLANNING SEMAINE 2026-02-01.xlsx").touch()

    monkeypatch.setattr(cp, "ASF_ONEDRIVE", root)
    monkeypatch.setattr(cp, "is_graph_onedrive", lambda: False)

    weeks = available_weeks_from_exports()
    assert (2, 2026) in weeks


def test_find_planning_files_for_week_sorted(tmp_path, monkeypatch):
    root = tmp_path / "onedrive"
    base_dir = root / "Planning MAB" / "ASFmm PLANNING 2026"
    base_dir.mkdir(parents=True, exist_ok=True)
    files = [
        base_dir / "ASFmm - PLANNING SEMAINE 2026-05-01.xlsx",
        base_dir / "ASFmm - PLANNING SEMAINE 2026-05-03.xlsx",
        base_dir / "ASFmm - PLANNING SEMAINE 2026-05-02.xlsx",
    ]
    for f in files:
        f.touch()

    monkeypatch.setattr(cp, "ASF_ONEDRIVE", root)
    monkeypatch.setattr(cp, "is_graph_onedrive", lambda: False)

    results = find_planning_files_for_week(5, 2026)
    assert [Path(p).name for p in results[:3]] == [
        "ASFmm - PLANNING SEMAINE 2026-05-03.xlsx",
        "ASFmm - PLANNING SEMAINE 2026-05-02.xlsx",
        "ASFmm - PLANNING SEMAINE 2026-05-01.xlsx",
    ]


def test_load_planning_preview_with_path(tmp_path, monkeypatch):
    path = tmp_path / "planning.xlsx"
    df = pd.DataFrame({"A": [1], "B": [2]})
    with pd.ExcelWriter(path) as writer:
        df.to_excel(writer, sheet_name="Export planning", index=False)

    monkeypatch.setattr(cp, "is_graph_onedrive", lambda: False)

    df_out, msg, used_path = load_planning_preview_with_path(2, 2026, path)
    assert used_path == path
    assert df_out is not None and not df_out.empty
    assert "Export planning" in msg


def test_load_planning_xlsx_parses(tmp_path):
    from openpyxl import Workbook

    path = tmp_path / "planning.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Planning"
    row = [
        "",
        "",
        "Lundi 01/01",
        "Jean Dupont",
        "",
        "BRAZZAVILLE",
        "BZV",
        "CDG-BZV",
        "AF123",
        "10:00",
        "250001",
        2,
        "MM",
        "",
        "",
        "ASF",
        "Hopital",
    ]
    ws.append(row)
    wb.save(path)

    df = load_planning_xlsx(path, default_year=2025)
    assert not df.empty
    assert df.iloc[0]["be"] == "250001"
