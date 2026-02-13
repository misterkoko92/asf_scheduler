# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

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

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        _ = exc_type, exc, tb
        return False

    def metric(self, label, value, delta=None):
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
        count = len(n) if isinstance(n, (list, tuple)) else int(n)
        return [_StubCol(self.metric_calls) for _ in range(count)]

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


def test_ui_stats_default_planning_dir_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "scheduler.config_paths.detect_onedrive_asf",
        lambda: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setattr(ui_stats, "get_onedrive_root", lambda: tmp_path)

    out = ui_stats._resolve_stats_default_planning_dir()

    assert out == tmp_path / "Planning MAB" / "ASFmm PLANNING 2025"


def test_ui_stats_render_filters_returns_expected_tuple(monkeypatch):
    df = _sample_stats_df()
    stub = _StubSt()
    monkeypatch.setattr(ui_stats, "st", stub)

    out = ui_stats._render_stats_filters(df)

    assert out is not None
    df_year, df_filtered, general_period = out
    assert not df_year.empty
    assert not df_filtered.empty
    assert general_period == "Annuel"


def test_render_tab_stats_smoke_orchestrated(monkeypatch, tmp_path):
    df = _sample_stats_df()
    stub = _StubSt()
    stub.session_state["stats_should_load"] = True
    stub.subheader = lambda *_args, **_kwargs: None  # type: ignore[attr-defined]
    monkeypatch.setattr(ui_stats, "st", stub)
    monkeypatch.setattr(
        ui_stats,
        "_resolve_stats_default_planning_dir",
        lambda: tmp_path / "Planning MAB" / "ASFmm PLANNING 2025",
    )
    monkeypatch.setattr(
        ui_stats,
        "_render_stats_planning_dir_selector",
        lambda default_dir: default_dir,
    )
    monkeypatch.setattr(ui_stats, "_trigger_stats_loading", lambda: True)
    monkeypatch.setattr(ui_stats, "_load_stats_dataframe", lambda _planning_dir: df)
    monkeypatch.setattr(
        ui_stats,
        "_render_stats_filters",
        lambda _df_all: (df.copy(), df.copy(), "Annuel"),
    )

    calls: list[str] = []
    monkeypatch.setattr(
        ui_stats,
        "_render_stats_kpi_block",
        lambda _df: calls.append("kpi"),
    )
    monkeypatch.setattr(
        ui_stats,
        "_render_stats_visual_sections",
        lambda _df, _period: calls.append("visuals"),
    )
    monkeypatch.setattr(
        ui_stats,
        "_render_stats_pdf_export",
        lambda _df_year: calls.append("pdf"),
    )

    ui_stats.render_tab_stats()

    assert calls == ["kpi", "visuals", "pdf"]


class _StubStActions(_StubSt):
    def __init__(self):
        super().__init__()
        self.rerun_called = False
        self.download_calls = 0
        self._button_sequences: dict[str, list[bool]] = {}
        self._text_input_value = ""

    def set_button_sequence(self, label: str, values: list[bool]):
        self._button_sequences[label] = list(values)

    def button(self, label, *_args, **_kwargs):
        seq = self._button_sequences.get(label)
        if seq:
            return seq.pop(0)
        return False

    def subheader(self, *_args, **_kwargs):
        return None

    def text_input(self, _label, value="", **_kwargs):
        return self._text_input_value or value

    def rerun(self):
        self.rerun_called = True

    def download_button(self, *_args, **_kwargs):
        self.download_calls += 1


def test_stats_selector_loading_and_filters_branches(monkeypatch, tmp_path):
    stub = _StubStActions()
    stub._text_input_value = str(tmp_path / "stats")
    stub.set_button_sequence("✅ Utiliser ce dossier", [True])
    stub.set_button_sequence("📥 Charger / actualiser les données", [True])
    monkeypatch.setattr(ui_stats, "st", stub)

    out_dir = ui_stats._render_stats_planning_dir_selector(tmp_path)
    assert out_dir == Path(stub.session_state["stats_planning_dir"])
    assert stub.rerun_called is True

    should_load = ui_stats._trigger_stats_loading()
    assert should_load is True

    # Branche sans année exploitable
    assert ui_stats._render_stats_filters(pd.DataFrame({"year": [pd.NA]})) is None

    # Branche une seule semaine (week_min == week_max)
    df = pd.DataFrame(
        [
            {"year": 2026, "week": 4, "date_dt": pd.Timestamp("2026-01-20")},
            {"year": 2026, "week": 4, "date_dt": pd.Timestamp("2026-01-21")},
        ]
    )
    out = ui_stats._render_stats_filters(df)
    assert out is not None
    _, filtered, period = out
    assert not filtered.empty
    assert period in {"Annuel", "Hebdomadaire"}


