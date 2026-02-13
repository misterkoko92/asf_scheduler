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


def test_build_logs_export_bundle_redacts_sensitive_content(tmp_path):
    log_path = tmp_path / "asf_scheduler.log"
    log_path.write_text(
        "Authorization: Bearer ABCDEFGHIJKLMNOPQRSTUVWXYZ123456\n"
        "email=test.user@example.org\n"
        "phone=+33 6 12 34 56 78\n"
        "API_KEY=supersecretvalue123456\n",
        encoding="utf-8",
    )
    payload = ui_logs.build_logs_export_bundle(log_path)
    with zipfile.ZipFile(io.BytesIO(payload), "r") as zf:
        logs = zf.read("asf_scheduler.log").decode("utf-8")
        assert "ABCDEFGHIJKLMNOPQRSTUVWXYZ123456" not in logs
        assert "test.user@example.org" not in logs
        assert "supersecretvalue123456" not in logs
        assert "***REDACTED***" in logs


class _Ctx:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        _ = exc_type, exc, tb
        return False


class _StubLogsSt:
    __version__ = "1.42.0"

    def __init__(self):
        self._checkbox = False
        self._buttons: dict[str, bool] = {}
        self.infos: list[str] = []
        self.errors: list[str] = []
        self.successes: list[str] = []
        self.download_calls: list[dict[str, object]] = []
        self.text_areas: list[str] = []
        self.rerun_called = False
        self.experimental_rerun_called = False

    def header(self, *_args, **_kwargs):
        return None

    def checkbox(self, *_args, **_kwargs):
        return self._checkbox

    def caption(self, *_args, **_kwargs):
        return None

    def markdown(self, *_args, **_kwargs):
        return None

    def columns(self, spec, **_kwargs):
        count = len(spec) if isinstance(spec, (list, tuple)) else int(spec)
        return [_Ctx() for _ in range(count)]

    def button(self, label, **_kwargs):
        return bool(self._buttons.get(str(label), False))

    def download_button(self, label, **kwargs):
        payload = {"label": str(label), **kwargs}
        self.download_calls.append(payload)
        return None

    def success(self, msg):
        self.successes.append(str(msg))

    def info(self, msg):
        self.infos.append(str(msg))

    def error(self, msg):
        self.errors.append(str(msg))

    def text_area(self, _label, value="", **_kwargs):
        self.text_areas.append(str(value))
        return value

    def expander(self, *_args, **_kwargs):
        return _Ctx()

    def code(self, *_args, **_kwargs):
        return None

    def write(self, *_args, **_kwargs):
        return None

    def rerun(self):
        self.rerun_called = True

    def experimental_rerun(self):
        self.experimental_rerun_called = True


def test_resolve_log_file_dev_and_frozen(monkeypatch, tmp_path):
    monkeypatch.setattr(ui_logs.sys, "frozen", False, raising=False)
    monkeypatch.setattr(ui_logs, "get_tmp_dir", lambda: tmp_path)
    path_dev = ui_logs.resolve_log_file()
    assert path_dev == tmp_path / "asf_scheduler.log"

    monkeypatch.setattr(ui_logs.sys, "frozen", True, raising=False)
    monkeypatch.setattr(ui_logs.sys, "executable", str(tmp_path / "bin" / "asf"), raising=False)
    path_frozen = ui_logs.resolve_log_file()
    assert path_frozen == (tmp_path / "bin" / "asf_scheduler.log")
    monkeypatch.delattr(ui_logs.sys, "frozen", raising=False)


def test_render_tab_logs_clear_flow(monkeypatch, tmp_path):
    stub = _StubLogsSt()
    stub._checkbox = True
    stub._buttons["🗑️ Vider le log"] = True
    monkeypatch.setattr(ui_logs, "st", stub)
    monkeypatch.setattr(ui_logs, "LOG_FILE", tmp_path / "asf_scheduler.log")
    monkeypatch.setattr(ui_logs, "build_logs_export_bundle", lambda _p: b"zip")
    called = {"write": 0, "sync": 0}
    monkeypatch.setattr(ui_logs, "write_log_file", lambda _p, _c: called.__setitem__("write", called["write"] + 1) or True)
    monkeypatch.setattr(ui_logs, "sync_to_onedrive", lambda _p: called.__setitem__("sync", called["sync"] + 1) or True)

    ui_logs.render_tab_logs()

    assert called["write"] == 1
    assert called["sync"] == 1
    assert any("Log vidé" in msg for msg in stub.successes)
    assert stub.experimental_rerun_called is True


