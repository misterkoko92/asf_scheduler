# -*- coding: utf-8 -*-
from __future__ import annotations

import logging

import scheduler.config_paths as cp
import utils.logging_utils as logging_utils
from utils.logging_utils import get_logger


def test_get_logger_creates_file(tmp_path, monkeypatch):
    monkeypatch.setattr(cp, "TMP_DIR", tmp_path)
    logger = get_logger("test_logger")
    logger.info("hello")
    log_path = tmp_path / "test_logger.log"
    assert log_path.exists()


def test_get_logger_redacts_sensitive_values(tmp_path, monkeypatch):
    monkeypatch.setattr(cp, "TMP_DIR", tmp_path)
    logger = get_logger("test_logger_redact")
    logger.info("Authorization: Bearer ABCDEFGHIJKLMNOPQRSTUVWXYZ123456")
    logger.info("email=test.user@example.org phone=+33 6 12 34 56 78")
    logger.info("API_KEY=supersecretvalue123456")

    content = (tmp_path / "test_logger_redact.log").read_text(encoding="utf-8")
    assert "ABCDEFGHIJKLMNOPQRSTUVWXYZ123456" not in content
    assert "test.user@example.org" not in content
    assert "supersecretvalue123456" not in content
    assert "***REDACTED***" in content


def test_get_logger_reuses_same_file_handler_without_duplication(tmp_path, monkeypatch):
    monkeypatch.setattr(cp, "TMP_DIR", tmp_path)
    logger = get_logger("test_logger_single")
    first_handlers = list(logger.handlers)
    logger = get_logger("test_logger_single")
    second_handlers = list(logger.handlers)

    assert len(second_handlers) == len(first_handlers)
    assert sum(isinstance(h, logging.FileHandler) for h in second_handlers) == 1


def test_get_logger_with_explicit_log_path_and_console_flag(tmp_path):
    log_path = tmp_path / "custom" / "explicit.log"
    logger = get_logger("test_logger_explicit", log_path=log_path, console=True)
    logger.info("hello")

    assert log_path.exists()
    assert any(isinstance(h, logging.StreamHandler) for h in logger.handlers)


def test_get_logger_adds_console_handler_when_streamhandler_check_excludes_filehandler(
    monkeypatch,
    tmp_path,
):
    class _FakeFileHandler(logging.Handler):
        def __init__(self, filename, mode="a", encoding="utf-8"):
            _ = mode, encoding
            super().__init__()
            self.baseFilename = str(filename)

        def setFormatter(self, fmt):  # noqa: N802
            self.formatter = fmt

        def emit(self, record):
            _ = record
            return None

    class _FakeStreamHandler(logging.Handler):
        def setFormatter(self, fmt):  # noqa: N802
            self.formatter = fmt

        def emit(self, record):
            _ = record
            return None

    monkeypatch.setattr(cp, "TMP_DIR", tmp_path)
    monkeypatch.setattr(logging_utils.logging, "FileHandler", _FakeFileHandler)
    monkeypatch.setattr(logging_utils.logging, "StreamHandler", _FakeStreamHandler)
    logger = get_logger("test_logger_console_branch", log_path=tmp_path / "x.log", console=True)

    assert any(isinstance(h, _FakeStreamHandler) for h in logger.handlers)
