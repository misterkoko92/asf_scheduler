# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime as _dt

import pandas as pd
import pytest

pytest.importorskip("reportlab")
import asf_app.ui.ui_stats.ui_stats as ui_stats  # noqa: E402


class _Ctx:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        _ = exc_type, exc, tb
        return False


class _StubSt:
    def __init__(self):
        self.session_state: dict[str, object] = {}
        self.infos: list[str] = []
        self.warnings: list[str] = []
        self.successes: list[str] = []
        self.dataframe_calls = 0
        self.plot_calls = 0
        self._radio_values: dict[str, object] = {}
        self._checkbox_values: dict[str, bool] = {}

    def header(self, *_args, **_kwargs):
        return None

    def subheader(self, *_args, **_kwargs):
        return None

    def markdown(self, *_args, **_kwargs):
        return None

    def caption(self, *_args, **_kwargs):
        return None

    def info(self, msg):
        self.infos.append(str(msg))

    def warning(self, msg):
        self.warnings.append(str(msg))

    def success(self, msg):
        self.successes.append(str(msg))

    def selectbox(self, _label, options, index=0, **_kwargs):
        return options[index]

    def radio(self, label, options, index=0, **_kwargs):
        return self._radio_values.get(str(label), options[index])

    def slider(self, _label, _min, _max, value, **_kwargs):
        return value

    def checkbox(self, label, value=False, **_kwargs):
        return self._checkbox_values.get(str(label), value)

    def plotly_chart(self, _fig, **_kwargs):
        self.plot_calls += 1

    def dataframe(self, _df, **_kwargs):
        self.dataframe_calls += 1

    def expander(self, *_args, **_kwargs):
        return _Ctx()

    def columns(self, n, **_kwargs):
        _ = _kwargs
        count = len(n) if isinstance(n, (list, tuple)) else int(n)
        return [_Ctx() for _ in range(count)]

    def button(self, *_args, **_kwargs):
        return False

    def text_input(self, _label, value="", **_kwargs):
        return value

    def rerun(self):
        return None

    def spinner(self, *_args, **_kwargs):
        return _Ctx()

    def download_button(self, *_args, **_kwargs):
        return None


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date_dt": pd.Timestamp("2026-01-19"),
                "week": 4,
                "year": 2026,
                "be": "260001",
                "nb_colis": 10,
                "destination_iata": "DLA",
                "destination_nom": "DOUALA",
                "vol_day": "AF822|2026-01-19",
                "expediteur": "ASF",
                "nom": "ALICE DUPONT",
                "heure": "11:00",
                "type": "MM",
                "vol_info": "AF822",
            },
            {
                "date_dt": pd.Timestamp("2026-01-20"),
                "week": 4,
                "year": 2026,
                "be": "260002",
                "nb_colis": 4,
                "destination_iata": "RUN",
                "destination_nom": "SAINT DENIS",
                "vol_day": "AF652|2026-01-20",
                "expediteur": "MEDILAB",
                "nom": "BOB MARTIN",
                "heure": "13:30",
                "type": "CN",
                "vol_info": "AF652",
            },
        ]
    )


def test_stats_helpers_cover_additional_fallback_paths():
    assert ui_stats.extract_week_version("planning 12") == (12, 0)
    assert ui_stats.extract_week_version("SEMAINE 2026-99-01.xlsx") == (20, 0)
    assert ui_stats._normalize_nom_last("....") == ""
    assert ui_stats._extract_year_from_name("x-no-year") is None


def test_filter_period_and_select_period_additional_paths(monkeypatch):
    df = _sample_df()
    assert ui_stats._filter_period(df, "Unknown", ref_date=pd.Timestamp("2026-01-20")).equals(df)
    assert ui_stats._filter_period(df, "Mensuel", ref_date="invalid").equals(df)
    assert ui_stats._filter_period(pd.DataFrame(), "Annuel").empty

    stub = _StubSt()
    monkeypatch.setattr(ui_stats, "st", stub)
    out = ui_stats._select_period(df, "Bloc X", "Annuel")
    assert len(out) == len(df)


def test_plot_functions_empty_inputs_emit_info(monkeypatch):
    stub = _StubSt()
    monkeypatch.setattr(ui_stats, "st", stub)
    empty = pd.DataFrame()
    ui_stats.plot_weekly_volume(empty, "Annuel")
    ui_stats.plot_top_destinations(empty, "Annuel")
    ui_stats.plot_heatmap_week_destination(empty, "Annuel")
    ui_stats.plot_hour_day_heatmap(empty, "Annuel")
    ui_stats.plot_benevole_load(empty, "Annuel")
    ui_stats.plot_expediteur_volume(empty, "Annuel")
    ui_stats.plot_type_colis(empty, "Annuel")
    ui_stats.plot_exp_dest_matrix(empty, "Annuel")
    ui_stats.plot_quality_report(empty, "Annuel")
    ui_stats.plot_comparison(empty, "Annuel")
    ui_stats.plot_top_alerts(empty, "Annuel")
    assert len(stub.infos) >= 10


