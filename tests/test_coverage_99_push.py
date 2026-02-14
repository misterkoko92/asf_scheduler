# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime as dt
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

import asf_app.ui.ui_communication.email_expediteurs_handler as exp_handler
import asf_app.ui.ui_communication.ui_communication as comm_ui
import asf_app.ui.ui_simulation as ui_sim
import asf_app.ui.ui_week_data as ui_week_data
import scheduler.solver_ortools_v3 as solver_v3


class _CommStubSt:
    def __init__(self):
        self.session_state: dict[str, object] = {}
        self.warnings: list[str] = []
        self.errors: list[str] = []
        self.infos: list[str] = []
        self._radio_values: dict[str, object] = {}
        self._button_values: dict[str, bool] = {}
        self._number_value = 2026

    def warning(self, msg):
        self.warnings.append(str(msg))

    def error(self, msg):
        self.errors.append(str(msg))

    def info(self, msg):
        self.infos.append(str(msg))

    def radio(self, label, options, index=0, key=None, **_kwargs):
        if key and key in self._radio_values:
            return self._radio_values[key]
        if label in self._radio_values:
            return self._radio_values[label]
        return options[index]

    def button(self, label, **_kwargs):
        return bool(self._button_values.get(str(label), False))

    def number_input(self, _label, **_kwargs):
        return self._number_value


def test_comm_ui_remaining_branches(monkeypatch, tmp_path):
    # Line 116: folder entries are skipped.
    monkeypatch.setattr(comm_ui, "get_output_remote_dir", lambda _year: "/remote")
    monkeypatch.setattr(
        comm_ui.cp,
        "list_onedrive_files",
        lambda *_a, **_k: [
            {"name": "folder.xlsx", "path": "/remote/folder.xlsx", "folder": {}},
            {"name": "ok.xlsx", "path": "/remote/ok.xlsx", "lastModifiedDateTime": "2026-01-01T10:00:00Z"},
        ],
    )
    files = comm_ui._list_onedrive_planning_files(2026)
    assert [f["name"] for f in files] == ["ok.xlsx"]

    # Line 153: simulation fallback to first mode when no active mode.
    stub = _CommStubSt()
    stub.session_state["sim_results"] = {
        "colis": {"planning_df": pd.DataFrame([{"mode": "colis"}])},
        "benevoles": {"planning_df": pd.DataFrame([{"mode": "benevoles"}])},
    }
    monkeypatch.setattr(comm_ui, "st", stub)
    monkeypatch.setattr(comm_ui, "get_planning_state", lambda: SimpleNamespace(planning=pd.DataFrame()))
    monkeypatch.setattr(comm_ui, "normalize_planning_df", lambda df: df if df is not None else pd.DataFrame())
    out = comm_ui._load_session_planning_ui()
    assert isinstance(out, pd.DataFrame)
    assert out.iloc[0]["mode"] == "colis"

    # Lines 161-162: options list unexpectedly empty.
    stub2 = _CommStubSt()
    monkeypatch.setattr(comm_ui, "st", stub2)
    monkeypatch.setattr(comm_ui, "get_planning_state", lambda: SimpleNamespace(planning=pd.DataFrame([{"x": 1}])))
    monkeypatch.setattr(comm_ui, "normalize_planning_df", lambda df: df if df is not None else pd.DataFrame())
    monkeypatch.setattr(comm_ui, "build_session_source_options", lambda **_kwargs: [])
    assert comm_ui._load_session_planning_ui() is None
    assert any("Aucun planning disponible" in msg for msg in stub2.warnings)

    # Line 236: loaded file has empty Export planning.
    stub3 = _CommStubSt()
    stub3._button_values["✅ Valider ce planning"] = True
    monkeypatch.setattr(comm_ui, "st", stub3)
    monkeypatch.setattr(comm_ui, "is_graph_onedrive", lambda: True)
    monkeypatch.setattr(
        comm_ui,
        "_list_onedrive_planning_files",
        lambda _year: [{"name": "plan.xlsx", "path": "/remote/plan.xlsx"}],
    )
    monkeypatch.setattr(comm_ui, "safe_cache_path", lambda _root, _remote: tmp_path / "plan.xlsx")
    monkeypatch.setattr(comm_ui.cp, "download_onedrive_file", lambda *_a, **_k: True)
    monkeypatch.setattr(comm_ui, "_read_export_planning", lambda _p: pd.DataFrame())
    assert comm_ui._load_onedrive_planning_ui() is None
    assert any("Export planning" in msg for msg in stub3.errors)

    # Lines 357-359: invalid OneDrive path in PDF chooser.
    stub4 = _CommStubSt()
    monkeypatch.setattr(comm_ui, "st", stub4)
    monkeypatch.setattr(comm_ui, "is_graph_onedrive", lambda: True)
    monkeypatch.setattr(
        comm_ui,
        "_resolve_pdf_candidates_from_graph",
        lambda _w, _y: [{"name": "planning.pdf", "path": "bad://remote"}],
    )
    monkeypatch.setattr(comm_ui, "safe_cache_path", lambda *_a, **_k: (_ for _ in ()).throw(ValueError("bad path")))
    assert comm_ui._resolve_pdf_attachment_path(week=4, year=2026) is None
    assert any("Chemin OneDrive invalide" in msg for msg in stub4.errors)


