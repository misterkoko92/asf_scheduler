# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import utils.export_pdf as export_pdf


def test_export_first_sheet_to_pdf_requires_macos(tmp_path, monkeypatch):
    xlsx = tmp_path / "sample.xlsx"
    xlsx.write_text("dummy", encoding="utf-8")
    monkeypatch.setattr(export_pdf.sys, "platform", "linux")

    with pytest.raises(RuntimeError, match="only supported on macOS"):
        export_pdf.export_first_sheet_to_pdf(xlsx)


def test_export_first_sheet_to_pdf_raises_when_osascript_fails(tmp_path, monkeypatch):
    xlsx = tmp_path / "sample.xlsx"
    xlsx.write_text("dummy", encoding="utf-8")

    monkeypatch.setattr(export_pdf.sys, "platform", "darwin")
    monkeypatch.setattr(
        export_pdf.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stderr="boom", stdout=""),
    )

    with pytest.raises(RuntimeError, match="AppleScript export failed"):
        export_pdf.export_first_sheet_to_pdf(xlsx)


def test_export_first_sheet_to_pdf_raises_when_pdf_not_generated(tmp_path, monkeypatch):
    xlsx = tmp_path / "sample.xlsx"
    xlsx.write_text("dummy", encoding="utf-8")
    pdf = tmp_path / "sample.pdf"

    monkeypatch.setattr(export_pdf.sys, "platform", "darwin")
    monkeypatch.setattr(
        export_pdf.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stderr="", stdout=""),
    )

    with pytest.raises(RuntimeError, match="PDF not generated"):
        export_pdf.export_first_sheet_to_pdf(xlsx, pdf)


def test_export_first_sheet_to_pdf_success_and_cleanup_error_is_ignored(tmp_path, monkeypatch):
    xlsx = tmp_path / "sample.xlsx"
    xlsx.write_text("dummy", encoding="utf-8")
    pdf = tmp_path / "out.pdf"

    monkeypatch.setattr(export_pdf.sys, "platform", "darwin")
    monkeypatch.setattr(export_pdf.tempfile, "gettempdir", lambda: str(tmp_path))

    def _fake_run(*_args, **_kwargs):
        pdf.write_bytes(b"%PDF-1.4")
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr(export_pdf.subprocess, "run", _fake_run)

    original_unlink = Path.unlink

    def _unlink_with_failure(self: Path, *args, **kwargs):
        if self.name.endswith("_pdf_tmp.xlsx"):
            raise PermissionError("locked")
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", _unlink_with_failure)

    out = export_pdf.export_first_sheet_to_pdf(xlsx, pdf)
    assert out == pdf
    assert out.exists()