def test_render_tab_logs_missing_file_creates_placeholder(monkeypatch, tmp_path):
    stub = _StubLogsSt()
    monkeypatch.setattr(ui_logs, "st", stub)
    log_path = tmp_path / "missing.log"
    monkeypatch.setattr(ui_logs, "LOG_FILE", log_path)
    monkeypatch.setattr(ui_logs, "build_logs_export_bundle", lambda _p: b"zip")

    ui_logs.render_tab_logs()

    assert log_path.exists()
    assert any("Aucun log trouvé" in msg for msg in stub.infos)


def test_render_tab_logs_download_and_reload(monkeypatch, tmp_path):
    stub = _StubLogsSt()
    stub._buttons["⬇ Télécharger le log"] = True
    stub._buttons["🔄 Recharger"] = True
    monkeypatch.setattr(ui_logs, "st", stub)
    log_path = tmp_path / "asf_scheduler.log"
    log_path.write_text("line1\nline2", encoding="utf-8")
    monkeypatch.setattr(ui_logs, "LOG_FILE", log_path)
    monkeypatch.setattr(ui_logs, "pretty_mtime", lambda _p: "16/02/2026 11:00:00")
    monkeypatch.setattr(ui_logs, "build_logs_export_bundle", lambda _p: b"zip")

    ui_logs.render_tab_logs()

    assert stub.text_areas and "line1" in stub.text_areas[0]
    assert len(stub.download_calls) >= 2
    assert stub.rerun_called is True


def test_render_tab_logs_download_is_redacted(monkeypatch, tmp_path):
    stub = _StubLogsSt()
    stub._buttons["⬇ Télécharger le log"] = True
    monkeypatch.setattr(ui_logs, "st", stub)
    log_path = tmp_path / "asf_scheduler.log"
    log_path.write_text("API_KEY=supersecretvalue123456", encoding="utf-8")
    monkeypatch.setattr(ui_logs, "LOG_FILE", log_path)
    monkeypatch.setattr(ui_logs, "build_logs_export_bundle", lambda _p: b"zip")

    ui_logs.render_tab_logs()

    raw_downloads = [d for d in stub.download_calls if d.get("file_name") == "asf_scheduler.log"]
    assert raw_downloads
    downloaded = bytes(raw_downloads[0]["data"]).decode("utf-8")
    assert "supersecretvalue123456" not in downloaded
    assert "***REDACTED***" in downloaded


def test_pretty_mtime_returns_na_on_error(monkeypatch, tmp_path):
    monkeypatch.setattr(ui_logs.os.path, "getmtime", lambda _p: (_ for _ in ()).throw(OSError("boom")))
    assert ui_logs.pretty_mtime(tmp_path / "x.log") == "N/A"


def test_read_log_file_reports_error_on_failure(monkeypatch, tmp_path):
    errors: list[str] = []
    monkeypatch.setattr(ui_logs.st, "error", lambda msg: errors.append(str(msg)))
    monkeypatch.setattr(Path, "read_text", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("boom")))
    assert ui_logs.read_log_file(tmp_path / "x.log") == ""
    assert any("Erreur lors de la lecture des logs" in msg for msg in errors)


