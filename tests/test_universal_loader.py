# -*- coding: utf-8 -*-
from __future__ import annotations

import logging

import pandas as pd

from loaders.universal_loader import fuzzy_match_columns, load_and_normalize, normalize_header


def test_normalize_header_strips_accents_and_spaces():
    assert normalize_header("Téléphone 1") == "TELEPHONE 1"
    assert normalize_header("  DATE  DE  DEPART  ") == "DATE DE DEPART"


def test_fuzzy_match_columns_basic():
    df = pd.DataFrame({"N° BE": [1], "DATE IMPRESSION BE": ["01/01/2025"]})
    mapping = {"N° BE": "BE_Numero", "DATE IMPRESSION BE": "BE_Date_Impression"}
    df2 = fuzzy_match_columns(df, mapping)
    assert "BE_Numero" in df2.columns
    assert "BE_Date_Impression" in df2.columns


def test_load_and_normalize_logs_missing_columns(monkeypatch, caplog):
    monkeypatch.setattr(
        "loaders.universal_loader.pd.read_excel",
        lambda *args, **kwargs: pd.DataFrame({"A": [1]}),
    )
    mapping = {"A": "ColA", "B": "ColB"}

    with caplog.at_level(logging.INFO, logger="ASF-SCHEDULER"):
        out = load_and_normalize("dummy.xlsx", "Sheet1", mapping, header=0)

    assert "ColA" in out.columns
    assert "ColB" in out.columns
    assert any("Colonne manquante ajoutee: ColB" in msg for msg in caplog.messages)


def test_load_and_normalize_retries_with_resolved_sheet(monkeypatch):
    calls = {"n": 0}

    def _fake_read_excel(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ValueError("missing sheet")
        return pd.DataFrame({"A": [1]})

    monkeypatch.setattr("loaders.universal_loader.pd.read_excel", _fake_read_excel)
    monkeypatch.setattr("loaders.universal_loader._resolve_sheet_name", lambda path, sheet: "Resolved")

    out = load_and_normalize("dummy.xlsx", "Missing", {"A": "ColA"}, header=0)

    assert calls["n"] == 2
    assert "ColA" in out.columns
