# -*- coding: utf-8 -*-
from __future__ import annotations

import scheduler.config_paths as cp
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
