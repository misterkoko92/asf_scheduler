# -*- coding: utf-8 -*-
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import asf_app.ui.ui_logs as ui_logs


def test_write_and_read_log_file_roundtrip(tmp_path):
    path = tmp_path / "logs" / "asf_scheduler.log"
    assert ui_logs.write_log_file(path, "hello") is True
    assert path.exists()
    assert ui_logs.read_log_file(path) == "hello"


def test_write_log_file_reports_error_when_write_fails(monkeypatch, tmp_path):
    errors: list[str] = []
    monkeypatch.setattr(ui_logs.st, "error", lambda msg: errors.append(str(msg)))
    monkeypatch.setattr(Path, "write_text", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("boom")))

    ok = ui_logs.write_log_file(tmp_path / "x.log", "content")
    assert ok is False
    assert errors
    assert "Impossible d'ecrire" in errors[0] or "Impossible d'écrire" in errors[0]


def test_sync_to_onedrive_success_and_failure(monkeypatch, tmp_path):
    src = tmp_path / "tmp.log"
    src.write_text("abc", encoding="utf-8")
    dst = tmp_path / "onedrive" / "asf_scheduler.log"
    monkeypatch.setattr(ui_logs, "LOG_FILE_ONEDRIVE", dst)

    assert ui_logs.sync_to_onedrive(src) is True
    assert dst.read_text(encoding="utf-8") == "abc"

    errors: list[str] = []
    monkeypatch.setattr(ui_logs.st, "error", lambda msg: errors.append(str(msg)))
    monkeypatch.setattr(ui_logs.shutil, "copy2", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("copy-fail")))
    assert ui_logs.sync_to_onedrive(src) is False
    assert errors
    assert "synchroniser" in errors[0]


def test_build_logs_export_bundle_contains_log_and_context(monkeypatch, tmp_path):
    log_path = tmp_path / "asf_scheduler.log"
    log_path.write_text("line1\nline2", encoding="utf-8")

    version_dir = tmp_path / "app"
    version_dir.mkdir(parents=True, exist_ok=True)
    (version_dir / "VERSION").write_text("1.2.3", encoding="utf-8")
    monkeypatch.setattr(ui_logs.cp, "BASE_DIR", version_dir)

    payload = ui_logs.build_logs_export_bundle(log_path)
    with zipfile.ZipFile(io.BytesIO(payload), "r") as zf:
        names = set(zf.namelist())
        assert "asf_scheduler.log" in names
        assert "context.txt" in names
        assert "line1" in zf.read("asf_scheduler.log").decode("utf-8")
        context = zf.read("context.txt").decode("utf-8")
        assert "app_version=1.2.3" in context
