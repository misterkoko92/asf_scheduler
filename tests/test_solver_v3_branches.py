# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

import scheduler.solver_ortools_v3 as s3


class _DataSource:
    name = "dummy_v3_branches"

    def __init__(
        self,
        *,
        df_param_be: pd.DataFrame | None = None,
        df_param_dest: pd.DataFrame | None = None,
        df_param_benev: pd.DataFrame | None = None,
        df_be: pd.DataFrame | None = None,
        df_vols: pd.DataFrame | None = None,
        df_benev: pd.DataFrame | None = None,
    ):
        self._df_param_be = df_param_be if df_param_be is not None else pd.DataFrame([{"Type": "MM", "Priorite_Type": 1}])
        self._df_param_dest = df_param_dest if df_param_dest is not None else pd.DataFrame([{"Dest_IATA": "RUN"}])
        self._df_param_benev = df_param_benev if df_param_benev is not None else pd.DataFrame([{"ID": 1, "Benevole": "Alice"}])
        self._df_be = df_be if df_be is not None else pd.DataFrame([{"BE_Numero": "BE1", "Destination": "RUN"}])
        self._df_vols = df_vols if df_vols is not None else pd.DataFrame(
            [{"Date_Vol": dt.date(2026, 1, 20), "Heure_Vol": "10:00", "IATA": "RUN", "Numero_Vol": "AF001"}]
        )
        self._df_benev = df_benev if df_benev is not None else pd.DataFrame(
            [{"ID": 1, "Date_dt": pd.Timestamp("2026-01-20"), "Heure_Arrivee_time": dt.time(9, 0), "Heure_Depart_time": dt.time(12, 0)}]
        )

    def load_param_be(self) -> pd.DataFrame:
        return self._df_param_be

    def load_param_dest(self) -> pd.DataFrame:
        return self._df_param_dest

    def load_param_benev(self) -> pd.DataFrame:
        return self._df_param_benev

    def load_shipments_df(self, _param_be=None, *, planifiables_only: bool = True) -> pd.DataFrame:
        _ = planifiables_only
        return self._df_be

    def load_vols_df(self, _param_dest=None) -> pd.DataFrame:
        return self._df_vols

    def load_benevoles_df(self, _param_benev=None) -> pd.DataFrame:
        return self._df_benev


def _patch_valid_pipeline(monkeypatch):
    monkeypatch.setattr(s3, "_validate_inputs", lambda *_a, **_k: [])
    monkeypatch.setattr(s3, "_build_dest_info", lambda *_a, **_k: {})
    monkeypatch.setattr(
        s3,
        "_group_shipments",
        lambda *_a, **_k: pd.DataFrame(
            [{"BE_Numero": "BE1", "poids_total": 1, "type": "MM", "nb_colis": 1, "BE_Expediteur": "ASF", "BE_Destinataire": "HOP"}],
            index=[0],
        ),
    )
    monkeypatch.setattr(
        s3,
        "_parse_vols",
        lambda *_a, **_k: pd.DataFrame(
            [
                {
                    "Date_Vol": dt.date(2026, 1, 20),
                    "Heure_Vol": "10:00",
                    "Numero_Vol": "AF001",
                    "Destination": "RUN",
                    "dest_iata": "RUN",
                    "Routing": "CDG-RUN",
                    "datetime": pd.Timestamp("2026-01-20 10:00"),
                }
            ],
            index=[0],
        ),
    )
    monkeypatch.setattr(
        s3,
        "_parse_benevoles",
        lambda *_a, **_k: pd.DataFrame(
            [{"ID": 1, "date": dt.date(2026, 1, 20), "heure_debut": dt.time(9, 0), "heure_fin": dt.time(12, 0)}],
            index=[0],
        ),
    )


def test_solve_planning_ortools_wrapper_enriches_stats(monkeypatch):
    planning = pd.DataFrame([{"x": 1}])
    bilan = pd.DataFrame([{"y": 1}])
    monkeypatch.setattr(
        s3,
        "solve_planning_ortools_simulation",
        lambda **_k: {"planning_df": planning, "bilan_df": bilan, "statistiques": {"foo": 1}, "status": "OPTIMAL"},
    )
    out_planning, out_bilan, stats = s3.solve_planning_ortools(priority_mode="benevoles")
    assert out_planning is planning
    assert out_bilan is bilan
    assert stats["priority_mode"] == "benevoles"
    assert stats["status"] == "OPTIMAL"


