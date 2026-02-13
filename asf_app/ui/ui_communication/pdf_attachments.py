# pdf_attachments.py
# --------------------------------------------------
# Helpers to attach BE PDF files to communication emails.

import os
import re
from pathlib import Path

import pandas as pd

import scheduler.config_paths as cp
from asf_app.config.runtime import (
    get_listes_colisage_remote_dir,
    get_onedrive_root,
    get_tmp_dir,
    is_graph_onedrive,
)
from utils.identifiers import normalize_be_number
from utils.logging_utils import get_logger
from utils.path_utils import safe_cache_path

_BE_FILENAME_RE = re.compile(r"\bBE\D*([0-9]{6})(?![0-9])", re.IGNORECASE)
_BARE_BE_FILENAME_RE = re.compile(r"(?<!\d)([0-9]{6})(?!\d)")
_DEFAULT_DIR_NAME = "8-Listes de colisage"
logger = get_logger("pdf_attachments", console=False)


def get_colisage_dir() -> Path | str:
    env_override = os.getenv("ASF_LISTES_COLISAGE_DIR")
    if env_override:
        return Path(env_override).expanduser()
    if is_graph_onedrive():
        return get_listes_colisage_remote_dir()
    return get_onedrive_root() / _DEFAULT_DIR_NAME


def _normalize_be_key(value: str) -> str:
    return normalize_be_number(value)


def collect_be_keys(df: pd.DataFrame) -> set[str]:
    if df is None or df.empty:
        return set()

    candidates: list[str] = []
    if "Numero_BE_Aff" in df.columns:
        candidates = df["Numero_BE_Aff"].dropna().astype(str).tolist()
    else:
        for col in ["NUMERO BE", "BE_Numero", "Numero_BE"]:
            if col in df.columns:
                candidates.extend(df[col].dropna().astype(str).tolist())

    keys = set()
    for val in candidates:
        key = _normalize_be_key(val)
        if key:
            keys.add(key)
    return keys


def index_pdfs_by_be(base_dir: Path | str | None = None) -> dict[str, list[str]]:
    base_dir = base_dir or get_colisage_dir()
    index: dict[str, list[str]] = {}
    if is_graph_onedrive():
        remote_dir = str(base_dir)
        items = cp.list_onedrive_files(remote_dir, recursive=True, suffixes=[".pdf"])
        for item in items:
            name = item.get("name", "")
            path = item.get("path", "")
            match = _BE_FILENAME_RE.search(name)
            if not match:
                match = _BARE_BE_FILENAME_RE.search(name)
            if not match:
                continue
            key = match.group(1)
            index.setdefault(key, []).append(path)
        for key, paths in index.items():
            index[key] = sorted(paths, key=lambda p: Path(p).name)
        return index

    base_dir = Path(base_dir)
    if not base_dir.exists():
        return index

    for path in base_dir.rglob("*.pdf"):
        if not path.is_file():
            continue
        match = _BE_FILENAME_RE.search(path.name)
        if not match:
            match = _BARE_BE_FILENAME_RE.search(path.name)
        if not match:
            continue
        key = match.group(1)
        index.setdefault(key, []).append(str(path))

    for key, paths in index.items():
        index[key] = sorted(paths, key=lambda p: Path(p).name)
    return index


def find_be_pdf_attachments(
    df_subset: pd.DataFrame,
    pdf_index: dict[str, list[str]] | None = None,
    base_dir: Path | str | None = None,
) -> list[str]:
    if df_subset is None or df_subset.empty:
        return []

    if pdf_index is None:
        pdf_index = index_pdfs_by_be(base_dir)
    if not pdf_index:
        return []

    be_keys = sorted(collect_be_keys(df_subset))
    attachments: list[str] = []
    for key in be_keys:
        for entry in pdf_index.get(key, []):
            if is_graph_onedrive():
                remote_path = str(entry)
                cache_root = get_tmp_dir() / "onedrive_cache" / "listes_colisage"
                try:
                    local_path = safe_cache_path(cache_root, remote_path)
                except ValueError as exc:
                    logger.warning("Chemin OneDrive invalide: %s (%s)", remote_path, exc)
                    continue
                if not local_path.exists():
                    cp.download_onedrive_file(remote_path, local_path, interactive=False)
                if local_path.exists():
                    attachments.append(str(local_path))
            else:
                attachments.append(str(entry))

    # De-duplicate while preserving order.
    seen = set()
    unique: list[str] = []
    for path in attachments:
        if path in seen:
            continue
        seen.add(path)
        unique.append(path)
    return unique
