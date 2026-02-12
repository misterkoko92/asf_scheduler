# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import date, datetime

import pandas as pd
from openpyxl import Workbook, load_workbook

import scheduler.config_paths as cp
import utils.excel_automation as excel_automation

from asf_app.services.export_service import (
    _apply_routing_fallback_from_vols,
    _alt_key_for_sheet,
    _build_bene_display_map,
    _find_mag_row,
    _friday_previous_week,
    _mag_lookup_keys,
    _create_minimal_workbook,
    _extract_version_from_planning_name,
    _format_bene_display,
    _normalize_vol_key,
    _safe_text,
    _sheet_order_for_be,
    _update_mag_central_dates_for_export,
    _week_year_from_ws_plan,
)


def test_create_minimal_workbook_has_expected_sheets(tmp_path):
    path = tmp_path / "minimal.xlsx"
    _create_minimal_workbook(path, week=3, year=2026)

    wb = load_workbook(path)
    assert wb.worksheets[0].title == "Planning SXX"
    assert wb.worksheets[0]["Q1"].value == 0
    assert "Export planning" in wb.sheetnames
    assert "Data Vols" in wb.sheetnames
    assert "Data Benevoles" in wb.sheetnames


def test_week_year_from_ws_plan_datetime_value():
    wb = Workbook()
    ws = wb.active
    ws["A1"] = datetime(2026, 1, 14, 10, 30)

    week, year = _week_year_from_ws_plan(ws, fallback_week=1, fallback_year=2025)
    assert (week, year) == (3, 2026)


def test_week_year_from_ws_plan_string_value():
    wb = Workbook()
    ws = wb.active
    ws["A1"] = "14/01/2026"

    week, year = _week_year_from_ws_plan(ws, fallback_week=1, fallback_year=2025)
    assert (week, year) == (3, 2026)


def test_week_year_from_ws_plan_invalid_fallback():
    wb = Workbook()
    ws = wb.active
    ws["A1"] = "not-a-date"

    week, year = _week_year_from_ws_plan(ws, fallback_week=5, fallback_year=2027)
    assert (week, year) == (5, 2027)


def test_extract_version_from_planning_name_new_format():
    name = "ASFmm - PLANNING SEMAINE 2026-05-03.xlsx"
    assert _extract_version_from_planning_name(name, week=5, year=2026) == 3


def test_extract_version_from_planning_name_legacy_with_v():
    name = "ASFmm - PLANNING SEMAINE No 05 - 2026 v7.xlsm"
    assert _extract_version_from_planning_name(name, week=5, year=2026) == 7


def test_extract_version_from_planning_name_legacy_without_v_defaults_to_1():
    name = "ASFmm - PLANNING SEMAINE No 05 - 2026.xlsx"
    assert _extract_version_from_planning_name(name, week=5, year=2026) == 1


def test_extract_version_from_planning_name_returns_none_for_other_week():
    name = "ASFmm - PLANNING SEMAINE 2026-05-03.xlsx"
    assert _extract_version_from_planning_name(name, week=6, year=2026) is None


def test_build_bene_display_map_and_format_bene_display():
    df_parambenev = pd.DataFrame(
        {
            "BENEVOLE": ["Alice Martin"],
            "Prenom court": ["A"],
            "Nom": ["Martin"],
        }
    )
    display_map = _build_bene_display_map(df_parambenev)

    assert display_map["Alice Martin"] == "A MARTIN"
    assert _format_bene_display("Alice Martin", display_map=display_map) == "A MARTIN"
    assert _format_bene_display("Bob Dupont", display_map=display_map) == "B. DUPONT"
    assert _format_bene_display("mono", display_map=display_map) == "MONO"


def test_normalize_vol_key_handles_af_prefix_and_digits():
    assert _normalize_vol_key("AF0652") == "652"
    assert _normalize_vol_key(" af 0652A ") == "652"
    assert _normalize_vol_key("KLM") == "KLM"
    assert _normalize_vol_key(None) == ""


def test_apply_routing_fallback_from_vols_fills_only_missing_routing():
    df_export = pd.DataFrame(
        {
            "DATE": [pd.Timestamp("2026-01-23"), pd.Timestamp("2026-01-23")],
            "Numero_Vol": ["AF0652", "AF0653"],
            "Routing": ["", "KEEP-ME"],
        }
    )
    df_vols = pd.DataFrame(
        {
            "Date_Vol": ["23/01/2026", "23/01/2026"],
            "Numero_Vol": ["652", "653"],
            "Routing": ["CDG-RUN", "CDG-FRA-RUN"],
        }
    )

    out = _apply_routing_fallback_from_vols(df_export, df_vols=df_vols)

    assert out.loc[0, "Routing"] == "CDG-RUN"
    assert out.loc[1, "Routing"] == "KEEP-ME"
    assert "_DATE_KEY" not in out.columns
    assert "_VOL_KEY" not in out.columns