def test_email_expediteur_empty_df_returns_false():
    assert (
        exp_handler.generate_expediteur_email_for_pair(
            df_comm=pd.DataFrame(),
            df_paramdest=pd.DataFrame(),
            df_paramexpediteur=pd.DataFrame(),
            expediteur="MSF",
            destination="DLA",
            week=4,
            year=2026,
        )
        is False
    )


def test_ui_week_data_remaining_branches(monkeypatch):
    # Line 112: fallback series when column is missing.
    state = SimpleNamespace(df_param_be=pd.DataFrame([{"Type": "MM"}]), tdb_tmp="tdb.xlsx")
    monkeypatch.setattr(ui_week_data, "get_state", lambda: state)
    monkeypatch.setattr(
        ui_week_data,
        "load_shipments_df",
        lambda **_kwargs: pd.DataFrame([{"BE_Numero": "260001", "BE_Douane": "oui"}]),
    )
    out_be, err = ui_week_data.load_be_moteur()
    assert err is None
    assert out_be is not None and int(out_be.iloc[0]["Nb_Colis"]) == 0

    # Lines 292 and 352: invalid date row skipped / empty result path.
    state_flights = SimpleNamespace(
        df_vols=pd.DataFrame(
            [
                {"Date_Vol": "invalid", "Heure_Vol": "10:00", "Routing": "CDG-DLA", "Numero_Vol": "AF001"},
                {"Date_Vol": "invalid", "Heure_Vol": "", "Routing": "CDG", "Numero_Vol": "AF002"},
            ]
        ),
        df_param_dest=pd.DataFrame(),
        df_be=pd.DataFrame(),
        api_start_date=None,
        api_end_date=None,
    )
    monkeypatch.setattr(ui_week_data, "load_be_moteur", lambda: (None, None))
    out_flights = ui_week_data._prepare_flights_dataframe(state_flights, week=8, iata_to_city={"DLA": "DOUALA"})
    assert out_flights.empty


class _WeekCtx:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        _ = exc_type, exc, tb
        return False


class _WeekRenderStubSt:
    def __init__(self):
        self.errors: list[str] = []
        self._select_values: dict[str, object] = {}
        self.dataframe_calls = 0

    def header(self, *_args, **_kwargs):
        return None

    def subheader(self, *_args, **_kwargs):
        return None

    def columns(self, n, **_kwargs):
        _ = _kwargs
        return [_WeekCtx() for _ in range(int(n))]

    def error(self, msg):
        self.errors.append(str(msg))

    def info(self, *_args, **_kwargs):
        return None

    def expander(self, *_args, **_kwargs):
        return _WeekCtx()

    def container(self):
        return _WeekCtx()

    def markdown(self, *_args, **_kwargs):
        return None

    def selectbox(self, _label, options, index=0, **_kwargs):
        return options[index]

    def data_editor(self, df, **_kwargs):
        return df

    def dataframe(self, obj, **_kwargs):
        self.dataframe_calls += 1
        if hasattr(obj, "to_html"):
            obj.to_html()
        return None


