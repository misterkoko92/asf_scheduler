# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

import scheduler.config_paths as cp
from asf_app.services.input_service import load_tdb, load_benev, load_vols


def test_load_tdb(sample_onedrive):
    data = load_tdb(cp.TABLEAU_DE_BORD)
    assert not data.df_be.empty
    assert not data.df_param_be.empty
    assert not data.df_param_dest.empty


def test_load_benev(sample_onedrive):
    data = load_benev(cp.PLANNING_BENEVOLES)
    assert not data.df_param_benev.empty
    assert not data.df_benev.empty


def test_load_vols(sample_onedrive):
    df = load_vols(cp.VOLS)
    assert not df.empty


def test_load_vols_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_vols(tmp_path / "missing.xlsx")


def test_load_vols_empty_file_returns_empty_df(tmp_path):
    path = tmp_path / "vols.xlsx"
    path.touch()
    df = load_vols(path)
    assert df.empty


def test_get_benev_source_message(tmp_path):
    from openpyxl import Workbook
    from asf_app.services.input_service import get_benev_source_message

    path = tmp_path / "benev.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Source"
    ws["D2"] = "27/01/2025"
    ws["E2"] = "10:30"
    wb.save(path)

    msg = get_benev_source_message(path)
    assert "27/01/25" in msg or "27/01/2025" in msg
    assert "10h30" in msg
