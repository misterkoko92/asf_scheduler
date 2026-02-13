# utils/cache_utils.py
# -*- coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path


def file_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except (FileNotFoundError, OSError, PermissionError, TypeError, ValueError):
        return 0.0
