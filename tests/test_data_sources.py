# -*- coding: utf-8 -*-
from __future__ import annotations

from scheduler.data_sources import (
    ExcelDataSource,
    ExcelSourcePaths,
    AsfWmsDataSource,
    AsfBenevDataSource,
    CompositeDataSource,
    resolve_data_source,
)


def test_excel_data_source(sample_onedrive):
    paths = ExcelSourcePaths.from_defaults()
    source = ExcelDataSource(paths=paths)

    param_be = source.load_param_be()
    param_dest = source.load_param_dest()
    param_benev = source.load_param_benev()
    shipments = source.load_shipments_df(param_be)
    vols = source.load_vols_df(param_dest)
    benev = source.load_benevoles_df(param_benev)

    assert len(param_be) >= 1
    assert len(shipments) == 1
    assert len(vols) == 1
    assert len(benev) == 1


def test_excel_data_source_planifiables_only(sample_onedrive):
    paths = ExcelSourcePaths.from_defaults()
    source = ExcelDataSource(paths=paths)
    param_be = source.load_param_be()

    df_all = source.load_shipments_df(param_be, planifiables_only=False)
    df_planif = source.load_shipments_df(param_be, planifiables_only=True)

    assert len(df_all) == 2
    assert len(df_planif) == 1


def test_composite_data_source_fallback(sample_onedrive, tmp_path):
    base = ExcelDataSource(paths=ExcelSourcePaths.from_defaults())
    wms = AsfWmsDataSource(tmp_path, enabled=False)
    benev = AsfBenevDataSource(tmp_path, enabled=False)
    composite = CompositeDataSource(base=base, shipments_source=wms, volunteers_source=benev)

    shipments = composite.load_shipments_df()
    benev = composite.load_benevoles_df()

    assert len(shipments) == 1
    assert len(benev) == 1


def test_resolve_data_source_env(monkeypatch, sample_onedrive):
    monkeypatch.setenv("ASF_DATA_SOURCE", "excel")
    source = resolve_data_source()
    assert isinstance(source, ExcelDataSource)

    monkeypatch.setenv("ASF_DATA_SOURCE", "asf-wms")
    source = resolve_data_source()
    assert isinstance(source, AsfWmsDataSource)

    monkeypatch.setenv("ASF_DATA_SOURCE", "asf-benev")
    source = resolve_data_source()
    assert isinstance(source, AsfBenevDataSource)
