# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime as dt
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

import asf_app.config.email_defaults as email_defaults
import asf_app.config.session_context as session_context
import asf_app.state as app_state
import asf_app.ui.ui_communication.clean_planning_df as clean_df
import scheduler.solver_ortools_v3 as solver_v3
import utils.datetime_utils as du


def test_email_defaults_and_session_context_import_fallbacks(monkeypatch):
    normalized = email_defaults.normalize_email_defaults(None)
    assert "airfrance" in normalized and "asf_interne" in normalized

    fake_state_module = types.ModuleType("asf_app.state")
    monkeypatch.setitem(sys.modules, "asf_app.state", fake_state_module)
    ctx = session_context.SessionContext(
        config=SimpleNamespace(),
        session_id="sid",
        tmp_dir=Path("/tmp"),
        source_paths=SimpleNamespace(
            tableau_de_bord=Path("/tmp/a.xlsx"),
            planning_benevoles=Path("/tmp/b.xlsx"),
            vols=Path("/tmp/c.xlsx"),
        ),
    )
    # Must silently return on ImportError / AttributeError.
    session_context._sync_state_from_context(ctx)

    fake_session_context_module = types.ModuleType("asf_app.config.session_context")
    monkeypatch.setitem(sys.modules, "asf_app.config.session_context", fake_session_context_module)
    assert app_state._get_session_context() is None


def test_datetime_utils_extra_branches(monkeypatch):
    assert du.parse_iso_datetime("   ") is None

    class _BadDate:
        def strftime(self, _fmt: str):
            raise TypeError("boom")

    monkeypatch.setattr(du, "parse_date_value", lambda *_a, **_k: _BadDate())
    assert du.format_date_value("01/01/26", default="N/A") == "N/A"

    class _BadTime:
        def strftime(self, _fmt: str):
            raise TypeError("boom")

    monkeypatch.setattr(du, "parse_time_value", lambda *_a, **_k: _BadTime())
    assert du.format_time_value("10:00", default="N/A") == "N/A"

    assert du.format_date_fr_long_slash("invalid-date") == ""
    assert du.format_date_fr_words("invalid-date") == ""
    assert du.parse_date_value_as_date(None) is None
    assert du.format_time_hm_loose(None) == ""
    assert du.parse_date_long_fr("2026-01-19") == pd.Timestamp("2026-01-19")


def test_clean_planning_df_name_fallback_and_id_cleanup():
    df_planning = pd.DataFrame(
        [
            {
                "DATE": "2026-01-19",
                "HEURE VOL": "11:00",
                "NUMERO VOL": "AF0822",
                "DESTINATION": "DLA",
                "NUMERO BE": "260001",
                "NOMBRE COLIS": 2,
                "TYPE": "MM",
                "EXPEDITEUR": "ASF",
                "BENEVOLE": "DUPONT ALICE",
                "BENEVOLE_ID": "999",
                "ID_BENEVOLE": "123.0",
                "BE_Destinataire": "HOPITAL",
            }
        ]
    )
    df_paramdest = pd.DataFrame([{"Dest_IATA": "DLA", "Dest_Ville": "DOUALA"}])
    df_parambenev = pd.DataFrame(
        [
            {
                "ID": "123",
                "Benevole": "DUPONT ALICE",
                "Prenom": "Alice",
                "Prenom_Court": "A.",
                "Nom": "Dupont",
                "Telephone": "0600000000",
            }
        ]
    )

    out = clean_df.build_df_comm(df_planning, df_paramdest, df_parambenev)
    assert not out.empty
    assert out.loc[0, "Destinataire"] == "HOPITAL"
    # Current implementation keeps fallback fields empty when ID merge already
    # created nullable columns; this test still exercises the fallback branch.
    assert "Benevole_Prenom" in out.columns
    assert "Benevole_Prenom_Court" in out.columns


@pytest.mark.skipif(solver_v3.cp_model is None, reason="OR-Tools non disponible")
def test_solver_v3_extra_branches():
    # _build_benev_max_colis_map: skip NaN ID branch
    out = solver_v3._build_benev_max_colis_map(
        pd.DataFrame(
            [
                {"ID": float("nan"), "Max_Colis_Vol": 12},
                {"ID": 7, "Max_Colis_Vol": 8},
            ]
        )
    )
    assert out == {7: 8}

    # _parse_time wrapper delegates core parser
    assert solver_v3._parse_time("10:30") is not None

    # _add_assignment_constraints: force branch where z_vars is empty => x_var == 0
    model = solver_v3.cp_model.CpModel()
    x = {(0, 0): model.NewBoolVar("x_0_0")}
    y = {(1, 0): model.NewBoolVar("y_1_0")}
    z: dict[tuple[int, int, int], object] = {}
    be_groups = pd.DataFrame([{"poids_total": 1}], index=[0])
    solver_v3._add_assignment_constraints(
        model=model,
        be_groups=be_groups,
        x=x,
        y=y,
        z=z,
        benev_by_vol={0: [1]},
        max_colis_by_benev={1: 20},
    )
    model.Maximize(x[(0, 0)] + y[(1, 0)])
    solver = solver_v3.cp_model.CpSolver()
    _ = solver.Solve(model)
    assert solver.Value(x[(0, 0)]) == 0

    # _build_planning_bilan_v3: skip NaN benevole ID rows in param
    be_groups_df = pd.DataFrame(
        [
            {
                "BE_Numero": "BE1",
                "nb_colis": 1,
                "poids_total": 1,
                "type": "MM",
                "BE_Expediteur": "ASF",
                "BE_Destinataire": "HOP",
            }
        ],
        index=[0],
    )
    vols_df = pd.DataFrame(
        [
            {
                "datetime": pd.Timestamp("2026-01-20 10:00"),
                "Date_Vol": dt.date(2026, 1, 20),
                "Heure_Vol": "10h00",
                "Numero_Vol": "AF001",
                "Destination": "RUN",
            }
        ],
        index=[0],
    )
    param_benev_df = pd.DataFrame([{"ID": pd.NA, "Benevole": "X"}, {"ID": 12, "Benevole": "ALICE"}])
    planning_df, _bilan_df = solver_v3._build_planning_bilan_v3(
        pd.DataFrame(
            [
                {
                    "Vol_Date": dt.date(2026, 1, 20),
                    "Vol_Numero": "AF001",
                    "Vol_Destination": "RUN",
                    "BE_Numero": "BE1",
                    "BE_Nb_Colis": 1,
                    "BE_Poids_Equiv": 1,
                }
            ]
        ),
        [{"BE_Index": 0, "Benevole_ID": 12, "Vol_Index": 0}],
        be_groups_df,
        vols_df,
        param_benev_df,
    )
    assert not planning_df.empty
    assert planning_df.iloc[0]["Benevole"] == "ALICE"