def test_ui_week_data_styler_branches_execute(monkeypatch):
    stub = _WeekRenderStubSt()
    monkeypatch.setattr(ui_week_data, "st", stub)
    monkeypatch.setattr(ui_week_data, "detect_week", lambda _state: 8)
    monkeypatch.setattr(ui_week_data, "build_iata_city_maps", lambda _df: ({}, {}))
    monkeypatch.setattr(ui_week_data, "load_be_moteur", lambda: (pd.DataFrame([{"Destination": "DLA"}]), None))
    monkeypatch.setattr(ui_week_data, "bloc_with_sort", lambda *_a, **_k: None)
    monkeypatch.setattr(
        ui_week_data,
        "_prepare_benevoles_dataframe",
        lambda *_a, **_k: pd.DataFrame([{"Nom": "A", "Date": "16/02/26", "Arrivée": "11h00", "Départ": "13h00"}]),
    )
    monkeypatch.setattr(
        ui_week_data,
        "_prepare_flights_dataframe",
        lambda *_a, **_k: pd.DataFrame([{"Destination": "DLA", "Date": "16/02/26", "Heure": "11h00"}]),
    )
    monkeypatch.setattr(ui_week_data, "_compute_week_dates", lambda **_k: [pd.Timestamp("2026-02-16")])
    monkeypatch.setattr(ui_week_data, "_build_day_labels", lambda _dates: ["lundi 16/02"])
    monkeypatch.setattr(
        ui_week_data,
        "_build_benev_week_table",
        lambda *_a, **_k: (
            pd.DataFrame({("lundi 16/02", "Début"): ["11h00"], ("lundi 16/02", "Fin"): ["13h00"]}, index=["A (1)"]),
            pd.DataFrame({("lundi 16/02", "Début"): [True], ("lundi 16/02", "Fin"): [True]}, index=["A (1)"]),
        ),
    )
    monkeypatch.setattr(ui_week_data, "_build_benev_ranges_by_date", lambda *_a, **_k: {})
    monkeypatch.setattr(
        ui_week_data,
        "_build_flights_week_table",
        lambda *_a, **_k: (
            pd.DataFrame({"lundi 16/02": ["11h00 - AF 822 - DLA"]}, index=["DLA (1)"]),
            pd.DataFrame({"lundi 16/02": ["compatible"]}, index=["DLA (1)"]),
        ),
    )
    monkeypatch.setattr(
        ui_week_data,
        "get_state",
        lambda: SimpleNamespace(
            api_start_date=None,
            api_end_date=None,
            df_param_dest=pd.DataFrame(),
            df_be=pd.DataFrame(),
            df_benev=pd.DataFrame(),
            df_vols=pd.DataFrame(),
        ),
    )

    ui_week_data.render_tab_week_data()
    assert stub.dataframe_calls >= 2


