# -*- coding: utf-8 -*-
from __future__ import annotations

import pandas as pd

import asf_app.services.files_service as fs


def test_pretty_mtime_success(tmp_path):
    path = tmp_path / "a.xlsx"
    path.write_text("x", encoding="utf-8")

    out = fs.pretty_mtime(str(path))

    assert out != "N/A"


def test_save_excel_sheet_creates_file_when_missing(tmp_path, monkeypatch):
    path = tmp_path / "new.xlsx"
    synced: list[str] = []
    monkeypatch.setattr(fs.cp, "sync_local_file_to_onedrive", lambda p: synced.append(str(p)))

    fs.save_excel_sheet(path, "Data", pd.DataFrame([{"A": "x"}]))

    assert path.exists()
    assert synced == [str(path)]
    out = pd.read_excel(path, sheet_name="Data")
    assert out.iloc[0]["A"] == "x"


def test_save_excel_sheet_uses_excel_automation_when_available(tmp_path, monkeypatch):
    import utils.excel_automation as ea

    path = tmp_path / "existing.xlsx"
    pd.DataFrame([{"A": "old"}]).to_excel(path, sheet_name="Data", index=False)
    synced: list[str] = []
    called = {"write": 0}
    monkeypatch.setattr(
        ea,
        "write_sheet_table",
        lambda *_args, **_kwargs: called.__setitem__("write", called["write"] + 1) or True,
    )
    monkeypatch.setattr(fs.cp, "sync_local_file_to_onedrive", lambda p: synced.append(str(p)))

    fs.save_excel_sheet(path, "Data", pd.DataFrame([{"A": "x"}]))

    assert called["write"] == 1
    assert synced == [str(path)]


def test_append_row_to_sheet_appends_known_columns_only(tmp_path, monkeypatch):
    path = tmp_path / "append.xlsx"
    pd.DataFrame([{"A": "x", "B": "y"}]).to_excel(path, sheet_name="Data", index=False)
    monkeypatch.setattr(fs.cp, "sync_local_file_to_onedrive", lambda _p: None)

    fs.append_row_to_sheet(path, "Data", {"A": "z", "C": "ignored"})

    out = pd.read_excel(path, sheet_name="Data").fillna("")
    assert len(out) == 2
    assert out.iloc[1]["A"] == "z"
    assert out.iloc[1]["B"] == ""
