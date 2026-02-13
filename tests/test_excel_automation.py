# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime as dt
import sys
import types
from types import SimpleNamespace

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


def test_as_applescript_value_covers_primitives_and_strings():
    assert ea._as_applescript_value(True) == "true"
    assert ea._as_applescript_value(False) == "false"
    assert ea._as_applescript_value(12) == "12"
    assert ea._as_applescript_value("") == "\"\""
    assert ea._as_applescript_value("A\"B").startswith("\"")


def test_update_excel_cells_returns_true_when_all_values_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(ea.sys, "platform", "darwin")
    # Toutes les valeurs deviennent None => rien à appliquer => True
    out = ea.update_excel_cells(
        tmp_path / "dummy.xlsx",
        "Sheet1",
        [(1, 1, None), (2, 2, "")],
    )
    assert out is True


def test_write_sheet_table_returns_false_on_empty_data(monkeypatch, tmp_path):
    monkeypatch.setattr(ea.sys, "platform", "darwin")
    assert ea.write_sheet_table(tmp_path / "dummy.xlsx", "Sheet1", []) is False


def test_replace_sheet_table_unsupported_platform(monkeypatch, tmp_path):
    monkeypatch.setattr(ea.sys, "platform", "linux")
    out = ea.replace_sheet_table(tmp_path / "dummy.xlsx", "Sheet1", [["A"]])
    assert out is False


class _FakeCell:
    def __init__(self, ws, key):
        self._ws = ws
        self._key = key

    @property
    def Value(self):
        return self._ws.cells.get(self._key)

    @Value.setter
    def Value(self, value):
        self._ws.cells[self._key] = value


class _FakeRange:
    def __init__(self, ws):
        self._ws = ws

    @property
    def Value(self):
        return self._ws.range_value

    @Value.setter
    def Value(self, value):
        self._ws.range_value = value


class _FakeWorksheet:
    def __init__(self, name: str, collection):
        self.Name = name
        self._collection = collection
        self.cells: dict[tuple[int, int], object] = {}
        self.range_value: object = None
        self.cleared = False
        self.UsedRange = SimpleNamespace(ClearContents=self._clear_contents)

    def _clear_contents(self):
        self.cleared = True

    def Cells(self, row, col):
        return _FakeCell(self, (int(row), int(col)))

    def Range(self, _start, _end):
        return _FakeRange(self)

    def Delete(self):
        self._collection.delete(self.Name)


class _FakeWorksheets:
    def __init__(self, *, missing_name: str | None = None):
        self._sheets: dict[str, _FakeWorksheet] = {}
        self._missing_name = missing_name
        default = _FakeWorksheet("Sheet1", self)
        self._sheets["Sheet1"] = default
        self.last_added: _FakeWorksheet | None = None

    def __call__(self, name):
        if name in self._sheets and name != self._missing_name:
            return self._sheets[name]
        raise RuntimeError(f"sheet missing: {name}")

    def Add(self):
        ws = _FakeWorksheet(f"Sheet{len(self._sheets) + 1}", self)
        self._sheets[ws.Name] = ws
        self.last_added = ws
        return ws

    def delete(self, name: str):
        self._sheets.pop(name, None)


class _FakeWorkbook:
    def __init__(self, *, missing_name: str | None = None):
        self.Worksheets = _FakeWorksheets(missing_name=missing_name)
        self.saved = False
        self.closed = False

    def Save(self):
        self.saved = True

    def Close(self, SaveChanges=True):
        _ = SaveChanges
        self.closed = True


class _FakeWorkbooks:
    def __init__(self, *, missing_name: str | None = None):
        self._missing_name = missing_name
        self.last_workbook: _FakeWorkbook | None = None

    def Open(self, _path):
        wb = _FakeWorkbook(missing_name=self._missing_name)
        self.last_workbook = wb
        return wb


class _FakeExcel:
    def __init__(self, *, missing_name: str | None = None):
        self.DisplayAlerts = True
        self.Workbooks = _FakeWorkbooks(missing_name=missing_name)
        self.quit_called = False

    def Quit(self):
        self.quit_called = True


def _install_fake_win32(monkeypatch, *, missing_name: str | None = None):
    holder: dict[str, _FakeExcel] = {}

    def _dispatch(_name):
        excel = _FakeExcel(missing_name=missing_name)
        holder["excel"] = excel
        return excel

    win32_mod = types.ModuleType("win32com")
    client_mod = types.ModuleType("win32com.client")
    client_mod.Dispatch = _dispatch  # type: ignore[attr-defined]
    win32_mod.client = client_mod  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "win32com", win32_mod)
    monkeypatch.setitem(sys.modules, "win32com.client", client_mod)
    return holder


