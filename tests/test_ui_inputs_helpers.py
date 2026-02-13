# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd

import asf_app.ui.ui_inputs as ui_inputs
from asf_app.services.input_service import InputLoadError


def _build_state(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        tdb_tmp=tmp_path / "tdb.xlsx",
        benev_tmp=tmp_path / "benev.xlsx",
        vols_tmp=tmp_path / "vols.xlsx",
        df_be=None,
        df_param_be=None,
        df_param_dest=None,
        df_benev=None,
        df_param_benev=None,
        df_vols=None,
    )


def test_upload_too_large_reports_error(monkeypatch):
    class Upload:
        size = ui_inputs.MAX_UPLOAD_BYTES + 1

    errors: list[str] = []
    monkeypatch.setattr(ui_inputs.st, "error", lambda msg: errors.append(str(msg)))

    assert ui_inputs._upload_too_large(Upload(), "Vols.xlsx") is True
    assert errors
    assert "limite" in errors[0]


def test_upload_too_large_ignores_small_and_missing_size(monkeypatch):
    class UploadSmall:
        size = 12

    class UploadNoSize:
        pass

    errors: list[str] = []
    monkeypatch.setattr(ui_inputs.st, "error", lambda msg: errors.append(str(msg)))

    assert ui_inputs._upload_too_large(UploadSmall(), "Vols.xlsx") is False
    assert ui_inputs._upload_too_large(UploadNoSize(), "Vols.xlsx") is False
    assert errors == []


def test_pretty_mtime_ok_and_stat_error(monkeypatch, tmp_path):
    file_path = tmp_path / "f.xlsx"
    file_path.write_text("x", encoding="utf-8")
    assert ui_inputs.pretty_mtime(file_path) != "N/A"

    def _raise_stat(_self):
        raise OSError("boom")

    monkeypatch.setattr(Path, "stat", _raise_stat)
    assert ui_inputs.pretty_mtime(file_path) == "N/A"


def test_ensure_tmp_file_copy_and_overwrite(monkeypatch, tmp_path):
    src = tmp_path / "source.xlsx"
    src.write_text("v1", encoding="utf-8")
    tmp_dir = tmp_path / "tmp"

    monkeypatch.setattr(ui_inputs, "get_tmp_dir", lambda: tmp_dir)

    dst = ui_inputs.ensure_tmp_file(src, "VOLS.xlsx")
    assert dst.exists()
    assert dst.read_text(encoding="utf-8") == "v1"

    src.write_text("v2", encoding="utf-8")
    dst2 = ui_inputs.ensure_tmp_file(src, "VOLS.xlsx", overwrite=False)
    assert dst2.read_text(encoding="utf-8") == "v1"

    dst3 = ui_inputs.ensure_tmp_file(src, "VOLS.xlsx", overwrite=True)
    assert dst3.read_text(encoding="utf-8") == "v2"


def test_load_tdb_and_benev_show_input_load_error(monkeypatch, tmp_path):
    state = _build_state(tmp_path)
    errors: list[str] = []
    monkeypatch.setattr(ui_inputs.st, "error", lambda msg: errors.append(str(msg)))

    def _raise_input_load_error(*_args, **_kwargs):
        raise InputLoadError("boom")

    monkeypatch.setattr(ui_inputs, "load_tdb", _raise_input_load_error)
    monkeypatch.setattr(ui_inputs, "load_benev", _raise_input_load_error)

    ui_inputs.load_tdb_file(state, force=True)
    ui_inputs.load_benev_file(state, force=True)

    assert len(errors) == 2
    assert all("boom" in msg for msg in errors)


def test_load_vols_show_input_load_error(monkeypatch, tmp_path):
    state = _build_state(tmp_path)
    errors: list[str] = []
    monkeypatch.setattr(ui_inputs.st, "error", lambda msg: errors.append(str(msg)))

    def _raise_input_load_error(*_args, **_kwargs):
        raise InputLoadError("boom vols")

    monkeypatch.setattr(ui_inputs, "load_vols", _raise_input_load_error)
    ui_inputs.load_vols_file(state, force=True)

    assert errors == ["❌ boom vols"]


class _Ctx:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        _ = exc_type, exc, tb
        return False


