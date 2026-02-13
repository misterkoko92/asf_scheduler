# -*- coding: utf-8 -*-
from __future__ import annotations

import pandas as pd

from asf_app.services.files_service import pretty_mtime, read_excel_sheet, save_excel_sheet


def test_read_excel_sheet_fills_na(tmp_path):
    path = tmp_path / "test.xlsx"
    df = pd.DataFrame({"A": ["x", None], "B": [1, 2]})
    df.to_excel(path, sheet_name="Data", index=False)

    out = read_excel_sheet(path, "Data")
    assert out.iloc[1]["A"] == ""
    assert out.iloc[1]["B"] == "2"


def test_save_excel_sheet_fallback_openpyxl(tmp_path, monkeypatch):
    # Force Excel automation fallback to openpyxl
    import utils.excel_automation as ea

    monkeypatch.setattr(ea, "write_sheet_table", lambda *args, **kwargs: False)

    path = tmp_path / "test.xlsx"
    df_initial = pd.DataFrame({"A": ["a"], "B": ["b"]})
    df_initial.to_excel(path, sheet_name="Data", index=False)

    df_new = pd.DataFrame({"A": ["x"], "B": ["y"]})
    save_excel_sheet(path, "Data", df_new)

    out = pd.read_excel(path, sheet_name="Data")
    assert out.iloc[0]["A"] == "x"
    assert out.iloc[0]["B"] == "y"


def test_pretty_mtime_missing_file_returns_na(tmp_path):
    missing = tmp_path / "missing.xlsx"
    assert pretty_mtime(str(missing)) == "N/A"