def test_update_excel_windows_success_with_fake_com(monkeypatch, tmp_path):
    holder = _install_fake_win32(monkeypatch)

    ok = ea._update_excel_windows(
        tmp_path / "dummy.xlsx",
        "Sheet1",
        [(1, 1, "A"), (2, 3, 42)],
    )

    assert ok is True
    wb = holder["excel"].Workbooks.last_workbook
    assert wb is not None
    ws = wb.Worksheets("Sheet1")
    assert ws.cells[(1, 1)] == "A"
    assert ws.cells[(2, 3)] == 42
    assert wb.saved is True
    assert wb.closed is True
    assert holder["excel"].quit_called is True


def test_write_table_windows_creates_missing_sheet(monkeypatch, tmp_path):
    holder = _install_fake_win32(monkeypatch, missing_name="Target")

    ok = ea._write_table_windows(
        tmp_path / "dummy.xlsx",
        "Target",
        [["A", "B"], ["C", "D"]],
        clear_contents=True,
    )

    assert ok is True
    wb = holder["excel"].Workbooks.last_workbook
    assert wb is not None
    ws = wb.Worksheets.last_added
    assert ws is not None
    assert ws.Name == "Target"
    assert ws.cleared is True
    assert ws.range_value == [["A", "B"], ["C", "D"]]


def test_update_excel_cells_routes_windows_and_write_sheet_routes_macos(monkeypatch, tmp_path):
    monkeypatch.setattr(ea.sys, "platform", "win32")
    monkeypatch.setattr(ea, "_update_excel_windows", lambda *_args, **_kwargs: True)
    assert ea.update_excel_cells(tmp_path / "a.xlsx", "Sheet1", [(1, 1, "x")]) is True

    monkeypatch.setattr(ea.sys, "platform", "darwin")
    monkeypatch.setattr(ea, "_write_table_macos", lambda *_args, **_kwargs: True)
    assert ea.write_sheet_table(tmp_path / "a.xlsx", "Sheet1", [["x"]]) is True


def test_update_excel_macos_and_write_table_macos_generate_script(monkeypatch, tmp_path):
    calls: list[str] = []

    class _Res:
        returncode = 0

    def _run(args, capture_output=True, text=True):
        _ = capture_output, text
        calls.append(str(args[-1]))
        return _Res()

    monkeypatch.setattr(ea.subprocess, "run", _run)

    ok_update = ea._update_excel_macos(
        tmp_path / "dummy.xlsx",
        "Feuille",
        [(1, 1, "A"), (2, 2, 12)],
    )
    ok_write = ea._write_table_macos(
        tmp_path / "dummy.xlsx",
        "Feuille",
        [["A", "B"]],
        clear_contents=False,
    )

    assert ok_update is True
    assert ok_write is True
    assert any('set value of range "A1" of ws to "A"' in script for script in calls)
    assert any('set value of range "B2" of ws to 12' in script for script in calls)
    assert any("clear contents of used range of ws" not in script for script in calls)


def test_replace_sheet_table_windows_and_macos(monkeypatch, tmp_path):
    holder = _install_fake_win32(monkeypatch)
    monkeypatch.setattr(ea.sys, "platform", "win32")
    assert ea.replace_sheet_table(tmp_path / "dummy.xlsx", "Sheet1", [["A"]]) is True
    wb = holder["excel"].Workbooks.last_workbook
    assert wb is not None
    assert wb.Worksheets.last_added is not None
    assert wb.Worksheets.last_added.range_value == [["A"]]

    scripts: list[str] = []

    class _Res:
        returncode = 0

    monkeypatch.setattr(ea.sys, "platform", "darwin")
    monkeypatch.setattr(
        ea.subprocess,
        "run",
        lambda args, capture_output=True, text=True: (scripts.append(str(args[-1])) or _Res()),
    )
    assert ea.replace_sheet_table(tmp_path / "dummy.xlsx", "SheetX", [["A", 1]]) is True
    assert scripts and 'delete worksheet "SheetX" of wb' in scripts[0]


def test_replace_sheet_table_windows_returns_false_on_dispatch_error(monkeypatch, tmp_path):
    def _dispatch_fail(_name):
        raise RuntimeError("boom")

    win32_mod = types.ModuleType("win32com")
    client_mod = types.ModuleType("win32com.client")
    client_mod.Dispatch = _dispatch_fail  # type: ignore[attr-defined]
    win32_mod.client = client_mod  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "win32com", win32_mod)
    monkeypatch.setitem(sys.modules, "win32com.client", client_mod)
    monkeypatch.setattr(ea.sys, "platform", "win32")

    assert ea.replace_sheet_table(tmp_path / "dummy.xlsx", "Sheet1", [["A"]]) is False
