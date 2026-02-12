# utils/path_utils.py
# -*- coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path, PurePosixPath


def safe_cache_path(cache_root: Path, remote_path: str) -> Path:
    """
    Build a safe local cache path from a OneDrive remote path.
    Rejects absolute paths and parent traversal segments.
    """
    if not remote_path:
        raise ValueError("remote_path vide")
    remote = str(remote_path).strip().replace("\\", "/")
    pure = PurePosixPath(remote)
    if pure.is_absolute():
        raise ValueError(f"chemin absolu interdit: {remote_path}")
    parts = [p for p in pure.parts if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise ValueError(f"chemin parent interdit: {remote_path}")
    return cache_root.joinpath(*parts)
