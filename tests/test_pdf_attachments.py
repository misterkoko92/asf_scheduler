# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import pandas as pd

from asf_app.ui.ui_communication import pdf_attachments as pa


def test_get_colisage_dir_prefers_env_override(monkeypatch, tmp_path):
    custom = tmp_path / "colisage"
    monkeypatch.setenv("ASF_LISTES_COLISAGE_DIR", str(custom))

    assert pa.get_colisage_dir() == custom


def test_collect_be_keys_reads_main_column_and_normalizes():
    df = pd.DataFrame(
        {
            "Numero_BE_Aff": ["BE 250123", "250124", None, "invalid"],
            "BE_Numero": ["250999", "251000", "251001", "251002"],
        }
    )

    assert pa.collect_be_keys(df) == {"250123", "250124"}


def test_index_pdfs_by_be_local_mode(tmp_path, monkeypatch):
    monkeypatch.delenv("ASF_LISTES_COLISAGE_DIR", raising=False)
    monkeypatch.setattr(pa, "is_graph_onedrive", lambda: False)

    (tmp_path / "doc_BE250123_a.pdf").write_bytes(b"%PDF-1.4\n")
    (tmp_path / "x_250123.pdf").write_bytes(b"%PDF-1.4\n")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "be_250124.pdf").write_bytes(b"%PDF-1.4\n")
    (nested / "ignore.txt").write_text("nope", encoding="utf-8")

    index = pa.index_pdfs_by_be(tmp_path)

    assert sorted(index.keys()) == ["250123", "250124"]
    assert index["250123"] == sorted(index["250123"], key=lambda p: Path(p).name)
    assert len(index["250123"]) == 2
    assert len(index["250124"]) == 1


def test_find_be_pdf_attachments_deduplicates(monkeypatch):
    monkeypatch.setattr(pa, "is_graph_onedrive", lambda: False)

    df = pd.DataFrame({"NUMERO BE": ["250123", "250123", "250124"]})
    index = {
        "250123": ["/tmp/BE250123.pdf", "/tmp/BE250123.pdf"],
        "250124": ["/tmp/BE250124.pdf"],
    }

    attachments = pa.find_be_pdf_attachments(df_subset=df, pdf_index=index)

    assert attachments == ["/tmp/BE250123.pdf", "/tmp/BE250124.pdf"]
