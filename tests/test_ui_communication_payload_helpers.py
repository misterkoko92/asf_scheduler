# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd

import asf_app.ui.ui_communication.ui_communication as comm


class _StubSt:
    def __init__(self):
        self.errors: list[str] = []
        self.infos: list[str] = []
        self.warnings: list[str] = []
        self._expander_calls = 0
        self._dataframe_calls = 0

    def error(self, msg):
        self.errors.append(str(msg))

    def info(self, msg):
        self.infos.append(str(msg))

    def warning(self, msg):
        self.warnings.append(str(msg))

    def expander(self, *_args, **_kwargs):
        self._expander_calls += 1
        return self

    def dataframe(self, *_args, **_kwargs):
        self._dataframe_calls += 1

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        _ = exc_type, exc, tb
        return False


def test_build_communication_payload_returns_none_when_source_empty(monkeypatch):
    stub = _StubSt()
    monkeypatch.setattr(comm, "st", stub)
    monkeypatch.setattr(comm, "_select_communication_planning_source", lambda: pd.DataFrame())

    payload = comm._build_communication_payload(SimpleNamespace(tableau_de_bord=Path("x.xlsx")))

    assert payload is None
    assert stub.errors == []


def test_build_communication_payload_returns_none_when_df_comm_empty(monkeypatch):
    stub = _StubSt()
    monkeypatch.setattr(comm, "st", stub)
    monkeypatch.setattr(
        comm,
        "_select_communication_planning_source",
        lambda: pd.DataFrame([{"Date_Vol": "2026-01-20"}]),
    )
    monkeypatch.setattr(
        comm,
        "_load_communication_parameters",
        lambda _paths: (pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()),
    )
    monkeypatch.setattr(comm, "_build_enriched_comm_dataframe", lambda **_kwargs: pd.DataFrame())

    payload = comm._build_communication_payload(SimpleNamespace(tableau_de_bord=Path("x.xlsx")))

    assert payload is None
    assert any("Impossible de générer df_comm" in msg for msg in stub.errors)


def test_build_communication_payload_returns_none_when_week_not_detected(monkeypatch):
    stub = _StubSt()
    monkeypatch.setattr(comm, "st", stub)
    monkeypatch.setattr(
        comm,
        "_select_communication_planning_source",
        lambda: pd.DataFrame([{"Date_Vol": "2026-01-20"}]),
    )
    monkeypatch.setattr(
        comm,
        "_load_communication_parameters",
        lambda _paths: (pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()),
    )
    monkeypatch.setattr(comm, "_build_enriched_comm_dataframe", lambda **_kwargs: pd.DataFrame([{"DATE": None}]))
    monkeypatch.setattr(comm, "_detect_week_year", lambda _df: (None, None))

    payload = comm._build_communication_payload(SimpleNamespace(tableau_de_bord=Path("x.xlsx")))

    assert payload is None
    assert any("Impossible de détecter la semaine" in msg for msg in stub.errors)


def test_build_communication_payload_success(monkeypatch):
    stub = _StubSt()
    monkeypatch.setattr(comm, "st", stub)
    monkeypatch.setattr(
        comm,
        "_select_communication_planning_source",
        lambda: pd.DataFrame([{"Date_Vol": "2026-01-20"}]),
    )
    monkeypatch.setattr(
        comm,
        "_load_communication_parameters",
        lambda _paths: (
            pd.DataFrame([{"Dest_IATA": "RUN"}]),
            pd.DataFrame([{"Expediteur": "ASF"}]),
            pd.DataFrame([{"Benevole": "Alice"}]),
            pd.DataFrame(),
        ),
    )
    monkeypatch.setattr(
        comm,
        "_build_enriched_comm_dataframe",
        lambda **_kwargs: pd.DataFrame([{"DATE": "2026-01-20", "Destination": "RUN"}]),
    )
    monkeypatch.setattr(comm, "_detect_week_year", lambda _df: (4, 2026))

    payload = comm._build_communication_payload(SimpleNamespace(tableau_de_bord=Path("x.xlsx")))

    assert payload is not None
    assert payload["week"] == 4
    assert payload["year"] == 2026
    assert not payload["df_comm"].empty


