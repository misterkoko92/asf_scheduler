# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

import scheduler.solver_ortools_common as sc


HAS_CP_MODEL = sc.cp_model is not None


def test_validate_inputs_and_build_dest_info_branches():
    errors_empty = sc.validate_inputs(pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
    assert "Aucun BE planifiable." in errors_empty
    assert "Aucun vol." in errors_empty
    assert "Aucune disponibilité bénévole." in errors_empty

    errors_missing = sc.validate_inputs(
        pd.DataFrame([{"BE_Numero": "250001"}]),
        pd.DataFrame([{"Date_Vol": "20/01/26"}]),
        pd.DataFrame([{"Date": "20/01/26"}]),
    )
    assert any("Vols : colonnes manquantes" in e for e in errors_missing)
    assert any("Bénévoles : colonnes manquantes" in e for e in errors_missing)

    dest_info = sc.build_dest_info(
        pd.DataFrame(
            [
                {"Dest_IATA": "", "Freq_Lundi": 1},
                {
                    "Dest_IATA": "RUN",
                    "Freq_Lundi": "ok",
                    "Max_Colis_Par_Vol": "bad",
                    "Freq_Semaine": "bad",
                },
                {
                    "Dest_IATA": "DLA",
                    "Max_Colis_Par_Vol": 0,
                    "Freq_Semaine": 0,
                },
            ]
        )
    )
    assert set(dest_info.keys()) == {"RUN", "DLA"}
    assert dest_info["RUN"]["max_colis"] == sc.MAX_CAPACITE_PAR_VOL
    assert dest_info["RUN"]["max_vols_semaine"] == 999
    assert dest_info["RUN"]["jours_autorises"] == [0]
    assert dest_info["DLA"]["max_colis"] == sc.MAX_CAPACITE_PAR_VOL
    assert dest_info["DLA"]["max_vols_semaine"] == 999


def test_parse_vols_handles_multiple_fallback_paths():
    df_raw = pd.DataFrame(
        [
            {"Date_Vol": "invalid", "Heure_Vol": "10:00", "Destination": "RUN", "Numero_Vol": "AF100", "route_pos": 1},
            {"Date_Vol": "20/01/26", "Heure_Vol": "", "Destination": "DLA", "Numero_Vol": "AF101", "route_pos": 2},
            {"Date_Vol": "20/01/26", "Heure_Vol": "11:00", "Destination": "RUN", "Numero_Vol": "", "route_pos": 1},
        ]
    )
    out = sc.parse_vols(df_raw, dest_info={})
    assert len(out) == 2
    assert list(out["dest_iata"]) == ["DLA", "RUN"]
    assert list(out["route_pos"]) == [2, 1]
    assert any("IDX" in key for key in out["physical_flight_key"].tolist())


def test_parse_vols_handles_date_conversion_failures(monkeypatch):
    df_raw = pd.DataFrame([{"Date_Vol": "20/01/26", "Heure_Vol": "10:00", "IATA": "RUN", "Numero_Vol": "AF100"}])

    monkeypatch.setattr(sc, "parse_date_value_as_date", lambda *_a, **_k: None)
    out_none = sc.parse_vols(df_raw, dest_info={})
    assert out_none.empty

    monkeypatch.setattr(sc, "parse_date_value_as_date", lambda *_a, **_k: (_ for _ in ()).throw(TypeError("boom")))
    out_exc = sc.parse_vols(df_raw, dest_info={})
    assert out_exc.empty


def test_parse_benevoles_without_preparsed_times_filters_invalid_rows():
    df_benev = pd.DataFrame(
        [
            {"ID": 1, "Date": "20/01/26", "Heure_Arrivee": "09:00", "Heure_Depart": "12:00"},
            {"ID": 2, "Date": "20/01/26", "Heure_Arrivee": "bad", "Heure_Depart": "12:00"},
        ]
    )
    df_param = pd.DataFrame(
        [
            {
                "ID": 1,
                "Max_Jours_Semaine": 2,
                "Max_Exp_Semaine": 3,
                "Max_Exp_Jour": 2,
                "Attente_Max_Heures": 4,
                "Benevole": "ALICE",
                "Nom": "DUPONT",
                "Prenom": "Alice",
                "Prenom_Court": "A.",
                "Telephone": "0600000000",
            },
            {
                "ID": 2,
                "Max_Jours_Semaine": 2,
                "Max_Exp_Semaine": 3,
                "Max_Exp_Jour": 2,
                "Attente_Max_Heures": 4,
                "Benevole": "BOB",
                "Nom": "MARTIN",
                "Prenom": "Bob",
                "Prenom_Court": "B.",
                "Telephone": "0611111111",
            },
        ]
    )
    out = sc.parse_benevoles(df_benev, df_param)
    assert len(out) == 1
    assert int(out.iloc[0]["ID"]) == 1


@pytest.mark.skipif(not HAS_CP_MODEL, reason="OR-Tools non disponible")
def test_create_variables_and_constraints_branch_paths(monkeypatch):
    model = sc.cp_model.CpModel()
    be_groups = pd.DataFrame([{"Destination": "RUN"}], index=[0])
    df_vols = pd.DataFrame(
        [
            {"dest_iata": "RUN", "datetime": pd.Timestamp("2026-01-19 10:00")},
            {"dest_iata": "RUN", "datetime": pd.Timestamp("2026-01-20 10:00")},
        ]
    )
    x = sc.create_be_variables(model, be_groups, df_vols, {"RUN": {"jours_autorises": [1]}})
    assert (0, 0) not in x
    assert (0, 1) in x

    df_benev = pd.DataFrame(
        [
            {
                "ID": 1,
                "date_obj": pd.Timestamp("2026-01-20"),
                "heure_debut": "bad",
                "heure_fin": "bad",
            }
        ]
    )
    y, benev_vols_compat, vols_with_benev, benev_ids = sc.create_benev_variables(model, df_benev, df_vols)
    assert y == {}
    assert benev_vols_compat == {}
    assert vols_with_benev == []
    assert benev_ids == [1]

    monkeypatch.setattr(sc, "MAX_BENEV_PER_VOL", 3)
    y2 = {(1, 0): model.NewBoolVar("y_1_0")}
    u = {0: model.NewBoolVar("u_0")}
    charge = {0: model.NewIntVar(0, 10, "charge_0")}
    nb_benev = {0: model.NewIntVar(0, 10, "nb_benev_0")}
    sc.add_benev_constraints(
        model,
        y2,
        u,
        charge,
        nb_benev,
        pd.DataFrame([{"datetime": pd.Timestamp("2026-01-20 10:00")}]),
        pd.DataFrame(
            [
                {"ID": 1, "Max_Exp_Semaine": 3, "Max_Exp_Jour": 2, "Max_Jours_Semaine": 2},
                {"ID": pd.NA, "Max_Exp_Semaine": 3, "Max_Exp_Jour": 2, "Max_Jours_Semaine": 2},
            ]
        ),
        {1: [0]},
        enforce_equiv_capacity=True,
    )

    u2 = {0: model.NewBoolVar("u_a"), 1: model.NewBoolVar("u_b")}
    df_excl = pd.DataFrame(
        [
            {"physical_flight_key": "", "route_pos": 1},
            {"physical_flight_key": "K1", "route_pos": 1},
        ]
    )
    sc.add_physical_flight_exclusivity_constraints(model, df_excl, u2)

    x2 = {(0, 0): model.NewBoolVar("x_0"), (1, 1): model.NewBoolVar("x_1")}
    df_priority = pd.DataFrame(
        [
            {"physical_flight_key": "K2", "route_pos": 1},
            {"physical_flight_key": "K2", "route_pos": 1},
        ]
    )
    sc.add_physical_flight_routing_priority_constraints(model, df_priority, x2, u2, [0, 1])


def test_summarize_and_build_planning_bilan_edge_cases():
    summary = sc.summarize_vols_compatibility(pd.DataFrame())
    assert summary["nb_vols_total"] == 0

    df_affectations = pd.DataFrame(
        [
            {
                "Vol_Index": 0,
                "BE_Numero": "260001",
                "BE_Nb_Colis": 2,
                "BE_Poids_Equiv": 2,
                "Vol_Date": "2026-01-20",
                "Vol_Numero": "AF001",
                "Vol_Destination": "RUN",
            }
        ]
    )
    df_planning_benev = pd.DataFrame([{"Vol_Index": 99, "Benevole_ID": 1, "Benevole": "A"}])
    planning_df, bilan_df = sc.build_planning_bilan(df_affectations, df_planning_benev)
    assert planning_df.empty
    assert not bilan_df.empty


@pytest.mark.skipif(not HAS_CP_MODEL, reason="OR-Tools non disponible")
def test_optimize_equilibrage_verbose_logs(monkeypatch):
    model = sc.cp_model.CpModel()
    y = {
        (1, 0): model.NewBoolVar("y_1_0"),
        (2, 0): model.NewBoolVar("y_2_0"),
    }
    df_param = pd.DataFrame([{"ID": 1}, {"ID": 2}])

    class _Solver:
        def Solve(self, _model):
            return sc.cp_model.OPTIMAL

        def ObjectiveValue(self):
            return 1

    class _Logger:
        def __init__(self):
            self.messages: list[str] = []

        def info(self, msg, *args):
            self.messages.append(str(msg % args))

    logger = _Logger()
    monkeypatch.setattr(sc, "get_logger", lambda *_a, **_k: logger)
    sc.optimize_equilibrage(model, _Solver(), y, df_param, verbose=True)
    assert any("Phase équilibre" in message for message in logger.messages)


@pytest.mark.skipif(not HAS_CP_MODEL, reason="OR-Tools non disponible")
@pytest.mark.parametrize(
    ("priority_mode", "statuses"),
    [
        ("invalid-mode", [sc.cp_model.INFEASIBLE]),
        ("colis", [sc.cp_model.OPTIMAL, sc.cp_model.INFEASIBLE]),
        ("colis", [sc.cp_model.OPTIMAL, sc.cp_model.OPTIMAL, sc.cp_model.INFEASIBLE]),
        ("benevoles", [sc.cp_model.INFEASIBLE]),
        ("benevoles", [sc.cp_model.OPTIMAL, sc.cp_model.INFEASIBLE]),
        ("benevoles", [sc.cp_model.OPTIMAL, sc.cp_model.OPTIMAL, sc.cp_model.INFEASIBLE]),
        (
            "colis",
            [
                sc.cp_model.OPTIMAL,
                sc.cp_model.OPTIMAL,
                sc.cp_model.OPTIMAL,
                sc.cp_model.INFEASIBLE,
                sc.cp_model.INFEASIBLE,
                sc.cp_model.INFEASIBLE,
            ],
        ),
    ],
)
def test_run_hierarchical_priority_optimization_failure_branches(priority_mode, statuses):
    model = sc.cp_model.CpModel()
    x = {(0, 0): model.NewBoolVar("x_0_0")}
    y = {(1, 0): model.NewBoolVar("y_1_0")}
    u = {0: model.NewBoolVar("u_0")}
    nb_benev = {0: model.NewIntVar(0, 5, "nb_0")}
    be_groups = pd.DataFrame(
        [{"type": "MM", "priorite_moyenne": 4, "poids_total": 3, "BE_Numero": "260001"}],
        index=[0],
    )

    class _SeqSolver:
        def __init__(self, seq: list[int]):
            self.seq = list(seq)
            self.calls = 0
            self.last_idx = 0

        def Solve(self, _model):
            idx = self.calls if self.calls < len(self.seq) else len(self.seq) - 1
            self.last_idx = idx
            self.calls += 1
            return self.seq[idx]

        def ObjectiveValue(self):
            return 1

    mode, final_status = sc.run_hierarchical_priority_optimization(
        model=model,
        solver=_SeqSolver(statuses),
        x=x,
        y=y,
        u=u,
        nb_benev=nb_benev,
        be_groups=be_groups,
        priority_map={"MM": 1},
        benev_ids=[1],
        benev_vols_compat={1: [0]},
        benev_avail_minutes={1: 60},
        priority_mode=priority_mode,
        log_fn=lambda _m: None,
        optimize_equilibrage_fn=lambda: None,
    )
    assert mode in {"colis", "benevoles"}
    assert final_status is None


@pytest.mark.skipif(not HAS_CP_MODEL, reason="OR-Tools non disponible")
def test_extract_solver_results_verbose_logging(monkeypatch):
    class _Var:
        pass

    vx = _Var()
    vu = _Var()
    vc = _Var()
    vnb = _Var()

    class _Solver:
        def __init__(self, values: dict[object, int]):
            self.values = values

        def Value(self, var):
            return int(self.values.get(var, 0))

    class _Logger:
        def __init__(self):
            self.messages: list[str] = []

        def info(self, msg, *args):
            self.messages.append(str(msg % args))

    logger = _Logger()
    monkeypatch.setattr(sc, "get_logger", lambda *_a, **_k: logger)

    payload = sc.extract_solver_results(
        solver=_Solver({vx: 1, vu: 1, vc: 5, vnb: 1}),
        x={(0, 0): vx},
        y={},
        u={0: vu},
        charge={0: vc},
        nb_be={0: vnb},
        be_groups=pd.DataFrame(
            [
                {
                    "BE_Numero": "260001",
                    "Destination": "RUN",
                    "nb_colis": 2,
                    "poids_total": 2,
                    "type": "MM",
                }
            ],
            index=[0],
        ),
        df_be_original=pd.DataFrame([{"BE_Numero": "260001", "Destination": "RUN", "BE_Nb_Colis": 2}]),
        df_vols=pd.DataFrame(
            [
                {
                    "datetime": pd.Timestamp("2026-01-20 10:00"),
                    "Date_Vol": "20/01/26",
                    "Heure_Vol": "10h00",
                    "Numero_Vol": "AF001",
                    "Destination": "RUN",
                    "dest_iata": "RUN",
                    "Routing": "CDG-RUN",
                }
            ]
        ),
        df_param_benev=pd.DataFrame(),
        status=sc.cp_model.OPTIMAL,
        verbose=True,
    )
    assert payload["status"] in {"OPTIMAL", "FEASIBLE"}
    assert any("Résumé" in m for m in logger.messages)
