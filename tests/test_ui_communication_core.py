# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib
import os
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pandas as pd


def _ensure_yaml_stub() -> None:
    if "yaml" in sys.modules:
        return
    yaml_stub = types.ModuleType("yaml")
    yaml_stub.safe_load = lambda *args, **kwargs: {}
    yaml_stub.safe_dump = lambda *args, **kwargs: None
    sys.modules["yaml"] = yaml_stub


_ensure_yaml_stub()
comm = importlib.import_module("asf_app.ui.ui_communication.ui_communication")


def test_parse_onedrive_datetime_handles_invalid_values():
    assert comm._parse_onedrive_datetime("2026-01-01T12:00:00Z") is not None
    assert comm._parse_onedrive_datetime("not-a-date") is None
    assert comm._parse_onedrive_datetime(None) is None


def test_read_export_planning_returns_empty_on_read_error(monkeypatch):
    def _raise(*args, **kwargs):
        raise ValueError("bad excel")

    monkeypatch.setattr(comm.pd, "read_excel", _raise)

    out = comm._read_export_planning(Path("x.xlsx"))

    assert out.empty


def test_read_export_planning_normalizes_dataframe(monkeypatch):
    monkeypatch.setattr(
        comm.pd,
        "read_excel",
        lambda *args, **kwargs: pd.DataFrame([{"A": 1}]),
    )
    monkeypatch.setattr(
        comm,
        "normalize_planning_df",
        lambda df: df.assign(B=2),
    )

    out = comm._read_export_planning(Path("x.xlsx"))

    assert list(out.columns) == ["A", "B"]
    assert out.iloc[0]["B"] == 2


def test_detect_week_year_from_date_column():
    df = pd.DataFrame({"DATE": ["2026-01-05", "2026-01-06"]})
    week, year = comm._detect_week_year(df)

    assert week == 2
    assert year == 2026


def test_detect_week_year_invalid_or_missing_values():
    assert comm._detect_week_year(pd.DataFrame()) == (None, None)
    assert comm._detect_week_year(pd.DataFrame({"DATE": ["invalid"]})) == (None, None)


def test_list_local_planning_files_sorted_by_mtime(monkeypatch, tmp_path):
    monkeypatch.setattr(comm, "get_onedrive_root", lambda: tmp_path)
    base = tmp_path / "Planning MAB" / "ASFmm PLANNING 2026"
    base.mkdir(parents=True)
    older = base / "older.xlsx"
    newer = base / "newer.xlsm"
    ignored = base / "note.txt"
    older.write_text("x", encoding="utf-8")
    newer.write_text("x", encoding="utf-8")
    ignored.write_text("x", encoding="utf-8")
    os.utime(older, (1, 1))
    os.utime(newer, (2, 2))

    files = comm._list_local_planning_files(2026)

    assert [p.name for p in files] == ["newer.xlsm", "older.xlsx"]


def test_list_onedrive_planning_files_filters_and_sorts(monkeypatch):
    monkeypatch.setattr(comm, "get_output_remote_dir", lambda year: f"Planning/{year}")
    monkeypatch.setattr(
        comm.cp,
        "list_onedrive_files",
        lambda remote_dir, recursive=False, suffixes=None: [
            {
                "name": "older.xlsx",
                "path": f"{remote_dir}/older.xlsx",
                "lastModifiedDateTime": "2026-01-01T10:00:00Z",
            },
            {
                "name": "newer.xlsm",
                "path": f"{remote_dir}/newer.xlsm",
                "createdDateTime": "2026-01-02T10:00:00Z",
            },
            {
                "name": "folder",
                "path": f"{remote_dir}/folder",
                "folder": {},
            },
            {
                "name": "ignored.csv",
                "path": f"{remote_dir}/ignored.csv",
                "lastModifiedDateTime": "2026-01-03T10:00:00Z",
            },
        ],
    )

    files = comm._list_onedrive_planning_files(2026)

    assert [f["name"] for f in files] == ["newer.xlsm", "older.xlsx"]
    assert files[0]["path"].endswith("newer.xlsm")


