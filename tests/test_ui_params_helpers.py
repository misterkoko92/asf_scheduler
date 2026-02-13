# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pandas as pd


def _ensure_yaml_stub() -> None:
    if "yaml" in sys.modules:
        return
    yaml_stub = types.ModuleType("yaml")
    yaml_stub.safe_load = lambda *args, **kwargs: {}
    yaml_stub.safe_dump = lambda *args, **kwargs: None
    sys.modules["yaml"] = yaml_stub


_ensure_yaml_stub()
ui_params = importlib.import_module("asf_app.ui.ui_params")


def test_load_param_df_uses_state_cache(monkeypatch):
    state = SimpleNamespace(df_param_dest=None)
    calls = {"count": 0}

    def _fake_load(path, sheet_name, mapping, header=0):
        calls["count"] += 1
        return pd.DataFrame([{"x": 1}])

    monkeypatch.setattr(ui_params, "load_normalized_sheet", _fake_load)

    df1 = ui_params.load_param_df(
        state,
        "df_param_dest",
        Path("tdb.xlsx"),
        "ParamDest",
        {},
        header=0,
    )
    df2 = ui_params.load_param_df(
        state,
        "df_param_dest",
        Path("tdb.xlsx"),
        "ParamDest",
        {},
        header=0,
    )

    assert calls["count"] == 1
    assert df1.equals(df2)
    assert len(state.df_param_dest) == 1


def test_reload_param_df_overwrites_state(monkeypatch):
    state = SimpleNamespace(df_param_be=pd.DataFrame([{"x": "old"}]))

    monkeypatch.setattr(
        ui_params,
        "load_normalized_sheet",
        lambda *args, **kwargs: pd.DataFrame([{"x": "new"}]),
    )

    out = ui_params.reload_param_df(
        state,
        "df_param_be",
        Path("tdb.xlsx"),
        "ParamBE",
        {},
        header=0,
    )

    assert out.iloc[0]["x"] == "new"
    assert state.df_param_be.iloc[0]["x"] == "new"


def test_write_excel_sheet_success(monkeypatch):
    called = {"ok": False}
    monkeypatch.setattr(
        ui_params,
        "save_excel_sheet",
        lambda path, sheet_name, df: called.__setitem__("ok", True),
    )

    ok = ui_params.write_excel_sheet(Path("x.xlsx"), "ParamDest", pd.DataFrame([{"a": 1}]))

    assert ok is True
    assert called["ok"] is True


def test_write_excel_sheet_error(monkeypatch):
    errors: list[str] = []

    def _raise(*args, **kwargs):
        raise OSError("disk error")

    monkeypatch.setattr(ui_params, "save_excel_sheet", _raise)
    monkeypatch.setattr(ui_params.st, "error", lambda msg: errors.append(str(msg)))

    ok = ui_params.write_excel_sheet(Path("x.xlsx"), "ParamDest", pd.DataFrame([{"a": 1}]))

    assert ok is False
    assert errors and "Erreur écriture Excel" in errors[0]
