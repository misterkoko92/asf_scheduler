# -*- coding: utf-8 -*-
from __future__ import annotations

import pandas as pd
import pytest

import scheduler.config_paths as cp
from scheduler import be_manager


def test_load_param_be_logs_and_preserves_business_data(sample_onedrive, caplog):
    be_manager.reset_param_be_cache()
    caplog.set_level("INFO", logger="ASF-SCHEDULER")

    param_be = be_manager.load_param_be(use_cache=False, tdb_path=cp.TABLEAU_DE_BORD)

    assert param_be["MM"]["Priorite_Type"] == 3
    assert param_be["MM"]["Equiv"] == 2
    assert "=== PARAM_BE : Chargement ===" in caplog.text
    assert "Types manquants" in caplog.text
    assert "ParamBE semble incomplet" in caplog.text


def test_load_param_be_uses_cache(monkeypatch):
    be_manager.reset_param_be_cache()
    calls = {"count": 0}

    def _fake_load_and_normalize(**_kwargs):
        calls["count"] += 1
        return pd.DataFrame(
            [
                {"Type": "MM", "Priorite_Type": 3, "Equiv": 2},
                {"Type": "AUTRE", "Priorite_Type": 99, "Equiv": 1},
            ]
        )

    monkeypatch.setattr(be_manager, "load_and_normalize", _fake_load_and_normalize)

    first = be_manager.load_param_be(use_cache=True)
    second = be_manager.load_param_be(use_cache=True)

    assert calls["count"] == 1
    assert first is second


def test_normalize_param_be_falls_back_on_invalid_numeric_values():
    df = pd.DataFrame(
        [
            {"Type": "MM", "Priorite_Type": "abc", "Equiv": "oops"},
        ]
    )
    out = be_manager.normalize_param_be(df)
    assert out["MM"]["Priorite_Type"] == 99
    assert out["MM"]["Equiv"] == 1
    assert out["AUTRE"]["Priorite_Type"] == 99


def test_normalize_param_be_accepts_dict_and_normalizes_keys():
    out = be_manager.normalize_param_be(
        {
            " mm ": {"priorite_type": "4", "equiv": "2"},
            "cn": {"Priorite_Type": "x", "Equiv": None},
            "bad": "not-a-dict",
        }
    )
    assert out["MM"]["Priorite_Type"] == 4
    assert out["MM"]["Equiv"] == 2
    assert out["CN"]["Priorite_Type"] == 99
    assert out["CN"]["Equiv"] == 1
    assert out["BAD"]["Priorite_Type"] == 99
    assert out["BAD"]["Equiv"] == 1
    assert out["AUTRE"]["Priorite_Type"] == 99


def test_normalize_param_be_rejects_unsupported_input_type():
    with pytest.raises(TypeError):
        be_manager.normalize_param_be(["MM", "CN"])


def test_load_param_be_with_tdb_path_bypasses_cache(monkeypatch, tmp_path):
    be_manager.reset_param_be_cache()
    be_manager._PARAM_BE_CACHE = {"CACHED": {"Priorite_Type": 1, "Equiv": 1}}  # type: ignore[attr-defined]
    calls = {"count": 0}

    def _fake_load_and_normalize(**_kwargs):
        calls["count"] += 1
        return pd.DataFrame([{"Type": "MM", "Priorite_Type": 3, "Equiv": 2}])

    monkeypatch.setattr(be_manager, "load_and_normalize", _fake_load_and_normalize)

    out = be_manager.load_param_be(use_cache=True, tdb_path=tmp_path / "tdb.xlsx")
    assert calls["count"] == 1
    assert "MM" in out
    assert "CACHED" not in out


def test_reset_param_be_cache_sets_cache_to_none(monkeypatch):
    monkeypatch.setattr(
        be_manager,
        "_PARAM_BE_CACHE",
        {"MM": {"Priorite_Type": 3, "Equiv": 2}},
        raising=False,
    )
    be_manager.reset_param_be_cache()
    assert be_manager._PARAM_BE_CACHE is None  # type: ignore[attr-defined]