def test_simulation_returns_ortools_missing_when_cp_model_is_none(monkeypatch):
    monkeypatch.setattr(s3, "cp_model", None)
    out = s3.solve_planning_ortools_simulation(data_source=_DataSource())
    assert out.get("status") == "ORTOOLS_MISSING"


def test_simulation_returns_empty_statuses_for_missing_data():
    assert s3.solve_planning_ortools_simulation(data_source=_DataSource(df_be=pd.DataFrame())).get("status") == "AUCUN_BE"
    assert s3.solve_planning_ortools_simulation(data_source=_DataSource(df_vols=pd.DataFrame())).get("status") == "AUCUN_VOL"
    assert s3.solve_planning_ortools_simulation(data_source=_DataSource(df_benev=pd.DataFrame())).get("status") == "AUCUN_BENEVOLE"


@pytest.mark.skipif(s3.cp_model is None, reason="OR-Tools non disponible")
def test_simulation_returns_data_error_when_validation_fails(monkeypatch):
    monkeypatch.setattr(s3, "_validate_inputs", lambda *_a, **_k: ["bad input"])
    out = s3.solve_planning_ortools_simulation(data_source=_DataSource())
    assert out.get("status") == "ERREUR_DONNEES"


@pytest.mark.skipif(s3.cp_model is None, reason="OR-Tools non disponible")
def test_simulation_dry_run_branch(monkeypatch):
    _patch_valid_pipeline(monkeypatch)
    out = s3.solve_planning_ortools_simulation(data_source=_DataSource(), dry_run=True)
    assert out.get("status") == "DRY_RUN"
    assert out.get("statistiques", {}).get("nb_be") == 1


@pytest.mark.skipif(s3.cp_model is None, reason="OR-Tools non disponible")
def test_simulation_returns_empty_status_when_parsed_frames_invalid(monkeypatch):
    _patch_valid_pipeline(monkeypatch)
    monkeypatch.setattr(s3, "_parse_vols", lambda *_a, **_k: pd.DataFrame())
    out_vol = s3.solve_planning_ortools_simulation(data_source=_DataSource())
    assert out_vol.get("status") == "AUCUN_VOL_VALIDE"

    _patch_valid_pipeline(monkeypatch)
    monkeypatch.setattr(s3, "_parse_benevoles", lambda *_a, **_k: pd.DataFrame())
    out_benev = s3.solve_planning_ortools_simulation(data_source=_DataSource())
    assert out_benev.get("status") == "AUCUN_BENEVOLE_VALIDE"


@pytest.mark.skipif(s3.cp_model is None, reason="OR-Tools non disponible")
def test_simulation_returns_no_assignment_possible_when_x_empty(monkeypatch):
    _patch_valid_pipeline(monkeypatch)
    monkeypatch.setattr(s3, "_create_be_variables", lambda *_a, **_k: {})
    out = s3.solve_planning_ortools_simulation(data_source=_DataSource())
    assert out.get("status") == "AUCUNE_AFFECTATION_POSSIBLE"


