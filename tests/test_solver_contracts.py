# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from scheduler.solver_ortools import (
    cp_model as cp_model_v2,
)
from scheduler.solver_ortools import (
    solve_planning_ortools_simulation as solve_v2,
)
from scheduler.solver_ortools_v3 import (
    cp_model as cp_model_v3,
)
from scheduler.solver_ortools_v3 import (
    solve_planning_ortools_simulation as solve_v3,
)
from utils.identifiers import normalize_be_number


class DummyDataSource:
    name = "dummy_contract"

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

    def load_shipments_df(
        self,
        param_be: pd.DataFrame | None = None,
        *,
        planifiables_only: bool = True,
    ) -> pd.DataFrame:
        return self._df_be

    def load_vols_df(self, param_dest: pd.DataFrame | None = None) -> pd.DataFrame:
        return self._df_vols

    def load_benevoles_df(self, param_benev: pd.DataFrame | None = None) -> pd.DataFrame:
        return self._df_benev


def _make_contract_data_source() -> DummyDataSource:
    vol_date = dt.date(2025, 1, 1)

    df_param_be = pd.DataFrame(
        [
            {"Type": "MM", "Priorite_Type": 1, "Equiv": 1},
            {"Type": "AUTRE", "Priorite_Type": 99, "Equiv": 1},
        ]
    )
    df_param_dest = pd.DataFrame(
        [
            {"Dest_IATA": "RUN", "Max_Colis_Par_Vol": 25, "Freq_Semaine": 7},
        ]
    )
    df_param_benev = pd.DataFrame(
        [
            {
                "ID": 1,
                "Benevole": "Alice",
                "Nom": "DUPONT",
                "Prenom": "Alice",
                "Prenom_Court": "Alice",
                "Telephone": "0600000000",
                "Max_Colis_Vol": 30,
                "Max_Jours_Semaine": 7,
                "Max_Exp_Semaine": 10,
                "Max_Exp_Jour": 5,
                "Attente_Max_Heures": 8,
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
        ]
    )
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
    df_benev = pd.DataFrame(
        [
            {
                "ID": 1,
                "Benevole": "Alice",
                "Date": vol_date,
                "Date_dt": pd.Timestamp(vol_date),
                "Heure_Arrivee": "07:00",
                "Heure_Depart": "12:00",
                "Heure_Arrivee_time": dt.time(7, 0),
                "Heure_Depart_time": dt.time(12, 0),
            }
        ]
    )
    return DummyDataSource(
        df_param_be=df_param_be,
        df_param_dest=df_param_dest,
        df_param_benev=df_param_benev,
        df_be=df_be,
        df_vols=df_vols,
        df_benev=df_benev,
    )


def _make_same_physical_flight_conflict_data_source() -> DummyDataSource:
    vol_date = dt.date(2025, 1, 2)

    df_param_be = pd.DataFrame(
        [
            {"Type": "MM", "Priorite_Type": 1, "Equiv": 1},
            {"Type": "AUTRE", "Priorite_Type": 99, "Equiv": 1},
        ]
    )
    df_param_dest = pd.DataFrame(
        [
            {"Dest_IATA": "NKC", "Max_Colis_Par_Vol": 25, "Freq_Semaine": 7},
            {"Dest_IATA": "CKY", "Max_Colis_Par_Vol": 25, "Freq_Semaine": 7},
        ]
    )
    df_param_benev = pd.DataFrame(
        [
            {
                "ID": 1,
                "Benevole": "Alice",
                "Nom": "DUPONT",
                "Prenom": "Alice",
                "Prenom_Court": "Alice",
                "Telephone": "0600000000",
                "Max_Colis_Vol": 30,
                "Max_Jours_Semaine": 7,
                "Max_Exp_Semaine": 10,
                "Max_Exp_Jour": 5,
                "Attente_Max_Heures": 8,
            }
        ]
    )
    df_be = pd.DataFrame(
        [
            {
                "BE_Numero": "BE_NKC_001",
                "Destination": "NKC",
                "BE_Nb_Colis": 10,
                "Equiv_Colis": 10,
                "Priorite": 1,
                "BE_Type": "MM",
                "BE_Expediteur": "ASF",
                "BE_Destinataire": "Hopital",
            },
            {
                # Plus de colis côté CKY pour vérifier que la priorité routing prime sur l'objectif poids.
                "BE_Numero": "BE_CKY_001",
                "Destination": "CKY",
                "BE_Nb_Colis": 20,
                "Equiv_Colis": 20,
                "Priorite": 1,
                "BE_Type": "MM",
                "BE_Expediteur": "ASF",
                "BE_Destinataire": "Hopital",
            },
        ]
    )
    df_vols = pd.DataFrame(
        [
            {
                "Date_Vol": vol_date,
                "Heure_Vol": "10:00",
                "IATA": "NKC",
                "Destination": "NKC",
                "Numero_Vol": "AF1234",
                "Routing": "CDG-NKC-CKY",
                "Route_Pos": 1,
            },
            {
                "Date_Vol": vol_date,
                "Heure_Vol": "10:00",
                "IATA": "CKY",
                "Destination": "CKY",
                "Numero_Vol": "AF1234",
                "Routing": "CDG-NKC-CKY",
                "Route_Pos": 2,
            },
        ]
    )
    df_benev = pd.DataFrame(
        [
            {
                "ID": 1,
                "Benevole": "Alice",
                "Date": vol_date,
                "Date_dt": pd.Timestamp(vol_date),
                "Heure_Arrivee": "00:00",
                "Heure_Depart": "23:59",
                "Heure_Arrivee_time": dt.time(0, 0),
                "Heure_Depart_time": dt.time(23, 59),
            }
        ]
    )
    return DummyDataSource(
        df_param_be=df_param_be,
        df_param_dest=df_param_dest,
        df_param_benev=df_param_benev,
        df_be=df_be,
        df_vols=df_vols,
        df_benev=df_benev,
    )


def _make_same_physical_flight_only_second_destination_data_source() -> DummyDataSource:
    ds = _make_same_physical_flight_conflict_data_source()
    ds._df_be = ds._df_be[ds._df_be["Destination"] == "CKY"].copy()
    return ds


def _make_same_physical_flight_conflict_without_route_pos_data_source() -> DummyDataSource:
    ds = _make_same_physical_flight_conflict_data_source()
    ds._df_vols = ds._df_vols.drop(columns=["Route_Pos"])
    return ds


def _make_missing_paramdest_stop_data_source() -> DummyDataSource:
    df_param_be = pd.DataFrame(
        [
            {"Type": "MM", "Priorite_Type": 1, "Equiv": 1},
            {"Type": "AUTRE", "Priorite_Type": 99, "Equiv": 1},
        ]
    )
    df_param_dest = pd.DataFrame(
        [
            {"Dest_IATA": "DLA", "Max_Colis_Par_Vol": 20, "Freq_Semaine": 7},
        ]
    )
    df_param_benev = pd.DataFrame(
        [
            {
                "ID": 1,
                "Benevole": "Philippe",
                "Nom": "TEST",
                "Prenom": "Philippe",
                "Prenom_Court": "Phil",
                "Telephone": "0600000000",
                "Max_Colis_Vol": 30,
                "Max_Jours_Semaine": 7,
                "Max_Exp_Semaine": 10,
                "Max_Exp_Jour": 5,
                "Attente_Max_Heures": 8,
            }
        ]
    )
    df_be = pd.DataFrame(
        [
            {
                "BE_Numero": "BE_DLA_001",
                "Destination": "DLA",
                "BE_Nb_Colis": 20,
                "Equiv_Colis": 20,
                "Priorite": 1,
                "BE_Type": "MM",
                "BE_Expediteur": "ASF",
                "BE_Destinataire": "Hopital",
            },
            {
                "BE_Numero": "BE_DLA_002",
                "Destination": "DLA",
                "BE_Nb_Colis": 20,
                "Equiv_Colis": 20,
                "Priorite": 1,
                "BE_Type": "MM",
                "BE_Expediteur": "ASF",
                "BE_Destinataire": "Hopital",
            },
            {
                "BE_Numero": "BE_DLA_003",
                "Destination": "DLA",
                "BE_Nb_Colis": 20,
                "Equiv_Colis": 20,
                "Priorite": 1,
                "BE_Type": "MM",
                "BE_Expediteur": "ASF",
                "BE_Destinataire": "Hopital",
            },
        ]
    )
    df_vols = pd.DataFrame(
        [
            {
                "Date_Vol": dt.date(2026, 1, 19),
                "Heure_Vol": "11:00",
                "IATA": "SSG",
                "Destination": "SSG",
                "Numero_Vol": "AF0652",
                "Routing": "CDG-SSG-DLA",
                "Route_Pos": 1,
            },
            {
                "Date_Vol": dt.date(2026, 1, 19),
                "Heure_Vol": "11:00",
                "IATA": "DLA",
                "Destination": "DLA",
                "Numero_Vol": "AF0652",
                "Routing": "CDG-SSG-DLA",
                "Route_Pos": 2,
            },
            {
                "Date_Vol": dt.date(2026, 1, 20),
                "Heure_Vol": "11:30",
                "IATA": "DLA",
                "Destination": "DLA",
                "Numero_Vol": "AF0653",
                "Routing": "CDG-DLA-SSG",
                "Route_Pos": 1,
            },
            {
                "Date_Vol": dt.date(2026, 1, 20),
                "Heure_Vol": "11:30",
                "IATA": "SSG",
                "Destination": "SSG",
                "Numero_Vol": "AF0653",
                "Routing": "CDG-DLA-SSG",
                "Route_Pos": 2,
            },
            {
                "Date_Vol": dt.date(2026, 1, 21),
                "Heure_Vol": "12:00",
                "IATA": "DLA",
                "Destination": "DLA",
                "Numero_Vol": "AF0654",
                "Routing": "CDG-DLA",
                "Route_Pos": 1,
            },
        ]
    )
    df_benev = pd.DataFrame(
        [
            {
                "ID": 1,
                "Benevole": "Philippe",
                "Date": dt.date(2026, 1, 19),
                "Date_dt": pd.Timestamp(dt.date(2026, 1, 19)),
                "Heure_Arrivee": "00:00",
                "Heure_Depart": "23:59",
                "Heure_Arrivee_time": dt.time(0, 0),
                "Heure_Depart_time": dt.time(23, 59),
            },
            {
                "ID": 1,
                "Benevole": "Philippe",
                "Date": dt.date(2026, 1, 20),
                "Date_dt": pd.Timestamp(dt.date(2026, 1, 20)),
                "Heure_Arrivee": "00:00",
                "Heure_Depart": "23:59",
                "Heure_Arrivee_time": dt.time(0, 0),
                "Heure_Depart_time": dt.time(23, 59),
            },
            {
                "ID": 1,
                "Benevole": "Philippe",
                "Date": dt.date(2026, 1, 21),
                "Date_dt": pd.Timestamp(dt.date(2026, 1, 21)),
                "Heure_Arrivee": "00:00",
                "Heure_Depart": "23:59",
                "Heure_Arrivee_time": dt.time(0, 0),
                "Heure_Depart_time": dt.time(23, 59),
            },
        ]
    )
    return DummyDataSource(
        df_param_be=df_param_be,
        df_param_dest=df_param_dest,
        df_param_benev=df_param_benev,
        df_be=df_be,
        df_vols=df_vols,
        df_benev=df_benev,
    )


def _assert_solver_contract(res: dict) -> None:
    status = str(res.get("status", ""))
    stats = res.get("statistiques", {}) or {}
    planning_df = res.get("planning_df", pd.DataFrame())
    bilan_df = res.get("bilan_df", pd.DataFrame())

    assert status in {"OPTIMAL", "FEASIBLE"}
    assert stats.get("status") == status
    assert isinstance(planning_df, pd.DataFrame)
    assert isinstance(bilan_df, pd.DataFrame)

    required_columns = {"Date_Vol", "Numero_Vol", "Destination", "BE_Numero", "Benevole", "ID"}
    assert required_columns.issubset(set(planning_df.columns))

    nb_be_total = int(stats.get("nb_be_total", 0) or 0)
    nb_be_envoyes = int(stats.get("nb_be_envoyes", 0) or 0)
    nb_colis_total = int(stats.get("nb_colis_total", 0) or 0)
    nb_colis_expedies = int(stats.get("nb_colis_expedies", 0) or 0)
    taux_be = float(stats.get("taux_be", 0) or 0)
    taux_colis = float(stats.get("taux_colis", 0) or 0)
    nb_vols_total = int(stats.get("nb_vols_total", 0) or 0)
    nb_vols_sans_be = int(stats.get("nb_vols_sans_be_compatible", 0) or 0)
    nb_vols_sans_benev = int(stats.get("nb_vols_sans_benevole_compatible", 0) or 0)
    nb_vols_sans_full = int(stats.get("nb_vols_sans_compatibilite_complete", 0) or 0)
    nb_vols_non_utilises_compat = int(stats.get("nb_vols_non_utilises_avec_compatibilite", 0) or 0)

    assert nb_be_total >= nb_be_envoyes >= 0
    assert nb_colis_total >= nb_colis_expedies >= 0
    assert 0 <= taux_be <= 100
    assert 0 <= taux_colis <= 100
    assert nb_vols_total >= 0
    assert nb_vols_total >= nb_vols_sans_be >= 0
    assert nb_vols_total >= nb_vols_sans_benev >= 0
    assert nb_vols_total >= nb_vols_sans_full >= 0
    assert nb_vols_total >= nb_vols_non_utilises_compat >= 0

    diag_df = res.get("vols_diagnostics", pd.DataFrame())
    assert isinstance(diag_df, pd.DataFrame)
    if not diag_df.empty:
        assert "BE_Compat_Count" in diag_df.columns
        assert "Benev_Compat_Count" in diag_df.columns
        assert "Used" in diag_df.columns


@pytest.mark.skipif(cp_model_v2 is None or cp_model_v3 is None, reason="OR-Tools non disponible")
def test_solver_v2_v3_contracts_on_fixed_dataset():
    ds = _make_contract_data_source()

    res_v2 = solve_v2(timeout_seconds=5, data_source=ds, priority_mode="colis")
    res_v3 = solve_v3(timeout_seconds=5, data_source=ds, priority_mode="colis")

    _assert_solver_contract(res_v2)
    _assert_solver_contract(res_v3)

    be_v2 = set(res_v2.get("planning_df", pd.DataFrame()).get("BE_Numero", pd.Series(dtype=str)).astype(str))
    be_v3 = set(res_v3.get("planning_df", pd.DataFrame()).get("BE_Numero", pd.Series(dtype=str)).astype(str))
    expected = {normalize_be_number("BE_RUN_001"), normalize_be_number("BE_RUN_002")}
    assert be_v2 == expected
    assert be_v3 == expected


@pytest.mark.skipif(cp_model_v2 is None or cp_model_v3 is None, reason="OR-Tools non disponible")
def test_solver_v2_v3_dry_run_contract_is_consistent():
    ds = _make_contract_data_source()

    res_v2 = solve_v2(timeout_seconds=5, data_source=ds, priority_mode="colis", dry_run=True)
    res_v3 = solve_v3(timeout_seconds=5, data_source=ds, priority_mode="colis", dry_run=True)

    for res in (res_v2, res_v3):
        assert res.get("status") == "DRY_RUN"
        stats = res.get("statistiques", {})
        assert stats.get("status") == "DRY_RUN"
        assert int(stats.get("nb_be", 0)) == 2
        assert int(stats.get("nb_vols", 0)) >= 1
        assert int(stats.get("nb_benevoles", 0)) >= 1


@pytest.mark.skipif(cp_model_v2 is None or cp_model_v3 is None, reason="OR-Tools non disponible")
def test_solver_v2_v3_conflict_prefers_first_destination_in_routing():
    ds = _make_same_physical_flight_conflict_data_source()

    res_v2 = solve_v2(timeout_seconds=5, data_source=ds, priority_mode="colis")
    res_v3 = solve_v3(timeout_seconds=5, data_source=ds, priority_mode="colis")

    for res in (res_v2, res_v3):
        assert str(res.get("status", "")) in {"OPTIMAL", "FEASIBLE"}
        stats = res.get("statistiques", {}) or {}
        assert int(stats.get("nb_be_envoyes", 0)) == 1

        planning_df = res.get("planning_df", pd.DataFrame())
        assert not planning_df.empty
        assert set(planning_df["Destination"].astype(str).str.upper()) == {"NKC"}
        assert len(set(planning_df["BE_Numero"].astype(str))) == 1


@pytest.mark.skipif(cp_model_v2 is None or cp_model_v3 is None, reason="OR-Tools non disponible")
def test_solver_v2_v3_conflict_prefers_first_destination_without_explicit_route_pos():
    ds = _make_same_physical_flight_conflict_without_route_pos_data_source()

    res_v2 = solve_v2(timeout_seconds=5, data_source=ds, priority_mode="colis")
    res_v3 = solve_v3(timeout_seconds=5, data_source=ds, priority_mode="colis")

    for res in (res_v2, res_v3):
        assert str(res.get("status", "")) in {"OPTIMAL", "FEASIBLE"}
        planning_df = res.get("planning_df", pd.DataFrame())
        assert not planning_df.empty
        assert set(planning_df["Destination"].astype(str).str.upper()) == {"NKC"}


@pytest.mark.skipif(cp_model_v2 is None or cp_model_v3 is None, reason="OR-Tools non disponible")
def test_solver_v2_v3_uses_second_destination_when_no_conflict():
    ds = _make_same_physical_flight_only_second_destination_data_source()

    res_v2 = solve_v2(timeout_seconds=5, data_source=ds, priority_mode="colis")
    res_v3 = solve_v3(timeout_seconds=5, data_source=ds, priority_mode="colis")

    for res in (res_v2, res_v3):
        assert str(res.get("status", "")) in {"OPTIMAL", "FEASIBLE"}
        stats = res.get("statistiques", {}) or {}
        assert int(stats.get("nb_be_envoyes", 0)) == 1

        planning_df = res.get("planning_df", pd.DataFrame())
        assert not planning_df.empty
        assert set(planning_df["Destination"].astype(str).str.upper()) == {"CKY"}
        assert len(set(planning_df["BE_Numero"].astype(str))) == 1


@pytest.mark.skipif(cp_model_v2 is None or cp_model_v3 is None, reason="OR-Tools non disponible")
def test_solver_v2_v3_multistop_with_unknown_intermediate_stop_keeps_final_destination():
    ds = _make_missing_paramdest_stop_data_source()

    res_v2 = solve_v2(timeout_seconds=5, data_source=ds, priority_mode="colis")
    res_v3 = solve_v3(timeout_seconds=5, data_source=ds, priority_mode="colis")

    for res in (res_v2, res_v3):
        assert str(res.get("status", "")) in {"OPTIMAL", "FEASIBLE"}
        stats = res.get("statistiques", {}) or {}
        assert int(stats.get("nb_be_envoyes", 0)) == 3

        planning_df = res.get("planning_df", pd.DataFrame())
        assert not planning_df.empty
        assert set(planning_df["Destination"].astype(str).str.upper()) == {"DLA"}
        assert len(set(planning_df["BE_Numero"].astype(str))) == 3
