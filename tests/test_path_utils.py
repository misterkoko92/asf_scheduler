# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import pytest

from utils.path_utils import safe_cache_path


def test_safe_cache_path_allows_relative(tmp_path):
    cache_root = tmp_path / "cache"
    out = safe_cache_path(cache_root, "Planning/Exports/2026/file.xlsx")
    assert out == cache_root / "Planning" / "Exports" / "2026" / "file.xlsx"


def test_safe_cache_path_rejects_parent(tmp_path):
    cache_root = tmp_path / "cache"
    with pytest.raises(ValueError):
        safe_cache_path(cache_root, "Planning/../evil.xlsx")


def test_safe_cache_path_rejects_absolute(tmp_path):
    cache_root = tmp_path / "cache"
    with pytest.raises(ValueError):
        safe_cache_path(cache_root, "/abs/evil.xlsx")


def test_safe_cache_path_handles_backslashes(tmp_path):
    cache_root = tmp_path / "cache"
    out = safe_cache_path(cache_root, "Planning\\Exports\\file.xlsx")
    assert out == cache_root / "Planning" / "Exports" / "file.xlsx"
