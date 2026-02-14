# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import pandas as pd

import asf_app.services.planning_exports_service as pes


class _FakeMatch:
    def __init__(self, *groups: str):
        self._groups = groups

    def group(self, idx: int) -> str:
        return self._groups[idx - 1]


def test_available_weeks_local_skips_non_planning_directories(tmp_path, monkeypatch):
    root = tmp_path / "onedrive"
    base = root / "Planning MAB"
    (base / "RANDOM").mkdir(parents=True, exist_ok=True)
    good = base / "ASFmm PLANNING 2026"
    good.mkdir(parents=True, exist_ok=True)
    (good / "ASFmm - PLANNING SEMAINE 2026-05-01.xlsx").touch()

    monkeypatch.setattr(pes, "is_graph_onedrive", lambda: False)
    monkeypatch.setattr(pes, "get_onedrive_root", lambda: root)

    weeks = pes.available_weeks_from_exports()
    assert (5, 2026) in weeks


def test_load_planning_xlsx_returns_empty_when_read_excel_is_empty(monkeypatch, tmp_path):
    path = tmp_path / "planning.xlsx"
    path.touch()
    monkeypatch.setattr(pes.pd, "read_excel", lambda *_a, **_k: pd.DataFrame())

    out = pes.load_planning_xlsx(path, default_year=2026)
    assert out.empty


def test_load_planning_xlsx_returns_empty_when_no_numeric_be(tmp_path):
    from openpyxl import Workbook

    path = tmp_path / "planning.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Planning"
    ws.append(["", "", "Lundi 01/01", "Jean", "", "DOUALA", "DLA", "CDG-DLA", "AF822", "11:00", "ABC"])
    wb.save(path)

    out = pes.load_planning_xlsx(path, default_year=2026)
    assert out.empty


def test_available_weeks_graph_tolerates_invalid_old_format_groups(monkeypatch):
    real_search = pes.re.search

    def _fake_search(pattern: str, string: str, flags: int = 0):
        if pattern.startswith(r"SEMAINE"):
            return None
        if pattern.startswith(r"N°"):
            return _FakeMatch("oops")
        if pattern == r"(20\d{2})":
            return _FakeMatch("2026")
        return real_search(pattern, string, flags)

    monkeypatch.setattr(pes, "is_graph_onedrive", lambda: True)
    monkeypatch.setattr(
        pes.cp,
        "list_onedrive_files",
        lambda *_a, **_k: [{"name": "ASFmm - PLANNING SEMAINE N° XX - 2026 v1.xlsx"}],
    )
    monkeypatch.setattr(pes.re, "search", _fake_search)

    assert pes.available_weeks_from_exports() == set()


def test_available_weeks_local_tolerates_invalid_week_values(tmp_path, monkeypatch):
    root = tmp_path / "onedrive"
    base = root / "Planning MAB" / "ASFmm PLANNING 2026"
    base.mkdir(parents=True, exist_ok=True)
    (base / "ASFmm - PLANNING SEMAINE N° 05 - 2026 v1.xlsx").touch()

    real_search = pes.re.search

    def _fake_search(pattern: str, string: str, flags: int = 0):
        if pattern.startswith(r"SEMAINE"):
            return None
        if pattern.startswith(r"N°"):
            return _FakeMatch("oops")
        return real_search(pattern, string, flags)

    monkeypatch.setattr(pes, "is_graph_onedrive", lambda: False)
    monkeypatch.setattr(pes, "get_onedrive_root", lambda: root)
    monkeypatch.setattr(pes.re, "search", _fake_search)

    assert pes.available_weeks_from_exports() == set()


def test_parse_version_from_name_tolerates_non_numeric_groups(monkeypatch):
    real_search = pes.re.search

    def _fake_search(pattern: str, string: str, flags: int = 0):
        if pattern.startswith(r"SEMAINE"):
            return _FakeMatch("bad")
        if pattern.startswith(r"V("):
            return _FakeMatch("bad", "still_bad")
        return real_search(pattern, string, flags)

    monkeypatch.setattr(pes.re, "search", _fake_search)

    assert pes.parse_version_from_name(Path("planning.xlsx")) == (1, 0)
