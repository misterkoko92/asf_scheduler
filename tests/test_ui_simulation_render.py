# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

import asf_app.ui.ui_simulation as ui_sim


class _SessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


class _Ctx:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        _ = exc_type, exc, tb
        return False


class _Col(_Ctx):
    def __init__(self, parent):
        self.parent = parent

    def button(self, label, **_kwargs):
        return self.parent.button(label)

    def metric(self, label, value, delta=None):
        self.parent.metrics.append((str(label), value, delta))


class _StubSt:
    def __init__(self):
        self.session_state = _SessionState()
        self._button_sequences: dict[str, list[bool]] = {}
        self.infos: list[str] = []
        self.warnings: list[str] = []
        self.successes: list[str] = []
        self.errors: list[str] = []
        self.metrics: list[tuple[str, object, object]] = []

    def set_button_sequence(self, label: str, values: list[bool]):
        self._button_sequences[label] = list(values)

    def button(self, label, **_kwargs):
        seq = self._button_sequences.get(label)
        if seq:
            return seq.pop(0)
        return False

    def title(self, *_args, **_kwargs):
        return None

    def markdown(self, *_args, **_kwargs):
        return None

    def number_input(self, _label, min_value=0, max_value=0, value=0, step=1, **_kwargs):
        _ = min_value, max_value, step
        return value

    def checkbox(self, _label, value=False, **_kwargs):
        return value

    def spinner(self, *_args, **_kwargs):
        return _Ctx()

    def info(self, msg):
        self.infos.append(str(msg))

    def warning(self, msg):
        self.warnings.append(str(msg))

    def success(self, msg):
        self.successes.append(str(msg))

    def error(self, msg):
        self.errors.append(str(msg))

    def radio(self, _label, options, index=0, **_kwargs):
        return options[index]

    def selectbox(self, _label, options, index=0, **_kwargs):
        if not options:
            return ""
        return options[index]

    def columns(self, n, **_kwargs):
        count = len(n) if isinstance(n, (list, tuple)) else int(n)
        return [_Col(self) for _ in range(count)]

    def container(self):
        return _Ctx()

    def toggle(self, _label, value=False, **_kwargs):
        return value

    def dataframe(self, *_args, **_kwargs):
        return None

    def expander(self, *_args, **_kwargs):
        return _Ctx()


def _sample_planning_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Date_Vol": "20/01/26",
                "Heure_Vol": "10h00",
                "Numero_Vol": "AF100",
                "Destination": "DLA",
                "BE_Numero": "260001",
                "BE_Nb_Colis": 2,
                "BE_Nb_Equiv": 2,
                "BE_Expediteur": "ASF",
                "BE_Destinataire": "HOPITAL",
                "BE_Type": "MM",
                "Benevole": "ALICE",
                "ID": "1",
                "Telephone": "0600000000",
            }
        ]
    )


def test_render_tab_simulation_no_modes_shows_info(monkeypatch):
    stub = _StubSt()
    monkeypatch.setattr(ui_sim, "st", stub)
    monkeypatch.setattr(
        ui_sim,
        "get_state",
        lambda: SimpleNamespace(api_start_date=None, api_end_date=None),
    )
    monkeypatch.setattr(ui_sim, "get_solver_version", lambda _v: "v3")

    ui_sim.render_tab_simulation()

    assert any("Aucune simulation lancée" in msg for msg in stub.infos)


