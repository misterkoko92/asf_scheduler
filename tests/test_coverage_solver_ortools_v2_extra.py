# -*- coding: utf-8 -*-
from __future__ import annotations

import pandas as pd

import scheduler.solver_ortools as s2


class _DataSourceBase:
    name = "test"

    def load_param_dest(self):
        return pd.DataFrame([{"Dest_IATA": "DLA", "Max_BE": 1, "Jours_Autorises": "LUNDI"}])

    def load_param_be(self):
        return pd.DataFrame([{"Type": "MM", "Priorite_Type": 1}])

    def load_param_benev(self):
        return pd.DataFrame([{"ID": 1}])

    def load_shipments_df(self, _df_param_be, *, planifiables_only=True):
        _ = planifiables_only
        return pd.DataFrame([{"BE_Numero": "260001", "Type": "MM", "Equiv_Colis": 1, "Destination": "DLA"}])

    def load_vols_df(self, _df_param_dest):
        return pd.DataFrame([{"Numero_Vol": "AF822", "Date_Vol": "16/02/26", "Heure_Vol": "11h00", "Dest_IATA": "DLA"}])

    def load_benevoles_df(self, _df_param_benev):
        return pd.DataFrame([{"ID": 1, "Date": "16/02/26", "Heure_Arrivee": "08:00", "Heure_Depart": "14:00"}])


class _NoBEDataSource(_DataSourceBase):
    def load_shipments_df(self, _df_param_be, *, planifiables_only=True):
        _ = planifiables_only
        return pd.DataFrame()


class _NoVolDataSource(_DataSourceBase):
    def load_vols_df(self, _df_param_dest):
        return pd.DataFrame()


class _NoBenevDataSource(_DataSourceBase):
    def load_benevoles_df(self, _df_param_benev):
        return pd.DataFrame()


def test_solver_returns_empty_result_when_ortools_missing(monkeypatch):
    monkeypatch.setattr(s2, "cp_model", None)

    out = s2.solve_planning_ortools_simulation(data_source=_DataSourceBase())

    assert out.get("status") == "ORTOOLS_MISSING"


def test_solver_returns_empty_results_for_missing_input_tables():
    assert s2.solve_planning_ortools_simulation(data_source=_NoBEDataSource()).get("status") == "AUCUN_BE"
    assert s2.solve_planning_ortools_simulation(data_source=_NoVolDataSource()).get("status") == "AUCUN_VOL"
    assert s2.solve_planning_ortools_simulation(data_source=_NoBenevDataSource()).get("status") == "AUCUN_BENEVOLE"


def test_solver_returns_data_error_when_validation_fails(monkeypatch):
    monkeypatch.setattr(s2, "_validate_inputs", lambda *_a, **_k: ["bad"])

    out = s2.solve_planning_ortools_simulation(data_source=_DataSourceBase())

    assert out.get("status") == "ERREUR_DONNEES"


def test_solver_returns_empty_when_parsed_inputs_are_invalid(monkeypatch):
    monkeypatch.setattr(s2, "_validate_inputs", lambda *_a, **_k: [])
    monkeypatch.setattr(s2, "_build_dest_info", lambda *_a, **_k: {"DLA": {}})
    monkeypatch.setattr(s2, "_group_shipments", lambda *_a, **_k: pd.DataFrame([{"BE_Numero": "260001"}], index=[0]))
    monkeypatch.setattr(s2, "_parse_vols", lambda *_a, **_k: pd.DataFrame())
    monkeypatch.setattr(s2, "_parse_benevoles", lambda *_a, **_k: pd.DataFrame([{"ID": 1}]))

    out_vol = s2.solve_planning_ortools_simulation(data_source=_DataSourceBase())
    assert out_vol.get("status") == "AUCUN_VOL_VALIDE"

    monkeypatch.setattr(s2, "_parse_vols", lambda *_a, **_k: pd.DataFrame([{"x": 1}], index=[0]))
    monkeypatch.setattr(s2, "_parse_benevoles", lambda *_a, **_k: pd.DataFrame())

    out_benev = s2.solve_planning_ortools_simulation(data_source=_DataSourceBase())
    assert out_benev.get("status") == "AUCUN_BENEVOLE_VALIDE"