def test_ui_simulation_reason_and_stats_branches(monkeypatch):
    day = dt.date(2026, 1, 20)
    reason_context = {
        "vols": pd.DataFrame(
            [
                {"_Dest_Code": "DLA", "_Date_only": day, "_Heure_Min": 600, "_Max_Colis": 10, "_Vol_Numero": "AF100"},
                {"_Dest_Code": "DLA", "_Date_only": day, "_Heure_Min": 700, "_Max_Colis": pd.NA, "_Vol_Numero": "AF101"},
            ]
        ),
        "dispos": pd.DataFrame([{"_Date_only": day, "_Arr_Min": 500, "_Dep_Min": 900}]),
        "plan_load": {(day, 600, "AF100"): 10.0},
    }
    reason = ui_sim._infer_non_affectation_reason(dest_code="DLA", reason_context=reason_context)
    assert reason == "Conflit de contraintes (priorités/quotas)"

    reason_context2 = {
        "vols": pd.DataFrame(
            [{"_Dest_Code": "DLA", "_Date_only": day, "_Heure_Min": 600, "_Max_Colis": 20, "_Vol_Numero": "AF102"}]
        ),
        "dispos": pd.DataFrame([{"_Date_only": day, "_Arr_Min": 500, "_Dep_Min": 900}]),
        "plan_load": {(day, 600, "AF102"): 5.0},
    }
    reason2 = ui_sim._infer_non_affectation_reason(dest_code="DLA", reason_context=reason_context2)
    assert reason2 == "Conflit de contraintes (priorités/quotas)"

    reason3 = ui_sim._infer_non_affectation_reason(
        dest_code="DLA",
        reason_context={"vols": reason_context2["vols"], "dispos": pd.DataFrame(), "plan_load": {}},
    )
    assert "Aucun bénévole disponible" in reason3

    # _build_reason_context line 111 (Date column path)
    ctx = ui_sim._build_reason_context(
        df_plan=pd.DataFrame(),
        df_vols_src=pd.DataFrame(),
        df_dispo_src=pd.DataFrame([{"Date": "20/01/26", "Heure_Arrivee": "09:00", "Heure_Depart": "12:00"}]),
        start_dt=None,
        end_dt=None,
    )
    assert "dispos" in ctx

    # _recompute_dest_stats: empty/missing param branches + invalid date filter path.
    out_empty_param = ui_sim._recompute_dest_stats(
        pd.DataFrame([{"Destination": "UNK", "BE_Numero": "1", "BE_Nb_Colis": 1, "BE_Nb_Equiv": 1}]),
        df_vols_src=pd.DataFrame(),
        df_paramdest=pd.DataFrame(),
        start_dt=None,
        end_dt=None,
    )
    assert not out_empty_param.empty

    out_invalid_vol = ui_sim._recompute_dest_stats(
        pd.DataFrame(
            [
                {"Destination": "AAA", "BE_Numero": "1", "BE_Nb_Colis": 1, "BE_Nb_Equiv": 1, "Date_Vol": "20/01/26", "Heure_Vol": "10:00", "Numero_Vol": "AF1"},
                {"Destination": None, "BE_Numero": "2", "BE_Nb_Colis": 1, "BE_Nb_Equiv": 1, "Date_Vol": "20/01/26", "Heure_Vol": "11:00", "Numero_Vol": "AF2"},
            ]
        ),
        df_vols_src=pd.DataFrame([{"Date_Vol": "bad-date", "Heure_Vol": "10:00", "Numero_Vol": "AF1", "IATA": "AAA"}]),
        df_paramdest=pd.DataFrame(
            [
                {"Dest_IATA": "", "Dest_Ville": "EMPTY"},
                {"Dest_IATA": "AAA", "Dest_Ville": "AAA CITY", "Freq_Lundi": 1},
            ]
        ),
        start_dt=None,
        end_dt=None,
    )
    assert int(out_invalid_vol.iloc[0]["Nb_Vols_Existant"]) == 0

    # _recompute_bilan_benevoles branches 658 + 674-677
    bilan_benev = ui_sim._recompute_bilan_benevoles(
        pd.DataFrame(),
        pd.DataFrame([{"Benevole": "ALICE", "Date": "20/01/26", "Heure_Arrivee": "09:00", "Heure_Depart": "12:00"}]),
        df_parambenev=pd.DataFrame([{"Benevole": ""}, {"Benevole": "ALICE"}]),
        start_dt=None,
        end_dt=None,
    )
    assert not bilan_benev.empty

    monkeypatch.setattr(ui_sim, "count_benevoles_with_dispo", lambda *_a, **_k: (0, None, None))
    resume = ui_sim._compute_resume_numbers(
        pd.DataFrame(),
        df_be=None,
        df_dispo=pd.DataFrame(),
        start_dt=None,
        end_dt=None,
        stats={"status": "OK"},
    )
    assert resume["nb_colis_total"] == 0

    monkeypatch.setattr(ui_sim, "count_benevoles_with_dispo", lambda *_a, **_k: (1, None, None))
    resume2 = ui_sim._compute_resume_numbers(
        pd.DataFrame(
            [
                {
                    "BE_Numero": "260001",
                    "BE_Nb_Colis": pd.NA,
                    "Date_Vol": "20/01/26",
                    "Numero_Vol": "AF100",
                }
            ]
        ),
        df_be=pd.DataFrame(
            [{"BE_Numero": "260001", "BE_Nb_Colis": pd.NA, "BE_Nb_Colis_MAG": pd.NA, "Nb_Colis": 2}]
        ),
        df_dispo=pd.DataFrame(),
        start_dt=None,
        end_dt=None,
        stats={"status": "OK"},
    )
    assert resume2["nb_colis_total"] == 2