def test_plot_specific_branches(monkeypatch):
    stub = _StubSt()
    monkeypatch.setattr(ui_stats, "st", stub)
    df = _sample_df()

    stub._checkbox_values["Hors ASF"] = True
    monkeypatch.setattr(ui_stats, "_select_period", lambda *_a, **_k: df[df["expediteur"] == "ASF"])
    ui_stats.plot_expediteur_volume(df, "Annuel")
    assert any("Aucun expéditeur après filtrage" in msg for msg in stub.infos)

    stub._radio_values["Afficher par :"] = "Répartition par destination"
    monkeypatch.setattr(ui_stats, "_select_period", lambda *_a, **_k: pd.DataFrame(columns=df.columns))
    ui_stats.plot_type_colis(df, "Annuel")
    assert any("Aucune donnée de répartition" in msg for msg in stub.infos)

    monkeypatch.setattr(ui_stats, "_select_period", lambda *_a, **_k: pd.DataFrame(columns=df.columns))
    ui_stats.plot_exp_dest_matrix(df, "Annuel")
    assert any("Aucune donnée sur la période." in msg for msg in stub.infos)

    # Sans anomalies
    clean = _sample_df().copy()
    clean["destination_iata"] = "DLA"
    clean["vol_info"] = "AF822"
    clean["heure"] = "11:00"
    clean["be"] = ["260001", "260002"]
    clean["nom"] = ["ALICE", "BOB"]
    clean["expediteur"] = ["ASF", "MEDILAB"]
    monkeypatch.setattr(ui_stats, "_select_period", lambda *_a, **_k: clean)
    ui_stats.plot_quality_report(clean, "Annuel")
    assert any("Pas d'anomalies détectées" in msg for msg in stub.successes)

    single_day = clean.copy()
    single_day["date_dt"] = pd.Timestamp("2026-01-19")
    ui_stats.plot_comparison(single_day, "Annuel")
    assert any("Période insuffisante" in msg for msg in stub.infos)

    alerts = clean.copy()
    alerts["nom"] = pd.NA
    monkeypatch.setattr(ui_stats, "_select_period", lambda *_a, **_k: alerts)
    ui_stats.plot_top_alerts(alerts, "Annuel")
    assert stub.dataframe_calls >= 2


def test_stats_orchestration_helpers_additional_paths(monkeypatch, tmp_path):
    class _FakeDatetime:
        @classmethod
        def now(cls):
            return _dt(2026, 2, 13)

    monkeypatch.setattr(ui_stats, "datetime", _FakeDatetime)
    assert ui_stats._resolve_stats_year_default([2025, 2026]) == 2026
    assert ui_stats._resolve_stats_year_default([2024, 2025]) == 2025
    assert ui_stats._resolve_stats_year_default([]) == 2026

    stub = _StubSt()
    monkeypatch.setattr(ui_stats, "st", stub)
    monkeypatch.setattr(ui_stats, "_load_all_plannings", lambda **_k: pd.DataFrame([{"x": 1}]))
    assert not ui_stats._load_stats_dataframe(tmp_path).empty

    df_no_weeks = pd.DataFrame([{"year": 2026, "week": pd.NA, "date_dt": pd.Timestamp("2026-01-19")}])
    assert ui_stats._render_stats_filters(df_no_weeks) is None


def test_load_all_plannings_returns_empty_when_no_files(monkeypatch, tmp_path):
    monkeypatch.setattr("scheduler.config_paths.detect_onedrive_asf", lambda: tmp_path / "no-root")
    monkeypatch.setattr("scheduler.config_paths.get_planning_dirs", lambda: [])
    monkeypatch.setattr(ui_stats, "get_onedrive_root", lambda: tmp_path / "no-root")
    monkeypatch.setattr(ui_stats, "get_output_planning_dir", lambda: tmp_path / "no-out")
    out = ui_stats._load_all_plannings(base_override=tmp_path / "empty-dir")
    assert out.empty


def test_load_all_plannings_handles_glob_oserror(monkeypatch, tmp_path):
    root = tmp_path / "root"
    root.mkdir(parents=True, exist_ok=True)

    class _BadRoot:
        def exists(self):
            return True

        def glob(self, _pattern):
            raise OSError("glob-error")

    monkeypatch.setattr("scheduler.config_paths.detect_onedrive_asf", lambda: tmp_path)
    monkeypatch.setattr("scheduler.config_paths.get_planning_dirs", lambda: [])
    monkeypatch.setattr(ui_stats, "get_onedrive_root", lambda: tmp_path)
    monkeypatch.setattr(ui_stats, "get_output_planning_dir", lambda: tmp_path / "out")
    monkeypatch.setattr(ui_stats, "_resolve_stats_default_planning_dir", lambda: root)
    out = ui_stats._load_all_plannings(base_override=_BadRoot())
    assert out.empty