def test_render_tab_simulation_full_smoke(monkeypatch, tmp_path):
    stub = _StubSt()
    stub.session_state["solver_version"] = "v3"
    stub.set_button_sequence("Générer le planning", [True])
    stub.set_button_sequence("Ajouter / Mettre à jour", [True])
    stub.set_button_sequence("Supprimer l'expédition sélectionnée", [False])
    stub.set_button_sequence("📤 Exporter le planning simulé (Excel)", [True])
    monkeypatch.setattr(ui_sim, "st", stub)

    state = SimpleNamespace(
        api_start_date="2026-01-19",
        api_end_date="2026-01-25",
        current_week=4,
        current_year=2026,
        df_param_dest=pd.DataFrame([{"Dest_IATA": "DLA", "Dest_Ville": "DOUALA"}]),
    )
    monkeypatch.setattr(ui_sim, "get_state", lambda: state)
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
    monkeypatch.setattr(ui_sim, "ExcelDataSource", lambda paths: SimpleNamespace(paths=paths))
    monkeypatch.setattr(
        ui_sim,
        "run_ortools_simulation_dual",
        lambda **_kwargs: {
            "modes": {
                "colis": {
                    "planning_df": _sample_planning_df(),
                    "statistiques": {
                        "status": "OPTIMAL",
                        "nb_colis_expedies": 2,
                        "nb_benevoles_mobilises": 1,
                    },
                }
            },
            "selected": "colis",
        },
    )

    monkeypatch.setattr(
        "loaders.load_shipments.load_shipments_df",
        lambda **_kwargs: pd.DataFrame(
            [
                {
                    "Destination": "DLA",
                    "BE_Numero": "260001",
                    "BE_Nb_Colis": 2,
                    "Equiv_Colis": 2,
                    "BE_Type": "MM",
                    "BE_Expediteur": "ASF",
                    "BE_Destinataire": "HOPITAL",
                }
            ]
        ),
    )
    monkeypatch.setattr(
        "loaders.load_vols.load_vols_df",
        lambda **_kwargs: pd.DataFrame(
            [
                {
                    "Date_Vol": "20/01/26",
                    "Heure_Vol": "10h00",
                    "Numero_Vol": "AF100",
                    "IATA": "DLA",
                    "Destination": "DLA",
                    "Routing": "CDG-DLA",
                }
            ]
        ),
    )
    monkeypatch.setattr(
        "loaders.load_benevoles.load_benevoles",
        lambda **_kwargs: pd.DataFrame(
            [
                {
                    "Benevole": "ALICE",
                    "Date_dt": pd.Timestamp("2026-01-20"),
                    "Heure_Arrivee_time": pd.Timestamp("09:00").time(),
                    "Heure_Depart_time": pd.Timestamp("12:00").time(),
                }
            ]
        ),
    )
    monkeypatch.setattr(
        "loaders.load_params.get_param_dest",
        lambda: pd.DataFrame([{"Dest_IATA": "DLA", "Dest_Ville": "DOUALA"}]),
    )
    monkeypatch.setattr(
        "loaders.load_params.get_param_benev",
        lambda: pd.DataFrame([{"Benevole": "ALICE", "ID": "1", "Telephone": "0600000000"}]),
    )
    monkeypatch.setattr(
        ui_sim,
        "count_benevoles_with_dispo",
        lambda _df, _start, _end: (1, pd.Timestamp("2026-01-19"), pd.Timestamp("2026-01-25")),
    )
    monkeypatch.setattr(
        ui_sim,
        "build_iata_city_maps",
        lambda _df: ({"DLA": "DOUALA"}, {"DOUALA": "DLA"}),
    )

    monkeypatch.setattr(
        ui_sim,
        "_export_simulation_excel",
        lambda **_kwargs: SimpleNamespace(
            warnings=["test warning"],
            mag_write_method="excel",
            output_path=str(tmp_path / "planning_export.xlsx"),
        ),
    )
    monkeypatch.setattr(ui_sim, "_open_file", lambda _path: None)
    monkeypatch.setattr("asf_app.ui.ui_planning.utils.show_mag_central_status", lambda: None)
    monkeypatch.setattr(
        "utils.export_pdf.export_first_sheet_to_pdf",
        lambda _path: tmp_path / "planning_export.pdf",
    )

    ui_sim.render_tab_simulation()

    assert any("Planning simulation mis à jour." in msg for msg in stub.successes)
    assert any("Planning simulé exporté" in msg for msg in stub.successes)
    assert any("PDF généré" in msg for msg in stub.successes)
    assert any("test warning" in msg for msg in stub.warnings)
    assert stub.session_state.get("mag_central_write_method") == "excel"
    assert any(metric[0] == "Statut" for metric in stub.metrics)


def test_render_tab_simulation_empty_planning_shows_info(monkeypatch):
    stub = _StubSt()
    stub.session_state["solver_version"] = "v3"
    stub.session_state["sim_results"] = {"colis": {"planning_df": pd.DataFrame(), "statistiques": {}}}
    stub.session_state["sim_active_mode"] = "colis"
    monkeypatch.setattr(ui_sim, "st", stub)
    monkeypatch.setattr(ui_sim, "get_state", lambda: SimpleNamespace(api_start_date=None, api_end_date=None))
    monkeypatch.setattr(ui_sim, "get_solver_version", lambda _v: "v3")

    ui_sim.render_tab_simulation()

    assert any("Aucun planning simulé" in msg for msg in stub.infos)