class _StubInputsSt:
    def __init__(self):
        self.session_state: dict[str, object] = {}
        self.successes: list[str] = []
        self.errors: list[str] = []
        self.infos: list[str] = []
        self.warnings: list[str] = []

    def header(self, *_args, **_kwargs):
        return None

    def subheader(self, *_args, **_kwargs):
        return None

    def write(self, *_args, **_kwargs):
        return None

    def info(self, msg):
        self.infos.append(str(msg))

    def warning(self, msg):
        self.warnings.append(str(msg))

    def success(self, msg):
        self.successes.append(str(msg))

    def error(self, msg):
        self.errors.append(str(msg))

    def button(self, *_args, **_kwargs):
        return False

    def file_uploader(self, *_args, **_kwargs):
        return None

    def radio(self, _label, options, index=0, **_kwargs):
        return options[index]

    def columns(self, n, **_kwargs):
        _ = _kwargs
        return [_Ctx() for _ in range(int(n))]

    def selectbox(self, _label, options, index=0, **_kwargs):
        return options[index]

    def rerun(self):
        return None


def test_overwrite_tmp_file_updates_state_and_reloads(monkeypatch, tmp_path):
    stub = _StubInputsSt()
    monkeypatch.setattr(ui_inputs, "st", stub)
    synced: list[str] = []
    monkeypatch.setattr(ui_inputs.cp, "sync_local_file_to_onedrive", lambda p: synced.append(str(p)))
    monkeypatch.setattr(ui_inputs, "sync_state_paths_to_engine", lambda _state: None)
    state = _build_state(tmp_path)
    state.vols_tmp.write_bytes(b"old")
    state.df_vols = pd.DataFrame([{"a": 1}])
    called: list[bool] = []

    class Upload:
        def read(self):
            return b"new-content"

    def _reload(_state, force=False):
        called.append(bool(force))

    ui_inputs.overwrite_tmp_file(Upload(), state, "vols", _reload)

    assert state.vols_tmp.read_bytes() == b"new-content"
    assert state.df_vols is None
    assert called == [True]
    assert synced and str(state.vols_tmp) in synced[0]
    assert any("Fichier mis à jour" in msg for msg in stub.successes)


def test_refresh_from_onedrive_local_mode_resets_and_reloads(monkeypatch, tmp_path):
    stub = _StubInputsSt()
    monkeypatch.setattr(ui_inputs, "st", stub)
    monkeypatch.setattr(ui_inputs, "is_graph_onedrive", lambda: False)
    monkeypatch.setattr(ui_inputs, "sync_state_paths_to_engine", lambda _state: None)

    state = _build_state(tmp_path)
    state.tdb_tmp.write_bytes(b"old")
    state.df_be = pd.DataFrame([{"x": 1}])
    state.df_param_be = pd.DataFrame([{"x": 1}])
    state.df_param_dest = pd.DataFrame([{"x": 1}])
    src = tmp_path / "TABLEAU_DE_BORD_src.xlsx"
    src.write_bytes(b"src")
    copied = tmp_path / "TABLEAU_DE_BORD.xlsx"
    copied.write_bytes(b"copy")
    monkeypatch.setattr(ui_inputs, "ensure_tmp_file", lambda *_args, **_kwargs: copied)
    called: list[bool] = []

    def _reload(_state, force=False):
        called.append(bool(force))

    ui_inputs.refresh_from_onedrive(state, src, "tdb", _reload)

    assert state.tdb_tmp == copied
    assert state.df_be is None
    assert state.df_param_be is None
    assert state.df_param_dest is None
    assert called == [True]
    assert any("Rechargé depuis OneDrive" in msg for msg in stub.successes)