class _SimCtx:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        _ = exc_type, exc, tb
        return False


class _SimCol(_SimCtx):
    def __init__(self, parent):
        self.parent = parent

    def button(self, label, **_kwargs):
        return self.parent.button(label)

    def metric(self, *_args, **_kwargs):
        return None


class _SessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


class _SimStubSt:
    def __init__(self):
        self.session_state = _SessionState(
            {
            "sim_results": {
                "colis": {
                    "planning_df": pd.DataFrame(
                        [
                            {
                                "Date_Vol": "20/01/26",
                                "Heure_Vol": "10:00",
                                "Numero_Vol": "AF100",
                                "Destination": "DLA",
                                "BE_Numero": "260001",
                                "Benevole": "ALICE",
                            }
                        ]
                    ),
                    "statistiques": {"status": "OK"},
                }
            },
            "sim_active_mode": "colis",
            "solver_version": "v3",
        }
        )
        self._button_values = {"Supprimer l'expédition sélectionnée": True}
        self.infos: list[str] = []
        self.warnings: list[str] = []
        self.successes: list[str] = []

    def title(self, *_args, **_kwargs):
        return None

    def markdown(self, *_args, **_kwargs):
        return None

    def number_input(self, _label, value=30, **_kwargs):
        return value

    def checkbox(self, _label, value=False, **_kwargs):
        return value

    def spinner(self, *_args, **_kwargs):
        return _SimCtx()

    def info(self, msg):
        self.infos.append(str(msg))

    def warning(self, msg):
        self.warnings.append(str(msg))

    def success(self, msg):
        self.successes.append(str(msg))

    def error(self, *_args, **_kwargs):
        return None

    def radio(self, _label, options, index=0, **_kwargs):
        return options[index]

    def selectbox(self, _label, options, index=0, **_kwargs):
        return options[index] if options else ""

    def columns(self, n, **_kwargs):
        count = len(n) if isinstance(n, (list, tuple)) else int(n)
        return [_SimCol(self) for _ in range(count)]

    def container(self):
        return _SimCtx()

    def toggle(self, _label, value=False, **_kwargs):
        return value

    def dataframe(self, *_args, **_kwargs):
        return None

    def expander(self, *_args, **_kwargs):
        return _SimCtx()

    def button(self, label, **_kwargs):
        return bool(self._button_values.get(str(label), False))