def test_build_logs_export_bundle_handles_version_read_error(monkeypatch, tmp_path):
    version_dir = tmp_path / "app"
    version_dir.mkdir(parents=True, exist_ok=True)
    version_file = version_dir / "VERSION"
    version_file.write_text("1.2.3", encoding="utf-8")
    monkeypatch.setattr(ui_logs.cp, "BASE_DIR", version_dir)

    orig_read_text = Path.read_text

    def _read_text(self, *args, **kwargs):
        if self == version_file:
            raise OSError("no-read")
        return orig_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _read_text)
    payload = ui_logs.build_logs_export_bundle(tmp_path / "missing.log")
    with zipfile.ZipFile(io.BytesIO(payload), "r") as zf:
        context = zf.read("context.txt").decode("utf-8")
        assert "app_version=unknown" in context


class _MissingLogPath:
    def exists(self):
        return False

    def touch(self):
        raise OSError("touch-fail")

    def __str__(self):
        return "missing.log"


def test_render_tab_logs_missing_file_touch_error_is_ignored(monkeypatch):
    stub = _StubLogsSt()
    monkeypatch.setattr(ui_logs, "st", stub)
    monkeypatch.setattr(ui_logs, "LOG_FILE", _MissingLogPath())
    monkeypatch.setattr(ui_logs, "build_logs_export_bundle", lambda _p: b"zip")

    ui_logs.render_tab_logs()
    assert any("Aucun log trouvé" in msg for msg in stub.infos)


def test_render_tab_logs_handles_raw_bytes_read_failure(monkeypatch, tmp_path):
    stub = _StubLogsSt()
    monkeypatch.setattr(ui_logs, "st", stub)
    log_path = tmp_path / "asf_scheduler.log"
    log_path.write_text("hello", encoding="utf-8")
    monkeypatch.setattr(ui_logs, "LOG_FILE", log_path)
    monkeypatch.setattr(ui_logs, "build_logs_export_bundle", lambda _p: b"zip")

    orig_read_bytes = Path.read_bytes

    def _read_bytes(self, *args, **kwargs):
        if self == log_path:
            raise OSError("raw-fail")
        return orig_read_bytes(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", _read_bytes)
    ui_logs.render_tab_logs()
    assert any("Erreur lecture brut" in msg for msg in stub.errors)


class _StubLogsNoRerun(_StubLogsSt):
    def __getattribute__(self, name):
        if name == "rerun":
            raise AttributeError
        return super().__getattribute__(name)

    def experimental_rerun(self):
        raise RuntimeError("rerun-fail")


def test_render_tab_logs_reload_fallback_handles_experimental_error(monkeypatch, tmp_path):
    stub = _StubLogsNoRerun()
    stub._buttons["🔄 Recharger"] = True
    monkeypatch.setattr(ui_logs, "st", stub)
    log_path = tmp_path / "asf_scheduler.log"
    log_path.write_text("x", encoding="utf-8")
    monkeypatch.setattr(ui_logs, "LOG_FILE", log_path)
    monkeypatch.setattr(ui_logs, "build_logs_export_bundle", lambda _p: b"zip")
    ui_logs.render_tab_logs()


class _BadParent:
    def mkdir(self, *args, **kwargs):
        _ = args, kwargs
        raise OSError("onedrive-denied")


class _BadOneDrivePath:
    parent = _BadParent()

    def __str__(self):
        return "onedrive.log"


def test_render_tab_logs_diagnostic_reports_local_and_onedrive_permissions(monkeypatch, tmp_path):
    stub = _StubLogsSt()
    stub._checkbox = True
    monkeypatch.setattr(ui_logs, "st", stub)
    log_path = tmp_path / "asf_scheduler.log"
    log_path.write_text("hello", encoding="utf-8")
    monkeypatch.setattr(ui_logs, "LOG_FILE", log_path)
    monkeypatch.setattr(ui_logs, "LOG_FILE_ONEDRIVE", _BadOneDrivePath())
    monkeypatch.setattr(ui_logs, "build_logs_export_bundle", lambda _p: b"zip")

    orig_open = Path.open

    def _open(self, *args, **kwargs):
        if self == log_path:
            raise OSError("local-denied")
        return orig_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", _open)
    ui_logs.render_tab_logs()
    assert any("Écriture locale impossible" in msg for msg in stub.errors)
    assert any("OneDrive inaccessible" in msg for msg in stub.errors)