class _StubSt:
    def __init__(self):
        self.session_state: dict[str, object] = {}
        self.warnings: list[str] = []
        self.infos: list[str] = []
        self.errors: list[str] = []
        self._radio_values: dict[str, object] = {}
        self._button_values: dict[str, bool] = {}
        self._number_value = 2026

    def warning(self, msg):
        self.warnings.append(str(msg))

    def info(self, msg):
        self.infos.append(str(msg))

    def error(self, msg):
        self.errors.append(str(msg))

    def radio(self, label, options, index=0, key=None, **kwargs):
        _ = kwargs
        if key and key in self._radio_values:
            return self._radio_values[key]
        if label in self._radio_values:
            return self._radio_values[label]
        return options[index]

    def button(self, label, **kwargs):
        _ = kwargs
        return self._button_values.get(label, False)

    def number_input(self, label, **kwargs):
        _ = label, kwargs
        return self._number_value


class _RenderCol:
    def __init__(self, parent: "_RenderStubSt"):
        self.parent = parent

    def button(self, label, **kwargs):
        return self.parent.button(label, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        _ = exc_type, exc, tb
        return False


class _RenderStubSt(_StubSt):
    def __init__(self):
        super().__init__()
        self.successes: list[str] = []
        self.titles: list[str] = []

    def title(self, msg):
        self.titles.append(str(msg))

    def success(self, msg):
        self.successes.append(str(msg))

    def divider(self):
        return None

    def dataframe(self, *_args, **_kwargs):
        return None

    def markdown(self, *_args, **_kwargs):
        return None

    def expander(self, *_args, **_kwargs):
        return _RenderCol(self)

    def columns(self, n, **_kwargs):
        return [_RenderCol(self) for _ in range(int(n))]

    def code(self, *_args, **_kwargs):
        return None


def test_load_session_planning_ui_main_mode(monkeypatch):
    stub = _StubSt()
    monkeypatch.setattr(comm, "st", stub)
    monkeypatch.setattr(comm, "get_planning_state", lambda: SimpleNamespace(planning=pd.DataFrame([{"x": 1}])))
    monkeypatch.setattr(comm, "normalize_planning_df", lambda df: df if df is not None else pd.DataFrame())

    out = comm._load_session_planning_ui()

    assert isinstance(out, pd.DataFrame)
    assert not out.empty
    assert any("Moteur principal" in msg for msg in stub.infos)


def test_load_session_planning_ui_simulation_mode(monkeypatch):
    stub = _StubSt()
    stub.session_state["sim_results"] = {
        "colis": {"planning_df": pd.DataFrame([{"mode": "colis"}])},
        "benevoles": {"planning_df": pd.DataFrame([{"mode": "benevoles"}])},
    }
    stub.session_state["sim_active_mode"] = "colis"
    stub._radio_values["Source session"] = "simulation"
    stub._radio_values["Mode OR-Tools"] = "colis"

    monkeypatch.setattr(comm, "st", stub)
    monkeypatch.setattr(comm, "get_planning_state", lambda: SimpleNamespace(planning=pd.DataFrame()))
    monkeypatch.setattr(comm, "normalize_planning_df", lambda df: df if df is not None else pd.DataFrame())

    out = comm._load_session_planning_ui()

    assert isinstance(out, pd.DataFrame)
    assert out.iloc[0]["mode"] == "colis"
    assert stub.session_state["sim_active_mode"] == "colis"
    assert any("Planning OR-Tools" in msg for msg in stub.infos)


def test_load_onedrive_planning_ui_local_validated_file(monkeypatch):
    stub = _StubSt()
    stub._radio_values["comm_onedrive_file"] = "planning.xlsx"
    stub._button_values["✅ Valider ce planning"] = True
    monkeypatch.setattr(comm, "st", stub)
    monkeypatch.setattr(comm, "is_graph_onedrive", lambda: False)
    monkeypatch.setattr(comm, "_list_local_planning_files", lambda year: [Path("planning.xlsx")])
    monkeypatch.setattr(comm, "_read_export_planning", lambda path: pd.DataFrame([{"A": 1}]))

    out = comm._load_onedrive_planning_ui()

    assert isinstance(out, pd.DataFrame)
    assert out.iloc[0]["A"] == 1
    assert stub.session_state["comm_onedrive_file_label"] == "planning.xlsx"


def test_load_onedrive_planning_ui_local_without_file(monkeypatch):
    stub = _StubSt()
    monkeypatch.setattr(comm, "st", stub)
    monkeypatch.setattr(comm, "is_graph_onedrive", lambda: False)
    monkeypatch.setattr(comm, "_list_local_planning_files", lambda year: [])

    out = comm._load_onedrive_planning_ui()

    assert out is None
    assert any("Aucun fichier Excel" in msg for msg in stub.warnings)


def test_render_tab_communication_session_whatsapp_smoke(monkeypatch):
    stub = _RenderStubSt()
    monkeypatch.setattr(comm, "st", stub)
    monkeypatch.setattr(comm, "get_state", lambda: SimpleNamespace())
    monkeypatch.setattr(
        comm,
        "get_excel_source_paths",
        lambda _state: SimpleNamespace(
            tableau_de_bord=Path("tdb.xlsx"),
            planning_benevoles=Path("benev.xlsx"),
            vols=Path("vols.xlsx"),
        ),
    )
    monkeypatch.setattr(
        comm,
        "_load_session_planning_ui",
        lambda: pd.DataFrame([{"Date_Vol": "2026-01-19", "BE_Numero": "260001"}]),
    )
    monkeypatch.setattr(comm, "_load_onedrive_planning_ui", lambda: None)
    monkeypatch.setattr(
        comm,
        "load_parameters",
        lambda **_kwargs: (pd.DataFrame([{"Dest_IATA": "RUN"}]), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()),
    )
    monkeypatch.setattr(
        comm,
        "build_df_comm",
        lambda **_kwargs: pd.DataFrame(
            [
                {
                    "DATE": "2026-01-19",
                    "Destination": "RUN",
                    "Expediteur": "ASF",
                    "Destinataire": "Hopital",
                    "Benevole": "ALICE",
                    "Telephone": "0600000000",
                }
            ]
        ),
    )
    monkeypatch.setattr(comm, "get_shipments_df_cached", lambda **_kwargs: pd.DataFrame())
    monkeypatch.setattr(comm, "build_destinataire_mapping", lambda **_kwargs: {})
    monkeypatch.setattr(comm, "fill_missing_destinataire", lambda df, _map: df)
    monkeypatch.setattr(comm, "is_graph_onedrive", lambda: False)
    monkeypatch.setattr(comm, "get_onedrive_root", lambda: Path("/nonexistent"))
    monkeypatch.setattr(comm, "build_communication_display_dataframe", lambda df: df)
    monkeypatch.setattr(comm, "generate_whatsapp_messages", lambda _df: [])

    comm.render_tab_communication()

    assert any("Communication pour S4" in msg for msg in stub.successes)
    assert any("Pas de planning PDF trouvé" in msg for msg in stub.warnings)


def test_list_local_planning_files_returns_empty_when_base_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(comm, "get_onedrive_root", lambda: tmp_path)
    assert comm._list_local_planning_files(2026) == []


def test_read_export_planning_returns_empty_when_sheet_is_empty(monkeypatch):
    monkeypatch.setattr(comm.pd, "read_excel", lambda *args, **kwargs: pd.DataFrame())
    out = comm._read_export_planning(Path("x.xlsx"))
    assert out.empty


def test_load_session_planning_ui_warns_when_no_available_plan(monkeypatch):
    stub = _StubSt()
    monkeypatch.setattr(comm, "st", stub)
    monkeypatch.setattr(comm, "get_planning_state", lambda: SimpleNamespace(planning=pd.DataFrame()))
    monkeypatch.setattr(comm, "normalize_planning_df", lambda df: df if df is not None else pd.DataFrame())

    out = comm._load_session_planning_ui()
    assert out is None
    assert any("Aucun planning principal" in msg for msg in stub.warnings)


def test_load_session_planning_ui_warns_when_selected_simulation_is_empty(monkeypatch):
    stub = _StubSt()
    stub.session_state["sim_results"] = {"colis": {"planning_df": pd.DataFrame()}}
    stub.session_state["sim_active_mode"] = "colis"
    stub._radio_values["Source session"] = "simulation"
    monkeypatch.setattr(comm, "st", stub)
    monkeypatch.setattr(comm, "get_planning_state", lambda: SimpleNamespace(planning=pd.DataFrame([{"x": 1}])))
    monkeypatch.setattr(comm, "normalize_planning_df", lambda df: df if df is not None else pd.DataFrame())

    out = comm._load_session_planning_ui()
    assert out is None
    assert any("planning choisi est vide" in msg.lower() for msg in stub.warnings)


def test_load_onedrive_planning_ui_graph_branches(monkeypatch, tmp_path):
    stub = _StubSt()
    monkeypatch.setattr(comm, "st", stub)
    monkeypatch.setattr(comm, "is_graph_onedrive", lambda: True)
    monkeypatch.setattr(comm, "_list_onedrive_planning_files", lambda _year: [])

    out_empty = comm._load_onedrive_planning_ui()
    assert out_empty is None
    assert any("Aucun fichier Excel" in msg for msg in stub.warnings)

    stub_ok = _StubSt()
    stub_ok._button_values["✅ Valider ce planning"] = True
    monkeypatch.setattr(comm, "st", stub_ok)
    monkeypatch.setattr(
        comm,
        "_list_onedrive_planning_files",
        lambda _year: [{"name": "planning.xlsx", "path": "remote/planning.xlsx"}],
    )
    monkeypatch.setattr(comm, "get_tmp_dir", lambda: tmp_path)
    monkeypatch.setattr(comm, "safe_cache_path", lambda root, _remote: root / "planning.xlsx")
    monkeypatch.setattr(comm.cp, "download_onedrive_file", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(comm, "_read_export_planning", lambda _path: pd.DataFrame([{"A": 1}]))

    out_ok = comm._load_onedrive_planning_ui()
    assert isinstance(out_ok, pd.DataFrame)
    assert stub_ok.session_state["comm_onedrive_file_path"] == "remote/planning.xlsx"


def test_load_onedrive_planning_ui_local_empty_export_sheet(monkeypatch):
    stub = _StubSt()
    stub._button_values["✅ Valider ce planning"] = True
    monkeypatch.setattr(comm, "st", stub)
    monkeypatch.setattr(comm, "is_graph_onedrive", lambda: False)
    monkeypatch.setattr(comm, "_list_local_planning_files", lambda _year: [Path("planning.xlsx")])
    monkeypatch.setattr(comm, "_read_export_planning", lambda _path: pd.DataFrame())

    out = comm._load_onedrive_planning_ui()
    assert out is None
    assert any("Export planning" in msg for msg in stub.errors)


def test_select_communication_planning_source_onedrive(monkeypatch):
    stub = _StubSt()
    stub._radio_values["comm_source_mode"] = "onedrive"
    monkeypatch.setattr(comm, "st", stub)
    monkeypatch.setattr(comm, "_load_session_planning_ui", lambda: pd.DataFrame([{"x": 1}]))
    monkeypatch.setattr(comm, "_load_onedrive_planning_ui", lambda: pd.DataFrame([{"y": 2}]))
    out = comm._select_communication_planning_source()
    assert "y" in out.columns


def test_build_enriched_comm_dataframe_handles_shipments_io_error(monkeypatch):
    monkeypatch.setattr(comm, "build_df_comm", lambda **_kwargs: pd.DataFrame([{"A": 1}]))
    monkeypatch.setattr(comm, "get_shipments_df_cached", lambda **_kwargs: (_ for _ in ()).throw(OSError("boom")))
    monkeypatch.setattr(comm, "build_destinataire_mapping", lambda **_kwargs: {})
    monkeypatch.setattr(comm, "fill_missing_destinataire", lambda df, _map: df.assign(B=2))

    out = comm._build_enriched_comm_dataframe(
        df_planning=pd.DataFrame([{"x": 1}]),
        df_paramdest=pd.DataFrame(),
        df_parambenev=pd.DataFrame(),
        tdb_path=Path("tdb.xlsx"),
    )
    assert list(out.columns) == ["A", "B"]


def test_pdf_candidate_helpers_and_attachment_branches(monkeypatch, tmp_path):
    monkeypatch.setattr(comm, "get_output_remote_dir", lambda year: f"Planning/{year}")
    monkeypatch.setattr(
        comm.cp,
        "list_onedrive_files",
        lambda *_a, **_k: [{"name": "ASFmm - PLANNING SEMAINE 2026-04-01.pdf"}],
    )
    assert len(comm._resolve_pdf_candidates_from_graph(4, 2026)) == 1

    base = tmp_path / "Planning MAB" / "ASFmm PLANNING 2026"
    base.mkdir(parents=True)
    (base / "ASFmm - PLANNING SEMAINE 2026-04-01.pdf").write_text("pdf", encoding="utf-8")
    monkeypatch.setattr(comm, "get_onedrive_root", lambda: tmp_path)
    assert len(comm._resolve_pdf_candidates_from_local(4, 2026)) == 1

    stub = _StubSt()
    monkeypatch.setattr(comm, "st", stub)
    monkeypatch.setattr(comm, "is_graph_onedrive", lambda: True)
    monkeypatch.setattr(comm, "_resolve_pdf_candidates_from_graph", lambda _w, _y: [])
    assert comm._resolve_pdf_attachment_path(4, 2026) is None

    monkeypatch.setattr(
        comm,
        "_resolve_pdf_candidates_from_graph",
        lambda _w, _y: [{"name": "p.pdf", "path": ""}],
    )
    assert comm._resolve_pdf_attachment_path(4, 2026) is None

    monkeypatch.setattr(comm, "is_graph_onedrive", lambda: False)
    monkeypatch.setattr(
        comm,
        "_resolve_pdf_candidates_from_local",
        lambda _w, _y: (_ for _ in ()).throw(OSError("boom")),
    )
    assert comm._resolve_pdf_attachment_path(4, 2026) is None


def test_render_whatsapp_section_warns_when_generation_returns_empty(monkeypatch):
    class _WaStub(_StubSt):
        def markdown(self, *_a, **_k):
            return None

        def code(self, *_a, **_k):
            return None

        def success(self, msg):
            self.infos.append(str(msg))

    stub = _WaStub()
    stub._button_values["Générer les messages WhatsApp"] = True
    monkeypatch.setattr(comm, "st", stub)
    monkeypatch.setattr(comm, "generate_whatsapp_messages", lambda _df: [])
    comm._render_whatsapp_section(pd.DataFrame([{"x": 1}]))
    assert any("Aucun message généré." in msg for msg in stub.warnings)


def test_render_tab_communication_returns_early_when_payload_none(monkeypatch):
    stub = _RenderStubSt()
    monkeypatch.setattr(comm, "st", stub)
    monkeypatch.setattr(comm, "get_state", lambda: SimpleNamespace())
    monkeypatch.setattr(comm, "get_excel_source_paths", lambda _state: SimpleNamespace(tableau_de_bord=Path("tdb.xlsx")))
    monkeypatch.setattr(comm, "_build_communication_payload", lambda _paths: None)

    comm.render_tab_communication()
    assert stub.successes == []
