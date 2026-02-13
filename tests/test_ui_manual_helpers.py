# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import pandas as pd

from asf_app.ui import ui_manual


def test_load_df_resets_index(monkeypatch):
    monkeypatch.setattr(
        ui_manual,
        "load_normalized_sheet",
        lambda **kwargs: pd.DataFrame([{"x": 1}], index=[5]),
    )

    out = ui_manual.load_df(Path("x.xlsx"), "Sheet1", {}, header=0)

    assert list(out.index) == [0]
    assert out.iloc[0]["x"] == 1


def test_write_excel_sheet_success(monkeypatch):
    called = {"ok": False}

    monkeypatch.setattr(
        ui_manual,
        "save_excel_sheet",
        lambda path, sheet_name, df: called.__setitem__("ok", True),
    )

    ok = ui_manual.write_excel_sheet(Path("x.xlsx"), "Sheet1", pd.DataFrame([{"a": 1}]))

    assert ok is True
    assert called["ok"] is True


def test_write_excel_sheet_error(monkeypatch):
    errors: list[str] = []

    def _raise(*args, **kwargs):
        raise OSError("disk error")

    monkeypatch.setattr(ui_manual, "save_excel_sheet", _raise)
    monkeypatch.setattr(ui_manual.st, "error", lambda msg: errors.append(str(msg)))

    ok = ui_manual.write_excel_sheet(Path("x.xlsx"), "Sheet1", pd.DataFrame([{"a": 1}]))

    assert ok is False
    assert errors and "Erreur écriture Excel" in errors[0]