def test_render_tab_simulation_warns_when_no_be_options(monkeypatch, tmp_path):
    stub = _StubSt()
    stub.session_state["solver_version"] = "v3"
    stub.session_state["sim_results"] = {"colis": {"planning_df": _sample_planning_df(), "statistiques": {}}}
    stub.session_state["sim_active_mode"] = "colis"
    monkeypatch.setattr(ui_sim, "st", stub)

    state = SimpleNamespace(
        api_start_date="2026-01-19",
        api_end_date="2026-01-25",
        current_week=4,
        current_year=2026,
        df_param_dest=pd.DataFrame(),
    )
    monkeypatch.setattr(ui_sim, "get_state", lambda: state)
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
    monkeypatch.setattr(
        "loaders.load_shipments.load_shipments_df",
        lambda **_kwargs: pd.DataFrame(),
    )
    monkeypatch.setattr("loaders.load_vols.load_vols_df", lambda **_kwargs: pd.DataFrame())
    monkeypatch.setattr(
        "loaders.load_benevoles.load_benevoles",
        lambda **_kwargs: pd.DataFrame(
            columns=["Benevole", "Date_dt", "Heure_Arrivee_time", "Heure_Depart_time"]
        ),
    )
    monkeypatch.setattr("loaders.load_params.get_param_dest", lambda: pd.DataFrame())
    monkeypatch.setattr("loaders.load_params.get_param_benev", lambda: pd.DataFrame())
    monkeypatch.setattr(
        ui_sim,
        "count_benevoles_with_dispo",
        lambda _df, _start, _end: (0, pd.Timestamp("2026-01-19"), pd.Timestamp("2026-01-25")),
    )
    monkeypatch.setattr(ui_sim, "build_iata_city_maps", lambda _df: ({}, {}))

    ui_sim.render_tab_simulation()

    assert any("Aucun BE statut D chargé." in msg for msg in stub.warnings)


