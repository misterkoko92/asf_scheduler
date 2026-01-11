# pdf_attachments.py
# --------------------------------------------------
# Helpers to attach BE PDF files to communication emails.

from pathlib import Path
import os
import re

import pandas as pd

from scheduler.format_rules import format_be_number
import scheduler.config_paths as cp

_BE_FILENAME_RE = re.compile(r"\bBE\D*([0-9]{6})(?![0-9])", re.IGNORECASE)
_DEFAULT_DIR_NAME = "8-Listes de colisage"


def get_colisage_dir() -> Path | str:
    env_override = os.getenv("ASF_LISTES_COLISAGE_DIR")
    if env_override:
        return Path(env_override).expanduser()
    if cp.is_graph_onedrive():
        return cp.LISTES_COLISAGE_REMOTE_DIR
    return cp.ASF_ONEDRIVE / _DEFAULT_DIR_NAME


def _normalize_be_key(value: str) -> str:
    digits = format_be_number(value)
    if len(digits) >= 6:
        return digits[-6:]
    return digits


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
    if cp.is_graph_onedrive():
        remote_dir = str(base_dir)
        items = cp.list_onedrive_files(remote_dir, recursive=True, suffixes=[".pdf"])
        for item in items:
            name = item.get("name", "")
            path = item.get("path", "")
            match = _BE_FILENAME_RE.search(name)
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
            if cp.is_graph_onedrive():
                remote_path = str(entry)
                local_path = cp.TMP_DIR / "onedrive_cache" / "listes_colisage" / remote_path
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