def test_ui_simulation_render_delete_branch(monkeypatch, tmp_path):
    stub = _SimStubSt()
    monkeypatch.setattr(ui_sim, "st", stub)
    monkeypatch.setattr(
        ui_sim,
        "get_state",
        lambda: SimpleNamespace(
            api_start_date="2026-01-19",
            api_end_date="2026-01-25",
            current_week=4,
            current_year=2026,
            df_param_dest=pd.DataFrame([{"Dest_IATA": "DLA", "Dest_Ville": "DOUALA"}]),
        ),
    )
    monkeypatch.setattr(ui_sim, "get_solver_version", lambda _v: "v3")
    monkeypatch.setattr(
        ui_sim,
        "get_excel_source_paths",
        lambda _state: SimpleNamespace(
            tableau_de_bord=tmp_path / "TABLEAU_DE_BORD.xlsx",
            vols=tmp_path / "VOLS.xlsx",
            planning_benevoles=tmp_path / "PLANNING_BENEVOLES.xlsx",
        ),
    )
    monkeypatch.setattr("loaders.load_shipments.load_shipments_df", lambda **_k: pd.DataFrame([{"BE_Numero": "260001"}]))
    monkeypatch.setattr("loaders.load_vols.load_vols_df", lambda **_k: pd.DataFrame([{"Numero_Vol": "AF100"}]))
    monkeypatch.setattr("loaders.load_benevoles.load_benevoles", lambda **_k: pd.DataFrame([{"Benevole": "ALICE"}]))
    monkeypatch.setattr("loaders.load_params.get_param_dest", lambda: pd.DataFrame([{"Dest_IATA": "DLA", "Dest_Ville": "DOUALA"}]))
    monkeypatch.setattr("loaders.load_params.get_param_benev", lambda: pd.DataFrame([{"Benevole": "ALICE", "ID": "1"}]))
    monkeypatch.setattr(ui_sim, "count_benevoles_with_dispo", lambda *_a, **_k: (1, pd.Timestamp("2026-01-19"), pd.Timestamp("2026-01-25")))
    monkeypatch.setattr(ui_sim, "build_iata_city_maps", lambda _df: ({"DLA": "DOUALA"}, {"DOUALA": "DLA"}))
    monkeypatch.setattr(
        ui_sim,
        "_build_be_options",
        lambda *_a, **_k: [("260001", "260001", "DLA | 260001", pd.Series({"Destination": "DLA"}))],
    )
    monkeypatch.setattr(
        ui_sim,
        "_filter_vols_for_selection",
        lambda *_a, **_k: pd.DataFrame([{"Date_Vol": "20/01/26", "Heure_Vol": "10:00", "Numero_Vol": "AF100", "Routing": "CDG-DLA"}]),
    )
    monkeypatch.setattr(
        ui_sim,
        "_build_vol_selector_data",
        lambda *_a, **_k: (["vol"], [("20/01/26", "AF100", "10:00")], 0),
    )
    monkeypatch.setattr(
        ui_sim,
        "_build_bene_selector_data",
        lambda *_a, **_k: (["ALICE"], ["ALICE"], 0),
    )
    monkeypatch.setattr(ui_sim, "_delete_manual_assignment", lambda df, **_k: df.copy())
    monkeypatch.setattr(ui_sim, "_sort_planning", lambda df: df)
    monkeypatch.setattr(ui_sim, "_normalize_sort_plan", lambda df: df)
    monkeypatch.setattr(
        ui_sim,
        "_recompute_all_tables",
        lambda *_a, **_k: (pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()),
    )
    monkeypatch.setattr(
        ui_sim,
        "_compute_resume_numbers",
        lambda *_a, **_k: {
            "status": "OK",
            "nb_be_envoyes": 0,
            "nb_be_total": 0,
            "nb_vols": 0,
            "nb_colis_expedies": 0,
            "nb_colis_total": 0,
            "taux_colis": 0,
            "benev_used": 0,
            "benev_dispo": 1,
        },
    )
    monkeypatch.setattr(ui_sim, "_style_manual_df", lambda df: df)
    monkeypatch.setattr(ui_sim, "_export_simulation_excel", lambda **_k: None)
    monkeypatch.setattr("asf_app.ui.ui_planning.utils.show_mag_central_status", lambda: None)

    ui_sim.render_tab_simulation()
    assert any("Expédition supprimée" in msg for msg in stub.successes)


