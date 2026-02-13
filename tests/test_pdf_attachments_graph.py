# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import pandas as pd

from asf_app.ui.ui_communication import pdf_attachments as pa


def test_get_colisage_dir_graph_mode(monkeypatch):
    monkeypatch.delenv("ASF_LISTES_COLISAGE_DIR", raising=False)
    monkeypatch.setattr(pa, "is_graph_onedrive", lambda: True)
    monkeypatch.setattr(pa, "get_listes_colisage_remote_dir", lambda: "remote/listes")

    assert pa.get_colisage_dir() == "remote/listes"


def test_index_pdfs_by_be_graph_mode(monkeypatch):
    monkeypatch.setattr(pa, "is_graph_onedrive", lambda: True)
    monkeypatch.setattr(
        pa.cp,
        "list_onedrive_files",
        lambda *_args, **_kwargs: [
            {"name": "BE250123-v2.pdf", "path": "remote/b/BE250123-v2.pdf"},
            {"name": "BE250123-v1.pdf", "path": "remote/a/BE250123-v1.pdf"},
            {"name": "doc_250124.pdf", "path": "remote/c/doc_250124.pdf"},
            {"name": "ignore.txt", "path": "remote/c/ignore.txt"},
        ],
    )

    index = pa.index_pdfs_by_be("remote/listes")

    assert sorted(index.keys()) == ["250123", "250124"]
    assert index["250123"] == ["remote/a/BE250123-v1.pdf", "remote/b/BE250123-v2.pdf"]


def test_find_be_pdf_attachments_graph_download(monkeypatch, tmp_path):
    monkeypatch.setattr(pa, "is_graph_onedrive", lambda: True)
    monkeypatch.setattr(pa, "get_tmp_dir", lambda: tmp_path)

    def _safe_cache_path(cache_root: Path, remote_path: str) -> Path:
        return cache_root / Path(remote_path).name

    monkeypatch.setattr(pa, "safe_cache_path", _safe_cache_path)

    def _download(remote_path: str, local_path: Path, interactive=False):
        _ = interactive, remote_path
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(b"%PDF")
        return True

    monkeypatch.setattr(pa.cp, "download_onedrive_file", _download)

    df = pd.DataFrame({"Numero_BE_Aff": ["250123", "250124"]})
    index = {
        "250123": ["remote/listes/BE250123.pdf"],
        "250124": ["remote/listes/BE250124.pdf"],
    }

    attachments = pa.find_be_pdf_attachments(df_subset=df, pdf_index=index)

    assert len(attachments) == 2
    assert attachments[0].endswith("BE250123.pdf")
    assert attachments[1].endswith("BE250124.pdf")


def test_find_be_pdf_attachments_graph_ignores_invalid_remote_path(monkeypatch):
    monkeypatch.setattr(pa, "is_graph_onedrive", lambda: True)
    monkeypatch.setattr(pa, "get_tmp_dir", lambda: Path("/tmp"))
    monkeypatch.setattr(pa, "safe_cache_path", lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad")))

    df = pd.DataFrame({"Numero_BE_Aff": ["250123"]})
    index = {"250123": ["remote/listes/BE250123.pdf"]}

    attachments = pa.find_be_pdf_attachments(df_subset=df, pdf_index=index)

    assert attachments == []


def test_index_pdfs_by_be_local_returns_empty_when_base_dir_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(pa, "is_graph_onedrive", lambda: False)
    missing = tmp_path / "missing"

    assert pa.index_pdfs_by_be(missing) == {}
