# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("reportlab")
import asf_app.ui.ui_stats.ui_stats as ui_stats  # noqa: E402


class _FakeMatch:
    def __init__(self, *groups: str):
        self._groups = groups

    def group(self, idx: int) -> str:
        return self._groups[idx - 1]


class _StubStatsSt:
    def __init__(self):
        self.infos: list[str] = []

    def info(self, msg):
        self.infos.append(str(msg))

    def plotly_chart(self, *_args, **_kwargs):
        return None

    def columns(self, n, **_kwargs):
        count = int(n)

        class _Col:
            def metric(self, *_a, **_k):
                return None

        return [_Col() for _ in range(count)]


def test_extract_week_version_tolerates_value_errors_for_all_patterns(monkeypatch):
    real_search = ui_stats.re.search

    def _first_invalid(pattern: str, string: str, flags: int = 0):
        if pattern.startswith(r"SEMAINE"):
            return _FakeMatch("2026", "oops", "2")
        if pattern.startswith(r"N") or pattern.startswith(r"N[°o]?"):
            return None
        return real_search(pattern, string, flags)

    monkeypatch.setattr(ui_stats.re, "search", _first_invalid)
    assert ui_stats.extract_week_version("planning-no-digits") == (None, None)

    def _second_invalid(pattern: str, string: str, flags: int = 0):
        if pattern.startswith(r"SEMAINE"):
            return None
        if "v(" in pattern:
            return _FakeMatch("oops", "2")
        return None

    monkeypatch.setattr(ui_stats.re, "search", _second_invalid)
    assert ui_stats.extract_week_version("planning-no-digits") == (None, None)

    def _third_invalid(pattern: str, string: str, flags: int = 0):
        if pattern.startswith(r"SEMAINE"):
            return None
        if "v(" in pattern:
            return None
        if pattern.startswith(r"N"):
            return _FakeMatch("oops")
        return None

    monkeypatch.setattr(ui_stats.re, "search", _third_invalid)
    assert ui_stats.extract_week_version("planning-no-digits") == (None, None)


def test_filter_latest_skips_files_without_week(tmp_path):
    valid = tmp_path / "ASFmm - PLANNING SEMAINE 2026-05-01.xlsx"
    valid.touch()
    invalid = tmp_path / "no_week_here.txt"
    invalid.touch()

    out = ui_stats.filter_latest([invalid, valid])
    assert out == [valid]


def test_load_planning_xlsx_wrapper_delegates(monkeypatch):
    sentinel = pd.DataFrame([{"x": 1}])
    monkeypatch.setattr(ui_stats, "_load_planning_xlsx", lambda *_a, **_k: sentinel)

    out = ui_stats.load_planning_xlsx(Path("dummy.xlsx"), default_year=2026)
    assert out is sentinel


def test_load_all_plannings_handles_get_planning_dirs_failure(monkeypatch, tmp_path):
    monkeypatch.setattr("scheduler.config_paths.detect_onedrive_asf", lambda: tmp_path)
    monkeypatch.setattr("scheduler.config_paths.get_planning_dirs", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(ui_stats, "get_onedrive_root", lambda: tmp_path)
    monkeypatch.setattr(ui_stats, "get_output_planning_dir", lambda: tmp_path / "out")

    out = ui_stats._load_all_plannings(base_override=tmp_path / "missing")
    assert out.empty


def test_load_all_plannings_handles_non_files_and_empty_loaded_frames(monkeypatch, tmp_path):
    root = tmp_path / "root"
    root.mkdir(parents=True, exist_ok=True)
    sub = root / "subdir"
    sub.mkdir(parents=True, exist_ok=True)
    planning = root / "ASFmm - PLANNING SEMAINE 2026-05-01.xlsx"
    planning.touch()

    class _RootProxy:
        def exists(self):
            return True

        def glob(self, _pattern):
            return [sub, planning]

    class _FakeDatetime:
        @staticmethod
        def fromtimestamp(_value):
            raise OverflowError("boom")

    monkeypatch.setattr("scheduler.config_paths.detect_onedrive_asf", lambda: tmp_path)
    monkeypatch.setattr("scheduler.config_paths.get_planning_dirs", lambda: [])
    monkeypatch.setattr(ui_stats, "datetime", _FakeDatetime)
    monkeypatch.setattr(ui_stats, "load_planning_xlsx", lambda *_a, **_k: pd.DataFrame())
    monkeypatch.setattr(ui_stats, "filter_latest", lambda files: files)
    monkeypatch.setattr(ui_stats, "_extract_year_from_name", lambda _name: None)

    out = ui_stats._load_all_plannings(base_override=_RootProxy())
    assert out.empty


def test_plot_heatmap_and_matrix_handle_empty_pivots(monkeypatch):
    stub = _StubStatsSt()
    monkeypatch.setattr(ui_stats, "st", stub)

    empty_heatmap_df = pd.DataFrame(
        [
            {"week": 4, "destination_iata": pd.NA, "nb_colis": 10},
        ]
    )
    monkeypatch.setattr(ui_stats, "_select_period", lambda *_a, **_k: empty_heatmap_df)
    ui_stats.plot_heatmap_week_destination(pd.DataFrame([{"x": 1}]), "Annuel")

    empty_matrix_df = pd.DataFrame(
        [
            {"expediteur": pd.NA, "destination_iata": pd.NA, "nb_colis": 10},
        ]
    )
    monkeypatch.setattr(ui_stats, "_select_period", lambda *_a, **_k: empty_matrix_df)
    ui_stats.plot_exp_dest_matrix(pd.DataFrame([{"x": 1}]), "Annuel")

    assert any("heatmap" in msg.lower() for msg in stub.infos)
    assert any("matrice vide" in msg.lower() for msg in stub.infos)


def test_plot_comparison_rejects_zero_day_span(monkeypatch):
    stub = _StubStatsSt()
    monkeypatch.setattr(ui_stats, "st", stub)

    df = pd.DataFrame(
        [
            {
                "date_dt": pd.Timestamp("2026-01-20 08:00:00"),
                "nb_colis": 5,
                "be": "260001",
                "vol_day": "AF001|2026-01-20",
            },
            {
                "date_dt": pd.Timestamp("2026-01-20 14:00:00"),
                "nb_colis": 6,
                "be": "260002",
                "vol_day": "AF002|2026-01-20",
            },
        ]
    )

    ui_stats.plot_comparison(df, "Annuel")
    assert any("trop courte" in msg.lower() for msg in stub.infos)
