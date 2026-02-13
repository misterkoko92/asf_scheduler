# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime as dt

import utils.excel_automation as ea


def test_coerce_excel_value_handles_to_pydatetime_error():
    class _BadTS:
        def to_pydatetime(self):
            raise TypeError("boom")

    bad = _BadTS()
    assert ea._coerce_excel_value(bad) is bad


def test_coerce_excel_value_date_conversion_fallback(monkeypatch):
    date_val = dt.date(2026, 1, 23)

    monkeypatch.setattr(ea, "to_excel", lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("boom")))
    assert ea._coerce_excel_value(date_val) == "2026-01-23"


def test_normalize_table_pads_rows_and_empty_values():
    out = ea._normalize_table([[1, None], [2]])
    assert out == [[1, ""], [2, ""]]


def test_update_excel_cells_unsupported_platform(monkeypatch, tmp_path):
    monkeypatch.setattr(ea.sys, "platform", "linux")
    result = ea.update_excel_cells(tmp_path / "dummy.xlsx", "Sheet1", [(1, 1, "x")])
    assert result is False


def test_write_sheet_table_unsupported_platform(monkeypatch, tmp_path):
    monkeypatch.setattr(ea.sys, "platform", "linux")
    result = ea.write_sheet_table(tmp_path / "dummy.xlsx", "Sheet1", [["A"]])
    assert result is False