@pytest.mark.skipif(solver_v3.cp_model is None, reason="OR-Tools non disponible")
def test_solver_v3_be_without_option_logs_branch(monkeypatch):
    monkeypatch.setattr(solver_v3, "_validate_inputs", lambda *_a, **_k: [])
    monkeypatch.setattr(solver_v3, "_build_dest_info", lambda *_a, **_k: {})
    monkeypatch.setattr(
        solver_v3,
        "_group_shipments",
        lambda *_a, **_k: pd.DataFrame(
            [
                {"BE_Numero": "BE1", "poids_total": 1, "type": "MM", "nb_colis": 1, "BE_Expediteur": "ASF", "BE_Destinataire": "X"},
                {"BE_Numero": "BE2", "poids_total": 1, "type": "MM", "nb_colis": 1, "BE_Expediteur": "ASF", "BE_Destinataire": "Y"},
            ],
            index=[0, 1],
        ),
    )
    monkeypatch.setattr(
        solver_v3,
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
        solver_v3,
        "_parse_benevoles",
        lambda *_a, **_k: pd.DataFrame(
            [{"ID": 1, "date": dt.date(2026, 1, 20), "heure_debut": dt.time(9, 0), "heure_fin": dt.time(12, 0)}],
            index=[0],
        ),
    )
    monkeypatch.setattr(
        solver_v3,
        "_create_be_variables",
        lambda model, *_a, **_k: {(0, 0): model.NewBoolVar("x_0_0")},
    )
    monkeypatch.setattr(
        solver_v3,
        "_create_benev_variables",
        lambda model, *_a, **_k: ({(1, 0): model.NewBoolVar("y_1_0")}, {1: [0]}, [0], [1]),
    )
    monkeypatch.setattr(
        solver_v3,
        "_build_vols_compatibility_df",
        lambda *_a, **_k: pd.DataFrame(
            [{"Numero_Vol": "AF001", "Date_Vol": "20/01/26", "Heure_Vol": "10:00", "Dest_IATA": "RUN", "BE_Compat_Count": 1, "Benev_Compat_Count": 1}]
        ),
    )
    monkeypatch.setattr(
        solver_v3,
        "_summarize_vols_compatibility",
        lambda *_a, **_k: {"nb_vols_total": 1, "nb_vols_sans_benevole_compatible": 0, "nb_vols_sans_be_compatible": 0},
    )
    monkeypatch.setattr(solver_v3, "_create_assignment_variables", lambda *_a, **_k: {})
    monkeypatch.setattr(solver_v3, "_build_benev_max_colis_map", lambda *_a, **_k: {1: 10})
    monkeypatch.setattr(solver_v3, "_add_be_constraints", lambda *_a, **_k: None)
    monkeypatch.setattr(solver_v3, "_add_benev_constraints", lambda *_a, **_k: None)
    monkeypatch.setattr(solver_v3, "_add_assignment_constraints", lambda *_a, **_k: None)
    monkeypatch.setattr(solver_v3, "_add_dest_constraints", lambda *_a, **_k: None)
    monkeypatch.setattr(solver_v3, "_add_physical_flight_exclusivity_constraints", lambda *_a, **_k: None)
    monkeypatch.setattr(solver_v3, "_add_physical_flight_routing_priority_constraints", lambda *_a, **_k: None)
    monkeypatch.setattr(solver_v3, "_run_hierarchical_priority_optimization", lambda **_k: ("colis", None))

    class _DS:
        name = "dummy_v3"

        def load_param_be(self):
            return pd.DataFrame([{"Type": "MM", "Priorite_Type": 1}])

        def load_param_dest(self):
            return pd.DataFrame([{"Dest_IATA": "RUN"}])

        def load_param_benev(self):
            return pd.DataFrame([{"ID": 1, "Benevole": "Alice"}])

        def load_shipments_df(self, _param_be=None, *, planifiables_only: bool = True):
            _ = _param_be, planifiables_only
            return pd.DataFrame([{"BE_Numero": "BE1", "Destination": "RUN"}])

        def load_vols_df(self, _param_dest=None):
            _ = _param_dest
            return pd.DataFrame([{"Date_Vol": "20/01/26", "Heure_Vol": "10:00", "IATA": "RUN", "Numero_Vol": "AF001"}])

        def load_benevoles_df(self, _param_benev=None):
            _ = _param_benev
            return pd.DataFrame([{"ID": 1, "Date_dt": pd.Timestamp("2026-01-20"), "Heure_Arrivee_time": dt.time(9, 0), "Heure_Depart_time": dt.time(12, 0)}])

    out = solver_v3.solve_planning_ortools_simulation(data_source=_DS())
    assert out.get("status") == "INFAISABLE"
