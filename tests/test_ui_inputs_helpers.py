# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

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
