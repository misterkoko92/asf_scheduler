# -*- coding: utf-8 -*-
from __future__ import annotations

import pandas as pd
import pytest

pytest.importorskip("reportlab")
import asf_app.ui.ui_stats.ui_stats as ui_stats  # noqa: E402


def _sample_stats_df() -> pd.DataFrame:
    rows = [
        {
            "date": "2026-01-19",
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
            "date": "2026-01-20",
            "date_dt": pd.Timestamp("2026-01-20"),
            "week": 4,
            "year": 2026,
            "be": "260002",
            "nb_colis": 5,
            "destination_iata": "RUN",
            "destination_nom": "SAINT DENIS",
            "vol_day": "AF652|2026-01-20",
            "expediteur": "MEDILAB",
            "nom": "BOB MARTIN",
            "heure": "13:35",
            "type": "CN",
            "vol_info": "AF652",
        },
        {
            "date": "2026-01-27",
            "date_dt": pd.Timestamp("2026-01-27"),
            "week": 5,
            "year": 2026,
            "be": "260003",
            "nb_colis": 8,
            "destination_iata": "DLA",
            "destination_nom": "DOUALA",
            "vol_day": "AF948|2026-01-27",
            "expediteur": "MEDILAB",
            "nom": "ALICE DUPONT",
            "heure": "14:05",
            "type": "MM",
            "vol_info": "AF948",
        },
    ]
    return pd.DataFrame(rows)


class _StubCol:
    def __init__(self, metrics: list[tuple[str, object, object]]):
        self._metrics = metrics

    def metric(self, label, value, delta):
        self._metrics.append((str(label), value, delta))


class _StubExpander:
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
        self.plot_calls = 0
        self.dataframe_calls = 0
        self.metric_calls: list[tuple[str, object, object]] = []

    def info(self, msg):
        self.infos.append(str(msg))

    def warning(self, msg):
        self.warnings.append(str(msg))

    def success(self, msg):
        self.successes.append(str(msg))

    def selectbox(self, _label, options, index=0, **_kwargs):
        return options[index]

    def radio(self, _label, options, index=0, **_kwargs):
        return options[index]

    def slider(self, _label, _min, _max, value, **_kwargs):
        return value

    def checkbox(self, _label, value=False, **_kwargs):
        return value

    def plotly_chart(self, _fig, **_kwargs):
        self.plot_calls += 1

    def dataframe(self, _df, **_kwargs):
        self.dataframe_calls += 1

    def expander(self, *_args, **_kwargs):
        return _StubExpander()

    def columns(self, n, **_kwargs):
        return [_StubCol(self.metric_calls) for _ in range(int(n))]

    def markdown(self, *_args, **_kwargs):
        return None

    def header(self, *_args, **_kwargs):
        return None

    def caption(self, *_args, **_kwargs):
        return None

    def button(self, *_args, **_kwargs):
        return False

    def text_input(self, _label, value="", **_kwargs):
        return value

    def rerun(self):
        return None

    def spinner(self, *_args, **_kwargs):
        return _StubExpander()

    def download_button(self, *_args, **_kwargs):
        return None


def test_ui_stats_helpers_filter_select_and_kpis(monkeypatch):
    df = _sample_stats_df()
    assert ui_stats._normalize_nom_last("Claude. Dupont") == "DUPONT"
    assert ui_stats._normalize_nom_last("") == ""

    weekly = ui_stats._filter_period(df, "Hebdomadaire", ref_date=pd.Timestamp("2026-01-20"))
    assert set(weekly["week"].tolist()) == {4}

    annual = ui_stats._filter_period(df, "Annuel", ref_date=pd.Timestamp("2026-02-01"))
    assert len(annual) == len(df)

    stub = _StubSt()
    monkeypatch.setattr(ui_stats, "st", stub)
    selected = ui_stats._select_period(df, "Volume hebdomadaire", "Annuel")
    assert len(selected) == len(df)

    kpi = ui_stats._kpi_global(df)
    assert kpi["nb_be"] == 3
    assert kpi["nb_colis"] == 23
    assert kpi["nb_dest"] == 2
    assert ui_stats._kpi_global(pd.DataFrame())["nb_colis"] == 0


def test_ui_stats_plot_functions_smoke(monkeypatch):
    df = _sample_stats_df()
    stub = _StubSt()
    monkeypatch.setattr(ui_stats, "st", stub)

    ui_stats.plot_weekly_volume(df, "Annuel")
    ui_stats.plot_top_destinations(df, "Annuel")
    ui_stats.plot_heatmap_week_destination(df, "Annuel")
    ui_stats.plot_hour_day_heatmap(df, "Annuel")
    ui_stats.plot_benevole_load(df, "Annuel")
    ui_stats.plot_expediteur_volume(df, "Annuel")
    ui_stats.plot_type_colis(df, "Annuel")
    ui_stats.plot_exp_dest_matrix(df, "Annuel")
    ui_stats.plot_quality_report(df, "Annuel")
    ui_stats.plot_comparison(df, "Annuel")
    ui_stats.plot_top_alerts(df, "Annuel")

    assert stub.plot_calls >= 8
    assert stub.dataframe_calls >= 2
    assert any(m[0] == "Colis" for m in stub.metric_calls)


def test_ui_stats_table_and_pdf_generation(tmp_path):
    df = _sample_stats_df()
    table = ui_stats._df_to_rl_table(df[["week", "nb_colis"]], max_rows=2)
    assert table is not None
    assert ui_stats._df_to_rl_table(pd.DataFrame()) is None

    pdf_path = ui_stats.generate_year_pdf_report(df, tmp_path)
    assert pdf_path.exists()
    assert pdf_path.suffix.lower() == ".pdf"
    assert "Statistiques" in str(pdf_path.parent)
