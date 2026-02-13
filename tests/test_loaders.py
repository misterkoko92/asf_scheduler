# -*- coding: utf-8 -*-
from __future__ import annotations

import logging

import pandas as pd

import loaders.load_benevoles as lb
import scheduler.config_paths as cp
from loaders.load_benevoles import load_benevoles
from loaders.load_params import load_param_be_from_path, load_param_dest_from_path
from loaders.load_shipments import load_shipments_df
from loaders.load_vols import load_vols, load_vols_df


def test_load_shipments_df_planifiables_only(sample_onedrive):
    param_be = load_param_be_from_path(cp.TABLEAU_DE_BORD)
    df = load_shipments_df(
        planifiables_only=True,
        tdb_path=cp.TABLEAU_DE_BORD,
        param_be_raw=param_be,
    )
    assert len(df) == 1
    assert df.loc[0, "Priorite"] == 3
    assert df.loc[0, "Equiv_Colis"] == 4
    assert df.loc[0, "BE_Numero"] == "25250001"


def test_load_benevoles_parses_hours(sample_onedrive):
    df = load_benevoles(planning_path=cp.PLANNING_BENEVOLES)
    assert len(df) == 1
    assert df.loc[0, "Heure_Arrivee"] == "06h00"
    assert df.loc[0, "Heure_Depart"] == "12h00"
    assert df.loc[0, "Heure_Arrivee_time"].hour == 6
    assert df.loc[0, "Heure_Depart_time"].hour == 12


def test_load_vols_routing_capacity(sample_onedrive):
    param_dest = load_param_dest_from_path(cp.TABLEAU_DE_BORD)
    vols = load_vols(vols_path=cp.VOLS, param_dest_df=param_dest)
    assert len(vols) == 1
    v = vols[0]
    assert v["max_colis_base"] == 10
    assert v["routing"] == ["CDG", "DLA"]


def test_load_vols_logs_summary(sample_onedrive, caplog):
    param_dest = load_param_dest_from_path(cp.TABLEAU_DE_BORD)
    with caplog.at_level(logging.INFO, logger="ASF-SCHEDULER"):
        load_vols(vols_path=cp.VOLS, param_dest_df=param_dest)
    assert any("Vols retenus" in msg for msg in caplog.messages)


def test_load_shipments_logs_summary(sample_onedrive, caplog):
    param_be = load_param_be_from_path(cp.TABLEAU_DE_BORD)
    with caplog.at_level(logging.INFO, logger="ASF-SCHEDULER"):
        load_shipments_df(
            planifiables_only=True,
            tdb_path=cp.TABLEAU_DE_BORD,
            param_be_raw=param_be,
        )
    assert any("load_shipments_df OK" in msg for msg in caplog.messages)


def test_load_param_dest_from_path(sample_onedrive):
    df = load_param_dest_from_path(cp.TABLEAU_DE_BORD)
    assert len(df) == 1
    assert df.loc[0, "Dest_IATA"] == "DLA"
    assert df.loc[0, "Freq_Mercredi"] == 1


def test_clear_benevoles_cache_ignores_clear_errors(monkeypatch):
    class _DummyCache:
        def clear(self):
            raise RuntimeError("boom")

    monkeypatch.setattr(lb, "_get_benevoles_cached", _DummyCache(), raising=False)

    lb.clear_benevoles_cache()


def test_load_vols_df_expands_multistop_routes_per_destination(tmp_path):
    vols_path = tmp_path / "Vols.xlsx"
    df_vols = pd.DataFrame(
        [
            {
                "PVOL_DATE": "19/01/2026",  # lundi
                "PVOL_HEURE": "11:00",
                "PVOL_NUMERO": "AF0652",
                "PVOL_ROUTE_API": "CDG, SSG, DLA",
            },
            {
                "PVOL_DATE": "20/01/2026",  # mardi
                "PVOL_HEURE": "11:30",
                "PVOL_NUMERO": "AF0653",
                "PVOL_ROUTE_API": "CDG, DLA, SSG",
            },
            {
                "PVOL_DATE": "21/01/2026",  # mercredi
                "PVOL_HEURE": "12:00",
                "PVOL_NUMERO": "AF0654",
                "PVOL_ROUTE_API": "CDG, DLA",
            },
        ]
    )
    with pd.ExcelWriter(vols_path) as writer:
        df_vols.to_excel(writer, sheet_name="Vols", index=False)

    df_param_dest = pd.DataFrame(
        [
            {
                "Dest_IATA": "DLA",
                "Dest_Ville": "DOUALA",
                "Max_Colis_Par_Vol": 20,
            }
        ]
    )

    df = load_vols_df(vols_path=vols_path, param_dest_df=df_param_dest)

    monday = df[df["Date_Vol"] == "19/01/26"].copy()
    tuesday = df[df["Date_Vol"] == "20/01/26"].copy()
    wednesday = df[df["Date_Vol"] == "21/01/26"].copy()

    assert set(monday["IATA"].astype(str)) == {"DLA", "SSG"}
    assert set(tuesday["IATA"].astype(str)) == {"DLA", "SSG"}
    assert set(wednesday["IATA"].astype(str)) == {"DLA"}

    monday_dla = monday[monday["IATA"] == "DLA"].iloc[0]
    monday_ssg = monday[monday["IATA"] == "SSG"].iloc[0]
    assert int(monday_dla["Max_Colis"]) == 20
    assert pd.isna(monday_ssg["Max_Colis"])
    assert monday_dla["Routing"] == "CDG-SSG-DLA"
    assert monday_ssg["Routing"] == "CDG-SSG-DLA"
    assert int(monday_dla["Route_Pos"]) == 2
    assert int(monday_ssg["Route_Pos"]) == 1