def test_render_tab_simulation_export_handles_pdf_error_and_clears_write_method(monkeypatch, tmp_path):
    class _ToggleStub(_StubSt):
        def toggle(self, label, value=False, **_kwargs):
            if "écriture sur le excel source" in str(label):
                return False
            return value

    stub = _ToggleStub()
    stub.session_state["solver_version"] = "v3"
    stub.session_state["mag_central_write_method"] = "legacy"
    stub.session_state["sim_results"] = {"colis": {"planning_df": _sample_planning_df(), "statistiques": {"status": "OK"}}}
    stub.session_state["sim_active_mode"] = "colis"
    stub.set_button_sequence("📤 Exporter le planning simulé (Excel)", [True])
    monkeypatch.setattr(ui_sim, "st", stub)
    monkeypatch.setattr(
        ui_sim,
        "get_state",
        lambda: SimpleNamespace(
            api_start_date="2026-01-19",
            api_end_date="2026-01-25",
            current_week=4,
            current_year=2026,
            df_param_dest=pd.DataFrame(),
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
    monkeypatch.setattr(
        "loaders.load_shipments.load_shipments_df",
        lambda **_kwargs: pd.DataFrame(
            [{"Destination": "DLA", "BE_Numero": "260001", "BE_Nb_Colis": 2, "Equiv_Colis": 2}]
        ),
    )
    monkeypatch.setattr(
        "loaders.load_vols.load_vols_df",
        lambda **_kwargs: pd.DataFrame(
            [
                {
                    "Date_Vol": "20/01/26",
                    "Heure_Vol": "10h00",
                    "Numero_Vol": "AF100",
                    "IATA": "DLA",
                    "Destination": "DLA",
                    "Routing": "CDG-DLA",
                }
            ]
        ),
    )
    monkeypatch.setattr(
        "loaders.load_benevoles.load_benevoles",
        lambda **_kwargs: pd.DataFrame(
            [
                {
                    "Benevole": "ALICE",
                    "Date_dt": pd.Timestamp("2026-01-20"),
                    "Heure_Arrivee_time": pd.Timestamp("09:00").time(),
                    "Heure_Depart_time": pd.Timestamp("12:00").time(),
                }
            ]
        ),
    )
    monkeypatch.setattr("loaders.load_params.get_param_dest", lambda: pd.DataFrame([{"Dest_IATA": "DLA"}]))
    monkeypatch.setattr(
        "loaders.load_params.get_param_benev",
        lambda: pd.DataFrame([{"Benevole": "ALICE", "ID": "1", "Telephone": "0600000000"}]),
    )
    monkeypatch.setattr(
        ui_sim,
        "count_benevoles_with_dispo",
        lambda _df, _start, _end: (1, pd.Timestamp("2026-01-19"), pd.Timestamp("2026-01-25")),
    )
    monkeypatch.setattr(ui_sim, "build_iata_city_maps", lambda _df: ({"DLA": "DOUALA"}, {"DOUALA": "DLA"}))
    monkeypatch.setattr(
        ui_sim,
        "_export_simulation_excel",
        lambda **_kwargs: SimpleNamespace(
            warnings=[],
            mag_write_method="excel",
            output_path=str(tmp_path / "planning_export.xlsx"),
        ),
    )
    monkeypatch.setattr(ui_sim, "_open_file", lambda _path: None)
    monkeypatch.setattr("asf_app.ui.ui_planning.utils.show_mag_central_status", lambda: None)
    monkeypatch.setattr(
        "utils.export_pdf.export_first_sheet_to_pdf",
        lambda _path: (_ for _ in ()).throw(RuntimeError("pdf failed")),
    )

    ui_sim.render_tab_simulation()

    assert "mag_central_write_method" not in stub.session_state
    assert any("PDF non généré automatiquement" in msg for msg in stub.warnings)


def test_render_tab_simulation_export_error_is_reported(monkeypatch, tmp_path):
    stub = _StubSt()
    stub.session_state["solver_version"] = "v3"
    stub.session_state["sim_results"] = {"colis": {"planning_df": _sample_planning_df(), "statistiques": {}}}
    stub.session_state["sim_active_mode"] = "colis"
    stub.set_button_sequence("📤 Exporter le planning simulé (Excel)", [True])
    monkeypatch.setattr(ui_sim, "st", stub)
    monkeypatch.setattr(
        ui_sim,
        "get_state",
        lambda: SimpleNamespace(
            api_start_date="2026-01-19",
            api_end_date="2026-01-25",
            current_week=4,
            current_year=2026,
            df_param_dest=pd.DataFrame(),
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
    monkeypatch.setattr(
        "loaders.load_shipments.load_shipments_df",
        lambda **_kwargs: pd.DataFrame(
            [
                {
                    "Destination": "DLA",
                    "BE_Numero": "260001",
                    "BE_Nb_Colis": 1,
                    "BE_Type": "MM",
                }
            ]
        ),
    )
    monkeypatch.setattr(
        "loaders.load_vols.load_vols_df",
        lambda **_kwargs: pd.DataFrame(
            [
                {
                    "Date_Vol": "20/01/26",
                    "Heure_Vol": "10h00",
                    "Numero_Vol": "AF100",
                    "IATA": "DLA",
                    "Destination": "DLA",
                    "Routing": "CDG-DLA",
                }
            ]
        ),
    )
    monkeypatch.setattr(
        "loaders.load_benevoles.load_benevoles",
        lambda **_kwargs: pd.DataFrame(
            columns=["Benevole", "Date_dt", "Heure_Arrivee_time", "Heure_Depart_time"]
        ),
    )
    monkeypatch.setattr("loaders.load_params.get_param_dest", lambda: pd.DataFrame([{"Dest_IATA": "DLA"}]))
    monkeypatch.setattr("loaders.load_params.get_param_benev", lambda: pd.DataFrame([{"Benevole": "ALICE"}]))
    monkeypatch.setattr(
        ui_sim,
        "count_benevoles_with_dispo",
        lambda _df, _start, _end: (0, pd.Timestamp("2026-01-19"), pd.Timestamp("2026-01-25")),
    )
    monkeypatch.setattr(ui_sim, "build_iata_city_maps", lambda _df: ({}, {}))
    monkeypatch.setattr(
        ui_sim,
        "_export_simulation_excel",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("boom export")),
    )

    ui_sim.render_tab_simulation()

    assert any("Erreur lors de l'export" in msg for msg in stub.errors)
