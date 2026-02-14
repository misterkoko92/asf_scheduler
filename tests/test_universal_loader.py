# -*- coding: utf-8 -*-
from __future__ import annotations

import logging

import pandas as pd

import loaders.universal_loader as ul
from loaders.universal_loader import (
    _resolve_sheet_name,
    _warn_unmapped_columns,
    fuzzy_match_columns,
    load_and_normalize,
    normalize_header,
)


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


def test_resolve_sheet_name_keeps_original_for_non_string():
    assert _resolve_sheet_name("dummy.xlsx", 0) == 0


def test_resolve_sheet_name_selects_latest_prefixed_candidate(monkeypatch):
    class _Book:
        sheet_names = ["ParamDest 2024", "ParamDest 2026", "Other"]

    monkeypatch.setattr("loaders.universal_loader.pd.ExcelFile", lambda *_args, **_kwargs: _Book())
    assert _resolve_sheet_name("dummy.xlsx", "ParamDest") == "ParamDest 2026"


def test_resolve_sheet_name_returns_original_when_excelfile_fails(monkeypatch):
    monkeypatch.setattr(
        "loaders.universal_loader.pd.ExcelFile",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("boom")),
    )
    assert _resolve_sheet_name("dummy.xlsx", "Sheet1") == "Sheet1"


def test_warn_unmapped_columns_logs_when_any(caplog):
    df = pd.DataFrame({"A": [1], "B": [2]})
    caplog.set_level(logging.INFO, logger="ASF-SCHEDULER")
    _warn_unmapped_columns(df, {"A": "A_STD"}, context="Vols")
    assert any("[UNMAPPED Vols]" in message for message in caplog.messages)


def test_load_and_normalize_returns_empty_and_warns_when_read_fails(monkeypatch):
    monkeypatch.setattr(
        "loaders.universal_loader.pd.read_excel",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("boom")),
    )
    warns: list[str] = []
    monkeypatch.setattr(ul, "warn_ui", lambda message: warns.append(message))

    out = load_and_normalize("dummy.xlsx", "Sheet1", {"A": "ColA"}, header=0)
    assert out.empty
    assert warns


def test_load_and_normalize_drops_unnamed_ignores_columns_and_normalizes_phone(monkeypatch):
    monkeypatch.setattr(
        "loaders.universal_loader.pd.read_excel",
        lambda *_args, **_kwargs: pd.DataFrame(
            {
                "Unnamed: 0": [1],
                "PHONE": [33612345678],
                "DROP": ["x"],
            }
        ),
    )
    mapping = {
        "PHONE": "Telephone",
        "DROP": "_IGNORE_DROP",
        "MISSING": "ColB",
    }

    out = load_and_normalize("dummy.xlsx", "Sheet1", mapping, header=0)
    assert "Unnamed: 0" not in out.columns
    assert "_IGNORE_DROP" not in out.columns
    assert "Telephone" in out.columns
    assert out.loc[0, "Telephone"] == "33612345678"
    assert "ColB" in out.columns


def test_resolve_sheet_name_exact_match_and_no_candidate(monkeypatch):
    class _Book:
        sheet_names = [" ParamDest ", "Other"]

    monkeypatch.setattr("loaders.universal_loader.pd.ExcelFile", lambda *_args, **_kwargs: _Book())
    assert _resolve_sheet_name("dummy.xlsx", "paramdest") == " ParamDest "
    assert _resolve_sheet_name("dummy.xlsx", "UnknownSheet") == "UnknownSheet"


def test_normalize_header_returns_empty_for_non_string():
    assert normalize_header(123) == ""
    assert normalize_header(None) == ""


def test_load_and_normalize_returns_empty_when_retry_on_resolved_sheet_fails(monkeypatch):
    monkeypatch.setattr(
        "loaders.universal_loader.pd.read_excel",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("boom")),
    )
    monkeypatch.setattr("loaders.universal_loader._resolve_sheet_name", lambda *_a, **_k: "Resolved")
    warnings: list[str] = []
    monkeypatch.setattr(ul, "warn_ui", lambda message: warnings.append(str(message)))

    out = load_and_normalize("dummy.xlsx", "Missing", {"A": "ColA"}, header=0)
    assert out.empty
    assert warnings


def test_load_and_normalize_skips_none_targets(monkeypatch):
    monkeypatch.setattr(
        "loaders.universal_loader.pd.read_excel",
        lambda *_args, **_kwargs: pd.DataFrame({"A": [1], "B": [2]}),
    )
    out = load_and_normalize(
        "dummy.xlsx",
        "Sheet1",
        {
            "A": "KeepA",
            "B": None,
        },
        header=0,
    )
    assert "KeepA" in out.columns
    assert "B" in out.columns
