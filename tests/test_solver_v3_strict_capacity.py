# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from scheduler.solver_ortools_v3 import cp_model, solve_planning_ortools_simulation


class DummyDataSource:
    name = "dummy"

    def __init__(
        self,
        *,
        df_param_be: pd.DataFrame,
        df_param_dest: pd.DataFrame,
        df_param_benev: pd.DataFrame,
        df_be: pd.DataFrame,
        df_vols: pd.DataFrame,
        df_benev: pd.DataFrame,
    ):
        self._df_param_be = df_param_be
        self._df_param_dest = df_param_dest
        self._df_param_benev = df_param_benev
        self._df_be = df_be
        self._df_vols = df_vols
        self._df_benev = df_benev

    def is_available(self) -> bool:
        return True

    def load_param_be(self) -> pd.DataFrame:
        return self._df_param_be

    def load_param_dest(self) -> pd.DataFrame:
        return self._df_param_dest

    def load_param_benev(self) -> pd.DataFrame:
        return self._df_param_benev

    def load_shipments_df(self, param_be: pd.DataFrame | None = None, *, planifiables_only: bool = True) -> pd.DataFrame:
        return self._df_be

    def load_vols_df(self, param_dest: pd.DataFrame | None = None) -> pd.DataFrame:
        return self._df_vols

    def load_benevoles_df(self, param_benev: pd.DataFrame | None = None) -> pd.DataFrame:
        return self._df_benev


def _make_common_frames():
    df_param_be = pd.DataFrame(
        [
            {"Type": "MM", "Priorite_Type": 1, "Equiv": 1},
            {"Type": "AUTRE", "Priorite_Type": 99, "Equiv": 1},
        ]
    )
    df_param_dest = pd.DataFrame(
        [
            {
                "Dest_IATA": "RUN",
                "Max_Colis_Par_Vol": 40,
                "Freq_Semaine": 7,
            }
        ]
    )
    df_be = pd.DataFrame(
        [
            {
                "BE_Numero": "BE_RUN_001",
                "Destination": "RUN",
                "BE_Nb_Colis": 10,
                "Equiv_Colis": 10,
                "Priorite": 1,
                "BE_Type": "MM",
                "BE_Expediteur": "ASF",
                "BE_Destinataire": "Hopital",
            },
            {
                "BE_Numero": "BE_RUN_002",
                "Destination": "RUN",
                "BE_Nb_Colis": 10,
                "Equiv_Colis": 10,
                "Priorite": 1,
                "BE_Type": "MM",
                "BE_Expediteur": "ASF",
                "BE_Destinataire": "Hopital",
            },
            {
                "BE_Numero": "BE_RUN_003",
                "Destination": "RUN",
                "BE_Nb_Colis": 1,
                "Equiv_Colis": 1,
                "Priorite": 1,
                "BE_Type": "MM",
                "BE_Expediteur": "ASF",
                "BE_Destinataire": "Hopital",
            },
            {
                "BE_Numero": "BE_RUN_004",
                "Destination": "RUN",
                "BE_Nb_Colis": 8,
                "Equiv_Colis": 8,
                "Priorite": 1,
                "BE_Type": "MM",
                "BE_Expediteur": "ASF",
                "BE_Destinataire": "Hopital",
            },
        ]
    )
    vol_date = dt.date(2025, 1, 1)
    df_vols = pd.DataFrame(
        [
            {
                "Date_Vol": vol_date,
                "Heure_Vol": "10:00",
                "IATA": "RUN",
                "Destination": "RUN",
                "Numero_Vol": "AF1234",
                "Routing": "CDG-RUN",
            }
        ]
    )
    return df_param_be, df_param_dest, df_be, df_vols, vol_date


def _make_benev_frames(*, benevs: list[tuple[int, str, int]], vol_date: dt.date):
    param_rows = []
    dispo_rows = []
    for benev_id, benev_name, max_colis_vol in benevs:
        param_rows.append(
            {
                "ID": benev_id,
                "Benevole": benev_name,
                "Nom": "",
                "Prenom": "",
                "Prenom_Court": "",
                "Telephone": "0600000000",
                "Max_Colis_Vol": max_colis_vol,
                "Max_Jours_Semaine": 7,
                "Max_Exp_Semaine": 10,
                "Max_Exp_Jour": 5,
                "Attente_Max_Heures": 5,
            }
        )
        dispo_rows.append(
            {
                "ID": benev_id,
                "Benevole": benev_name,
                "Date": vol_date,
                "Date_dt": pd.Timestamp(vol_date),
                "Heure_Arrivee": "07:00",
                "Heure_Depart": "12:00",
                "Heure_Arrivee_time": dt.time(7, 0),
                "Heure_Depart_time": dt.time(12, 0),
            }
        )

    df_param_benev = pd.DataFrame(param_rows)
    df_benev = pd.DataFrame(dispo_rows)
    return df_param_benev, df_benev


@pytest.mark.skipif(cp_model is None, reason="OR-Tools non disponible")
def test_v3_blocks_benevole_over_capacity():
    df_param_be, df_param_dest, df_be, df_vols, vol_date = _make_common_frames()
    df_param_benev, df_benev = _make_benev_frames(
        benevs=[
            (1, "Philippe", 22),
            (3, "Nora", 6),
        ],
        vol_date=vol_date,
    )
    ds = DummyDataSource(
        df_param_be=df_param_be,
        df_param_dest=df_param_dest,
        df_param_benev=df_param_benev,
        df_be=df_be,
        df_vols=df_vols,
        df_benev=df_benev,
    )

    res = solve_planning_ortools_simulation(timeout_seconds=5, data_source=ds, priority_mode="colis")
    stats = res.get("statistiques", {})
    assert stats.get("status") in {"OPTIMAL", "FEASIBLE"}
    assert stats.get("nb_be_envoyes") == 3
    planning_df = res.get("planning_df", pd.DataFrame())
    assert not planning_df.empty
    assert len(planning_df) == 3
    assert "BE_RUN_004" not in planning_df["BE_Numero"].astype(str).tolist()
    assert planning_df["Benevole"].astype(str).str.contains("Philippe").all()


@pytest.mark.skipif(cp_model is None, reason="OR-Tools non disponible")
def test_v3_allows_benevole_with_higher_capacity():
    df_param_be, df_param_dest, df_be, df_vols, vol_date = _make_common_frames()
    df_param_benev, df_benev = _make_benev_frames(
        benevs=[
            (1, "Philippe", 22),
            (2, "Virginie", 30),
            (3, "Nora", 6),
        ],
        vol_date=vol_date,
    )
    ds = DummyDataSource(
        df_param_be=df_param_be,
        df_param_dest=df_param_dest,
        df_param_benev=df_param_benev,
        df_be=df_be,
        df_vols=df_vols,
        df_benev=df_benev,
    )

    res = solve_planning_ortools_simulation(timeout_seconds=5, data_source=ds, priority_mode="colis")
    stats = res.get("statistiques", {})
    assert stats.get("status") in {"OPTIMAL", "FEASIBLE"}
    assert stats.get("nb_be_envoyes") == 4
    planning_df = res.get("planning_df", pd.DataFrame())
    assert not planning_df.empty
    assert len(planning_df) == 4
    assert planning_df["Benevole"].astype(str).str.contains("Virginie").all()