def test_stats_kpi_visual_sections_and_pdf(monkeypatch, tmp_path):
    stub = _StubStActions()
    stub.set_button_sequence("📑 Analyser toute l'année et générer un rapport PDF", [True])
    monkeypatch.setattr(ui_stats, "st", stub)

    df = _sample_stats_df()
    ui_stats._render_stats_kpi_block(df)
    assert any(m[0] == "BE distincts" for m in stub.metric_calls)

    called: list[str] = []
    monkeypatch.setattr(ui_stats, "plot_weekly_volume", lambda *_args, **_kwargs: called.append("weekly"))
    monkeypatch.setattr(ui_stats, "plot_top_destinations", lambda *_args, **_kwargs: called.append("dest"))
    monkeypatch.setattr(ui_stats, "plot_type_colis", lambda *_args, **_kwargs: called.append("type"))
    monkeypatch.setattr(ui_stats, "plot_hour_day_heatmap", lambda *_args, **_kwargs: called.append("hour"))
    monkeypatch.setattr(ui_stats, "plot_heatmap_week_destination", lambda *_args, **_kwargs: called.append("heat"))
    monkeypatch.setattr(ui_stats, "plot_benevole_load", lambda *_args, **_kwargs: called.append("benev"))
    monkeypatch.setattr(ui_stats, "plot_exp_dest_matrix", lambda *_args, **_kwargs: called.append("matrix"))
    monkeypatch.setattr(ui_stats, "plot_expediteur_volume", lambda *_args, **_kwargs: called.append("exp"))
    monkeypatch.setattr(ui_stats, "plot_top_alerts", lambda *_args, **_kwargs: called.append("alerts"))
    monkeypatch.setattr(ui_stats, "plot_quality_report", lambda *_args, **_kwargs: called.append("quality"))
    monkeypatch.setattr(ui_stats, "plot_comparison", lambda *_args, **_kwargs: called.append("comparison"))

    ui_stats._render_stats_visual_sections(df, "Annuel")
    assert called == [
        "weekly",
        "dest",
        "type",
        "hour",
        "heat",
        "benev",
        "matrix",
        "exp",
        "alerts",
        "quality",
        "comparison",
    ]

    pdf_path = tmp_path / "report.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")
    monkeypatch.setattr(ui_stats, "generate_year_pdf_report", lambda *_args, **_kwargs: pdf_path)
    monkeypatch.setattr(ui_stats, "get_output_planning_dir", lambda: tmp_path)

    ui_stats._render_stats_pdf_export(df)
    assert any("Rapport généré" in msg for msg in stub.successes)
    assert stub.download_calls == 1


def test_render_tab_stats_main_branches(monkeypatch, tmp_path):
    stub = _StubStActions()
    monkeypatch.setattr(ui_stats, "st", stub)
    monkeypatch.setattr(ui_stats, "_resolve_stats_default_planning_dir", lambda: tmp_path)
    monkeypatch.setattr(ui_stats, "_render_stats_planning_dir_selector", lambda _default: tmp_path)

    # Pas de trigger
    monkeypatch.setattr(ui_stats, "_trigger_stats_loading", lambda: False)
    ui_stats.render_tab_stats()
    assert any("Charger / actualiser" in msg for msg in stub.infos)

    # DataFrame vide après chargement
    monkeypatch.setattr(ui_stats, "_trigger_stats_loading", lambda: True)
    monkeypatch.setattr(ui_stats, "_load_stats_dataframe", lambda _p: pd.DataFrame())
    ui_stats.render_tab_stats()
    assert any("Aucun planning ASFmm détecté" in msg for msg in stub.infos)

    # Filtres non exploitables puis intervalle vide
    df = _sample_stats_df()
    monkeypatch.setattr(ui_stats, "_load_stats_dataframe", lambda _p: df)
    monkeypatch.setattr(ui_stats, "_render_stats_filters", lambda _df: None)
    ui_stats.render_tab_stats()
    assert any("Aucune donnée annuelle exploitable" in msg for msg in stub.warnings)

    monkeypatch.setattr(ui_stats, "_render_stats_filters", lambda _df: (df, pd.DataFrame(), "Annuel"))
    ui_stats.render_tab_stats()
    assert any("Aucune donnée dans l'intervalle choisi." in msg for msg in stub.warnings)
