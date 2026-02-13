# -*- coding: utf-8 -*-
from __future__ import annotations

from utils.cache_utils import file_mtime


def test_file_mtime_missing_path_returns_zero(tmp_path):
    assert file_mtime(tmp_path / "missing.txt") == 0.0


def test_file_mtime_existing_path_returns_positive(tmp_path):
    path = tmp_path / "file.txt"
    path.write_text("x", encoding="utf-8")
    assert file_mtime(path) > 0