def test_solver_returns_no_assignment_when_be_variables_are_empty(monkeypatch):
    monkeypatch.setattr(s2, "_validate_inputs", lambda *_a, **_k: [])
    monkeypatch.setattr(s2, "_build_dest_info", lambda *_a, **_k: {"DLA": {}})
    monkeypatch.setattr(s2, "_group_shipments", lambda *_a, **_k: pd.DataFrame([{"BE_Numero": "260001"}], index=[0]))
    monkeypatch.setattr(s2, "_parse_vols", lambda *_a, **_k: pd.DataFrame([{"x": 1}], index=[0]))
    monkeypatch.setattr(s2, "_parse_benevoles", lambda *_a, **_k: pd.DataFrame([{"ID": 1}], index=[0]))
    monkeypatch.setattr(s2, "_create_be_variables", lambda *_a, **_k: {})

    out = s2.solve_planning_ortools_simulation(data_source=_DataSourceBase())

    assert out.get("status") == "AUCUNE_AFFECTATION_POSSIBLE"


def test_solver_returns_infeasible_and_logs_be_without_option(monkeypatch):
    monkeypatch.setattr(s2, "_validate_inputs", lambda *_a, **_k: [])
    monkeypatch.setattr(s2, "_build_dest_info", lambda *_a, **_k: {"DLA": {}})
    monkeypatch.setattr(
        s2,
        "_group_shipments",
        lambda *_a, **_k: pd.DataFrame([{"BE_Numero": "260001"}], index=[0]),
    )
    monkeypatch.setattr(
        s2,
        "_parse_vols",
        lambda *_a, **_k: pd.DataFrame(
            [{"Numero_Vol": "AF822", "Date_Vol": "16/02/26", "Heure_Vol": "11h00", "Dest_IATA": "DLA"}],
            index=[0],
        ),
    )
    monkeypatch.setattr(
        s2,
        "_parse_benevoles",
        lambda *_a, **_k: pd.DataFrame([{"ID": 1}], index=[0]),
    )
    monkeypatch.setattr(s2, "_create_be_variables", lambda *_a, **_k: {(1, 0): object()})
    monkeypatch.setattr(s2, "_create_benev_variables", lambda *_a, **_k: ({}, {}, [], []))
    monkeypatch.setattr(
        s2,
        "_build_vols_compatibility_df",
        lambda *_a, **_k: pd.DataFrame(
            [{"Numero_Vol": "AF822", "Date_Vol": "16/02/26", "Heure_Vol": "11h00", "Dest_IATA": "DLA", "Benev_Compat_Count": 0, "BE_Compat_Count": 1}]
        ),
    )
    monkeypatch.setattr(
        s2,
        "_summarize_vols_compatibility",
        lambda *_a, **_k: {
            "nb_vols_sans_benevole_compatible": 0,
            "nb_vols_sans_be_compatible": 0,
            "nb_vols_total": 1,
        },
    )
    monkeypatch.setattr(s2, "_add_be_constraints", lambda *_a, **_k: None)
    monkeypatch.setattr(s2, "_add_physical_flight_routing_priority_constraints", lambda *_a, **_k: None)
    monkeypatch.setattr(s2, "_add_benev_constraints", lambda *_a, **_k: None)
    monkeypatch.setattr(s2, "_add_dest_constraints", lambda *_a, **_k: None)
    monkeypatch.setattr(s2, "_add_physical_flight_exclusivity_constraints", lambda *_a, **_k: None)
    monkeypatch.setattr(s2, "_run_hierarchical_priority_optimization", lambda *_a, **_k: ("colis", None))

    out = s2.solve_planning_ortools_simulation(data_source=_DataSourceBase())

    assert out.get("status") == "INFAISABLE"


def test_solver_v2_small_wrappers_delegate_to_common_helpers(monkeypatch):
    monkeypatch.setattr(s2, "_core_empty_result", lambda status: {"status": status})
    monkeypatch.setattr(s2, "_core_parse_time", lambda value: f"ok-{value}")

    assert s2._empty_result("X") == {"status": "X"}
    assert s2._parse_time("11:00") == "ok-11:00"