def test_render_pdf_attachment_status(monkeypatch, tmp_path):
    stub = _StubSt()
    monkeypatch.setattr(comm, "st", stub)

    comm._render_pdf_attachment_status(tmp_path / "plan.pdf")
    comm._render_pdf_attachment_status(None)

    assert any("PDF joint détecté" in msg for msg in stub.infos)
    assert any("Pas de planning PDF trouvé" in msg for msg in stub.warnings)


def test_render_communication_preview(monkeypatch):
    stub = _StubSt()
    monkeypatch.setattr(comm, "st", stub)
    monkeypatch.setattr(comm, "build_communication_display_dataframe", lambda df: df.assign(_ok=1))

    comm._render_communication_preview(pd.DataFrame([{"A": 1}]))

    assert stub._expander_calls == 1
    assert stub._dataframe_calls == 1


def test_load_onedrive_planning_ui_graph_invalid_remote_path(monkeypatch):
    class _GraphStub(_StubSt):
        def __init__(self):
            super().__init__()
            self.session_state: dict[str, object] = {}

        def number_input(self, *_args, **_kwargs):
            return 2026

        def radio(self, _label, options, index=0, **_kwargs):
            return options[index]

        def button(self, _label, **_kwargs):
            return True

    stub = _GraphStub()
    monkeypatch.setattr(comm, "st", stub)
    monkeypatch.setattr(comm, "is_graph_onedrive", lambda: True)
    monkeypatch.setattr(
        comm,
        "_list_onedrive_planning_files",
        lambda _year: [{"name": "planning.xlsx", "path": ""}],
    )

    out = comm._load_onedrive_planning_ui()

    assert out is None
    assert any("Chemin OneDrive invalide." in msg for msg in stub.errors)


def test_load_onedrive_planning_ui_graph_safe_cache_error(monkeypatch, tmp_path):
    class _GraphStub(_StubSt):
        def __init__(self):
            super().__init__()
            self.session_state: dict[str, object] = {}

        def number_input(self, *_args, **_kwargs):
            return 2026

        def radio(self, _label, options, index=0, **_kwargs):
            return options[index]

        def button(self, _label, **_kwargs):
            return True

    stub = _GraphStub()
    monkeypatch.setattr(comm, "st", stub)
    monkeypatch.setattr(comm, "is_graph_onedrive", lambda: True)
    monkeypatch.setattr(
        comm,
        "_list_onedrive_planning_files",
        lambda _year: [{"name": "planning.xlsx", "path": "remote/planning.xlsx"}],
    )
    monkeypatch.setattr(comm, "get_tmp_dir", lambda: tmp_path)
    monkeypatch.setattr(comm, "safe_cache_path", lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad")))

    out = comm._load_onedrive_planning_ui()

    assert out is None
    assert any("Chemin OneDrive invalide" in msg for msg in stub.errors)


def test_load_onedrive_planning_ui_graph_download_failure(monkeypatch, tmp_path):
    class _GraphStub(_StubSt):
        def __init__(self):
            super().__init__()
            self.session_state: dict[str, object] = {}

        def number_input(self, *_args, **_kwargs):
            return 2026

        def radio(self, _label, options, index=0, **_kwargs):
            return options[index]

        def button(self, _label, **_kwargs):
            return True

    stub = _GraphStub()
    monkeypatch.setattr(comm, "st", stub)
    monkeypatch.setattr(comm, "is_graph_onedrive", lambda: True)
    monkeypatch.setattr(
        comm,
        "_list_onedrive_planning_files",
        lambda _year: [{"name": "planning.xlsx", "path": "remote/planning.xlsx"}],
    )
    monkeypatch.setattr(comm, "get_tmp_dir", lambda: tmp_path)
    monkeypatch.setattr(comm, "safe_cache_path", lambda root, _remote: root / "planning.xlsx")
    monkeypatch.setattr(comm.cp, "download_onedrive_file", lambda *_args, **_kwargs: False)

    out = comm._load_onedrive_planning_ui()

    assert out is None
    assert any("Téléchargement OneDrive impossible." in msg for msg in stub.errors)