def test_apply_routing_fallback_from_vols_creates_routing_column_when_absent():
    df_export = pd.DataFrame(
        {
            "DATE": [pd.Timestamp("2026-01-23")],
            "Numero_Vol": ["AF0652"],
        }
    )
    df_vols = pd.DataFrame(
        {
            "Date_Vol_dt": [pd.Timestamp("2026-01-23")],
            "Numero_Vol": ["652"],
            "Routing": ["CDG-RUN"],
        }
    )

    out = _apply_routing_fallback_from_vols(df_export, df_vols=df_vols)

    assert "Routing" in out.columns
    assert out.loc[0, "Routing"] == "CDG-RUN"


def test_mag_lookup_keys_includes_base_and_suffixes():
    keys = _mag_lookup_keys("000123")
    assert keys[0] == "000123"
    assert "123" in keys
    assert "0123" in keys


def test_alt_key_for_sheet_uses_year_suffix():
    assert _alt_key_for_sheet("000123", "MAG CENTRAL 2025") == "250123"
    assert _alt_key_for_sheet("250123", "MAG CENTRAL 2025") is None
    assert _alt_key_for_sheet("000123", "MAG CENTRAL") is None


def test_sheet_order_for_be_prefers_be_prefix_then_preferred_year():
    names = ["MAG CENTRAL 2024", "MAG CENTRAL 2026", "MAG CENTRAL 2025"]
    ordered = _sheet_order_for_be("250001", names, preferred_year=2026)
    assert ordered[0] == "MAG CENTRAL 2025"
    assert ordered[1] == "MAG CENTRAL 2026"
    assert set(ordered) == set(names)


def test_find_mag_row_uses_alt_key_when_needed():
    sheet = "MAG CENTRAL 2025"
    target_sheet, target_row = _find_mag_row(
        be_key="000123",
        mag_sheet_names=[sheet],
        mag_indexes={sheet: {"250123": 7}},
        preferred_year=2025,
    )
    assert target_sheet == sheet
    assert target_row == 7


def test_safe_text_handles_none_and_na():
    assert _safe_text(None) == ""
    assert _safe_text(pd.NA) == ""
    assert _safe_text("  x  ") == "x"


def test_update_mag_central_dates_for_export_missing_file(tmp_path):
    missing = tmp_path / "nope.xlsx"
    used_dates, method = _update_mag_central_dates_for_export(
        df_export=pd.DataFrame(),
        week=1,
        year=2026,
        tdb_source_path=missing,
    )
    assert used_dates == {}
    assert method == "missing"


def test_update_mag_central_dates_for_export_openpyxl_fallback(tmp_path, monkeypatch):
    path = tmp_path / "tdb.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "MAG CENTRAL 2026"
    ws["A1"] = "N° BE"
    ws["A2"] = "260001"
    wb.save(path)

    monkeypatch.setattr(cp, "sync_local_file_to_onedrive", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(excel_automation, "update_excel_cells", lambda *_args, **_kwargs: False)

    df_export = pd.DataFrame(
        [
            {
                "BE_KEY": "260001",
                "DATE": pd.Timestamp("2026-01-05"),
                "ID": "45.0",
                "BENEVOLE_DISP": "DUPONT",
                "VOL_AFF": "AF123",
                "HEURE_AFF": "11h30",
            }
        ]
    )
    used_dates, method = _update_mag_central_dates_for_export(
        df_export=df_export,
        week=1,
        year=2026,
        tdb_source_path=path,
    )

    assert method == "openpyxl"
    assert used_dates["260001"] == _friday_previous_week(1, 2026)

    wb2 = load_workbook(path)
    ws2 = wb2["MAG CENTRAL 2026"]

    depart_vol = ws2.cell(row=2, column=cp.MAG_CENTRAL_COL_DEPART_VOL).value
    depart_mag = ws2.cell(row=2, column=cp.MAG_CENTRAL_COL_DEPART_MAG).value
    if hasattr(depart_vol, "date"):
        depart_vol = depart_vol.date()
    if hasattr(depart_mag, "date"):
        depart_mag = depart_mag.date()

    assert depart_vol == date(2026, 1, 5)
    assert depart_mag == _friday_previous_week(1, 2026)
    assert ws2.cell(row=2, column=cp.MAG_CENTRAL_COL_ID_BENEV).value == "45"
    assert ws2.cell(row=2, column=cp.MAG_CENTRAL_COL_BENEV).value == "DUPONT"
    assert ws2.cell(row=2, column=cp.MAG_CENTRAL_COL_VOL).value == "AF123"
    assert ws2.cell(row=2, column=cp.MAG_CENTRAL_COL_HEURE).value == "11h30"
