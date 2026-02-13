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
