# -*- coding: utf-8 -*-
from __future__ import annotations

from loaders.load_shipments import load_shipments_df
from loaders.load_benevoles import load_benevoles
from loaders.load_vols import load_vols
from loaders.load_params import load_param_be_from_path, load_param_dest_from_path
import scheduler.config_paths as cp


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


def test_load_param_dest_from_path(sample_onedrive):
    df = load_param_dest_from_path(cp.TABLEAU_DE_BORD)
    assert len(df) == 1
    assert df.loc[0, "Dest_IATA"] == "DLA"
    assert df.loc[0, "Freq_Mercredi"] == 1