@pytest.mark.skipif(s3.cp_model is None, reason="OR-Tools non disponible")
def test_simulation_returns_infeasible_when_hierarchical_optimization_fails(monkeypatch):
    _patch_valid_pipeline(monkeypatch)
    monkeypatch.setattr(s3, "_create_be_variables", lambda model, *_a, **_k: {(0, 0): model.NewBoolVar("x_0_0")})
    monkeypatch.setattr(
        s3,
        "_create_benev_variables",
        lambda model, *_a, **_k: ({(1, 0): model.NewBoolVar("y_1_0")}, {1: [0]}, [0], [1]),
    )
    monkeypatch.setattr(
        s3,
        "_build_vols_compatibility_df",
        lambda *_a, **_k: pd.DataFrame(
            [{"Numero_Vol": "AF001", "Date_Vol": "20/01/26", "Heure_Vol": "10:00", "Dest_IATA": "RUN", "BE_Compat_Count": 1, "Benev_Compat_Count": 1}]
        ),
    )
    monkeypatch.setattr(
        s3,
        "_summarize_vols_compatibility",
        lambda *_a, **_k: {"nb_vols_total": 1, "nb_vols_sans_benevole_compatible": 0, "nb_vols_sans_be_compatible": 0},
    )
    monkeypatch.setattr(s3, "_create_assignment_variables", lambda *_a, **_k: {})
    monkeypatch.setattr(s3, "_build_benev_max_colis_map", lambda *_a, **_k: {1: 10})
    monkeypatch.setattr(s3, "_add_be_constraints", lambda *_a, **_k: None)
    monkeypatch.setattr(s3, "_add_benev_constraints", lambda *_a, **_k: None)
    monkeypatch.setattr(s3, "_add_assignment_constraints", lambda *_a, **_k: None)
    monkeypatch.setattr(s3, "_add_dest_constraints", lambda *_a, **_k: None)
    monkeypatch.setattr(s3, "_add_physical_flight_exclusivity_constraints", lambda *_a, **_k: None)
    monkeypatch.setattr(s3, "_add_physical_flight_routing_priority_constraints", lambda *_a, **_k: None)
    monkeypatch.setattr(s3, "_run_hierarchical_priority_optimization", lambda **_k: ("colis", None))
    out = s3.solve_planning_ortools_simulation(data_source=_DataSource())
    assert out.get("status") == "INFAISABLE"


def test_build_benev_max_colis_map_handles_missing_and_invalid_values():
    assert s3._build_benev_max_colis_map(pd.DataFrame()) == {}
    assert s3._build_benev_max_colis_map(pd.DataFrame([{"ID": 1}])) == {}
    out = s3._build_benev_max_colis_map(
        pd.DataFrame(
            [
                {"ID": 1, "Max_Colis_Vol": 12},
                {"ID": 2, "Max_Colis_Vol": 0},
                {"ID": "bad", "Max_Colis_Vol": 5},
                {"ID": 3, "Max_Colis_Vol": "nan"},
            ]
        )
    )
    assert out[1] == 12
    assert out[2] == s3.MAX_EQUIV_PER_VOLUNTEER
    assert out[3] == s3.MAX_EQUIV_PER_VOLUNTEER


def test_build_planning_bilan_v3_handles_empty_and_missing_benevole_fields():
    empty_plan, empty_bilan = s3._build_planning_bilan_v3(
        pd.DataFrame(),
        [],
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(),
    )
    assert empty_plan.empty
    assert empty_bilan.empty

    be_groups = pd.DataFrame(
        [{"BE_Numero": "BE1", "nb_colis": 2, "poids_total": 2, "type": "MM", "BE_Expediteur": "ASF", "BE_Destinataire": "HOP"}],
        index=[0],
    )
    df_vols = pd.DataFrame(
        [{"datetime": pd.Timestamp("2026-01-20 10:00"), "Date_Vol": dt.date(2026, 1, 20), "Heure_Vol": "10h00", "Numero_Vol": "AF001", "Destination": "RUN"}],
        index=[0],
    )
    df_param_benev = pd.DataFrame([{"ID": 1, "Benevole": None, "Telephone": None}, {"ID": "bad", "Benevole": "X"}])
    planning_df, bilan_df = s3._build_planning_bilan_v3(
        pd.DataFrame([{"Vol_Date": dt.date(2026, 1, 20), "Vol_Numero": "AF001", "Vol_Destination": "RUN", "BE_Numero": "BE1", "BE_Nb_Colis": 2, "BE_Poids_Equiv": 2}]),
        [{"BE_Index": 0, "Benevole_ID": 1, "Vol_Index": 0}],
        be_groups,
        df_vols,
        df_param_benev,
    )
    assert not planning_df.empty
    assert planning_df.iloc[0]["Benevole"] == "ID_1"
    assert planning_df.iloc[0]["Telephone"] == ""
    assert not bilan_df.empty


def test_build_planning_bilan_wrapper_delegates(monkeypatch):
    sentinel_plan = pd.DataFrame([{"x": 1}])
    sentinel_bilan = pd.DataFrame([{"y": 1}])
    monkeypatch.setattr(s3, "_core_build_planning_bilan", lambda *_a, **_k: (sentinel_plan, sentinel_bilan))
    out_plan, out_bilan = s3._build_planning_bilan(pd.DataFrame(), pd.DataFrame())
    assert out_plan is sentinel_plan
    assert out_bilan is sentinel_bilan