def test_refresh_all_resets_session_and_reloads(monkeypatch, tmp_path):
    stub = _StubInputsSt()
    stub.session_state["source_error"] = "boom"
    monkeypatch.setattr(ui_inputs, "st", stub)

    state = _build_state(tmp_path)
    tdb = tmp_path / "TABLEAU_DE_BORD.xlsx"
    benev = tmp_path / "PLANNING_BENEVOLES.xlsx"
    vols = tmp_path / "VOLS.xlsx"
    for p in (tdb, benev, vols):
        p.write_bytes(b"x")
    ctx = SimpleNamespace(source_paths=SimpleNamespace(tableau_de_bord=tdb, planning_benevoles=benev, vols=vols))
    monkeypatch.setattr(ui_inputs, "refresh_session_context", lambda strict_sources=True: ctx)
    monkeypatch.setattr(ui_inputs, "sync_state_paths_to_engine", lambda _state: None)
    calls: list[str] = []
    monkeypatch.setattr(ui_inputs, "load_tdb_file", lambda _state, force=False: calls.append(f"tdb:{force}"))
    monkeypatch.setattr(ui_inputs, "load_benev_file", lambda _state, force=False: calls.append(f"benev:{force}"))
    monkeypatch.setattr(ui_inputs, "load_vols_file", lambda _state, force=False: calls.append(f"vols:{force}"))

    ui_inputs.refresh_all(state)

    assert "source_error" not in stub.session_state
    assert state.tdb_tmp == tdb
    assert state.benev_tmp == benev
    assert state.vols_tmp == vols
    assert calls == ["tdb:True", "benev:True", "vols:True"]
    assert any("Tous les fichiers ont été rechargés" in msg for msg in stub.successes)


def test_render_tab_inputs_smoke_excel_mode(monkeypatch, tmp_path):
    stub = _StubInputsSt()
    monkeypatch.setattr(ui_inputs, "st", stub)
    monkeypatch.setattr(ui_inputs, "IS_STREAMLIT_CLOUD", False)
    monkeypatch.setattr(ui_inputs, "is_graph_onedrive", lambda: False)

    tdb = tmp_path / "TABLEAU_DE_BORD.xlsx"
    benev = tmp_path / "PLANNING_BENEVOLES.xlsx"
    vols = tmp_path / "VOLS.xlsx"
    for p in (tdb, benev, vols):
        p.write_bytes(b"x")

    state = SimpleNamespace(
        tdb_tmp=None,
        benev_tmp=None,
        vols_tmp=None,
        df_be=None,
        df_param_be=None,
        df_param_dest=pd.DataFrame([{"Dest_IATA": "RUN", "Ville": "SAINT-DENIS"}]),
        df_benev=None,
        df_param_benev=None,
        df_vols=pd.DataFrame([{"Date_Vol": "16/02/26"}]),
        vols_source="excel",
        api_start_date=None,
        api_end_date=None,
    )
    ctx = SimpleNamespace(source_paths=SimpleNamespace(tableau_de_bord=tdb, planning_benevoles=benev, vols=vols))
    monkeypatch.setattr(ui_inputs, "get_state", lambda: state)
    monkeypatch.setattr(ui_inputs, "get_session_context", lambda: ctx)
    monkeypatch.setattr(ui_inputs, "ensure_session_context", lambda strict_sources=True: ctx)
    monkeypatch.setattr(ui_inputs, "sync_state_paths_to_engine", lambda _state: None)
    monkeypatch.setattr(ui_inputs, "pick_planning_dates", lambda _state: None)
    monkeypatch.setattr(ui_inputs, "pretty_mtime", lambda _p: "16/02/2026 à 11:00")
    monkeypatch.setattr(ui_inputs, "benev_last_message", lambda _p: "none")
    monkeypatch.setattr(
        ui_inputs,
        "load_shipments_df",
        lambda **_kwargs: pd.DataFrame([{"Destination": "RUN"}, {"Destination": "RUN"}, {"Destination": "DLA"}]),
    )
    calls: list[str] = []
    monkeypatch.setattr(ui_inputs, "load_tdb_file", lambda _state, force=False: calls.append(f"tdb:{force}"))
    monkeypatch.setattr(ui_inputs, "load_benev_file", lambda _state, force=False: calls.append(f"benev:{force}"))
    monkeypatch.setattr(ui_inputs, "load_vols_file", lambda _state, force=False: calls.append(f"vols:{force}"))

    ui_inputs.render_tab_inputs()

    assert state.tdb_tmp == tdb
    assert state.benev_tmp == benev
    assert state.vols_tmp == vols
    assert calls == ["tdb:False", "benev:False", "vols:False"]
    assert stub.errors == []
