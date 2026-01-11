# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import utils.excel_automation as ea


def test_update_excel_cells_unsupported_platform(monkeypatch, tmp_path):
    monkeypatch.setattr(ea.sys, "platform", "linux")
    result = ea.update_excel_cells(tmp_path / "dummy.xlsx", "Sheet1", [(1, 1, "x")])
    assert result is False


def test_write_sheet_table_unsupported_platform(monkeypatch, tmp_path):
    monkeypatch.setattr(ea.sys, "platform", "linux")
    result = ea.write_sheet_table(tmp_path / "dummy.xlsx", "Sheet1", [["A"]])
    assert result is False
