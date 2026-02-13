# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

import asf_app.ui.ui_inputs as ui_inputs


def _build_state(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        tdb_tmp=tmp_path / "TABLEAU_DE_BORD.xlsx",
        benev_tmp=tmp_path / "PLANNING_BENEVOLES.xlsx",
        vols_tmp=tmp_path / "VOLS.xlsx",
        df_be=None,
        df_param_be=None,
        df_param_dest=None,
        df_benev=None,
        df_param_benev=None,
        df_vols=None,
        api_start_date=None,
        api_end_date=None,
        api_time_origin_type="P",
        vols_source="excel",
    )


class _Ctx:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        _ = exc_type, exc, tb
        return False


class _StubSt:
    def __init__(self):
        self.session_state: dict[str, object] = {}
        self.errors: list[str] = []
        self.infos: list[str] = []
        self.warnings: list[str] = []
        self.successes: list[str] = []
        self._button_sequences: dict[str, list[bool]] = {}
        self._uploader = None
        self._radio = {}
        self.rerun_called = False

    def set_button_sequence(self, label: str, values: list[bool]) -> None:
        self._button_sequences[label] = list(values)

    def set_uploader(self, upload) -> None:
        self._uploader = upload

    def header(self, *_args, **_kwargs):
        return None

    def subheader(self, *_args, **_kwargs):
        return None

    def write(self, *_args, **_kwargs):
        return None

    def info(self, msg):
        self.infos.append(str(msg))

    def warning(self, msg):
        self.warnings.append(str(msg))

    def success(self, msg):
        self.successes.append(str(msg))

    def error(self, msg):
        self.errors.append(str(msg))

    def caption(self, *_args, **_kwargs):
        return None

    def text_input(self, _label, value="", **_kwargs):
        return value

    def date_input(self, _label, value=None, **_kwargs):
        _ = value, _kwargs
        return date(2026, 2, 16)

    def columns(self, n, **_kwargs):
        _ = _kwargs
        count = len(n) if isinstance(n, (list, tuple)) else int(n)
        return [_Ctx() for _ in range(count)]

    def selectbox(self, _label, options, index=0, **_kwargs):
        return options[index]

    def radio(self, label, options, index=0, **_kwargs):
        return self._radio.get(str(label), options[index])

    def button(self, label, **_kwargs):
        _ = _kwargs
        seq = self._button_sequences.get(str(label))
        if seq:
            return seq.pop(0)
        return False

    def file_uploader(self, *_args, **_kwargs):
        return self._uploader

    def expander(self, *_args, **_kwargs):
        return _Ctx()

    def rerun(self):
        self.rerun_called = True

    def spinner(self, *_args, **_kwargs):
        return _Ctx()


def test_benev_last_message_delegates(monkeypatch, tmp_path):
    monkeypatch.setattr(ui_inputs, "get_benev_source_message", lambda p: f"ok:{p.name}")
    out = ui_inputs.benev_last_message(tmp_path / "PLANNING_BENEVOLES.xlsx")
    assert out == "ok:PLANNING_BENEVOLES.xlsx"


def test_load_files_handle_file_not_found_and_generic_errors(monkeypatch, tmp_path):
    state = _build_state(tmp_path)
    errors: list[str] = []
    monkeypatch.setattr(ui_inputs.st, "error", lambda msg: errors.append(str(msg)))

    monkeypatch.setattr(ui_inputs, "load_tdb", lambda *_a, **_k: (_ for _ in ()).throw(FileNotFoundError("tdb missing")))
    ui_inputs.load_tdb_file(state, force=True)
    monkeypatch.setattr(ui_inputs, "load_tdb", lambda *_a, **_k: (_ for _ in ()).throw(ValueError("tdb broken")))
    ui_inputs.load_tdb_file(state, force=True)

    monkeypatch.setattr(ui_inputs, "load_benev", lambda *_a, **_k: (_ for _ in ()).throw(FileNotFoundError("benev missing")))
    ui_inputs.load_benev_file(state, force=True)
    monkeypatch.setattr(ui_inputs, "load_benev", lambda *_a, **_k: (_ for _ in ()).throw(ValueError("benev broken")))
    ui_inputs.load_benev_file(state, force=True)

    monkeypatch.setattr(ui_inputs, "load_vols", lambda *_a, **_k: (_ for _ in ()).throw(FileNotFoundError("vols missing")))
    ui_inputs.load_vols_file(state, force=True)
    monkeypatch.setattr(ui_inputs, "load_vols", lambda *_a, **_k: (_ for _ in ()).throw(ValueError("vols broken")))
    ui_inputs.load_vols_file(state, force=True)

    assert any("tdb missing" in m for m in errors)
    assert any("benev missing" in m for m in errors)
    assert any("vols missing" in m for m in errors)
    assert any("Erreur chargement TABLEAU DE BORD" in m for m in errors)
    assert any("Erreur chargement Bénévoles" in m for m in errors)
    assert any("Erreur chargement Vols" in m for m in errors)


def test_overwrite_tmp_file_returns_when_uploaded_file_is_none(tmp_path):
    state = _build_state(tmp_path)
    state.vols_tmp.write_bytes(b"old")
    ui_inputs.overwrite_tmp_file(None, state, "vols", lambda *_a, **_k: None)
    assert state.vols_tmp.read_bytes() == b"old"


def test_refresh_from_onedrive_graph_mode_downloads_and_resets(monkeypatch, tmp_path):
    stub = _StubSt()
    monkeypatch.setattr(ui_inputs, "st", stub)
    monkeypatch.setattr(ui_inputs, "is_graph_onedrive", lambda: True)
    monkeypatch.setattr(ui_inputs, "get_tmp_dir", lambda: tmp_path)
    monkeypatch.setattr(ui_inputs, "get_tableau_de_bord_remote", lambda: "/remote/tdb.xlsx")
    monkeypatch.setattr(ui_inputs, "sync_state_paths_to_engine", lambda _s: None)

    downloaded: list[tuple[str, str]] = []

    def _download(remote_path, dst, interactive=False):
        _ = interactive
        downloaded.append((str(remote_path), str(dst)))
        Path(dst).write_bytes(b"new")

    monkeypatch.setattr(ui_inputs.cp, "download_onedrive_file", _download)

    state = _build_state(tmp_path)
    state.tdb_tmp.write_bytes(b"old")
    state.df_be = pd.DataFrame([{"x": 1}])
    state.df_param_be = pd.DataFrame([{"x": 1}])
    state.df_param_dest = pd.DataFrame([{"x": 1}])
    calls: list[bool] = []

    ui_inputs.refresh_from_onedrive(
        state,
        Path("/src/TABLEAU_DE_BORD.xlsx"),
        "tdb",
        lambda _state, force=False: calls.append(bool(force)),
    )

    assert downloaded
    assert downloaded[0][0] == "/remote/tdb.xlsx"
    assert state.df_be is None
    assert state.df_param_be is None
    assert state.df_param_dest is None
    assert calls == [True]
    assert any("Rechargé depuis OneDrive" in msg for msg in stub.successes)


def test_refresh_all_handles_missing_sources(monkeypatch, tmp_path):
    stub = _StubSt()
    monkeypatch.setattr(ui_inputs, "st", stub)
    state = _build_state(tmp_path)
    monkeypatch.setattr(
        ui_inputs,
        "refresh_session_context",
        lambda strict_sources=True: (_ for _ in ()).throw(FileNotFoundError("sources absentes")),
    )

    ui_inputs.refresh_all(state)
    assert any("sources absentes" in msg for msg in stub.errors)


def test_try_load_api_sheet_into_tmp_state_success_and_failure(monkeypatch, tmp_path):
    state = _build_state(tmp_path)
    state.df_param_dest = pd.DataFrame([{"Dest_IATA": "DLA"}])
    state.vols_tmp.write_bytes(b"x")

    import loaders.load_vols as lv
    import loaders.load_vols_api as lva

    copied: list[str] = []
    monkeypatch.setattr(lva, "copy_api_sheet_to_tmp", lambda s: copied.append(s))
    monkeypatch.setattr(
        lv,
        "load_vols_df",
        lambda **_kwargs: pd.DataFrame([{"Date_Vol": "16/02/26"}]),
    )

    ui_inputs._try_load_api_sheet_into_tmp_state(state, "API_S07")
    assert copied == ["API_S07"]
    assert isinstance(state.df_vols, pd.DataFrame)

    monkeypatch.setattr(lva, "copy_api_sheet_to_tmp", lambda *_a, **_k: (_ for _ in ()).throw(OSError("boom")))
    ui_inputs._try_load_api_sheet_into_tmp_state(state, "API_S08")


def test_render_vols_api_controls_cache_read_error_and_api_none(monkeypatch, tmp_path):
    stub = _StubSt()
    stub.set_button_sequence("Charger le dernier cache", [True])
    stub.set_button_sequence("Appeler l'API Air France", [True])
    monkeypatch.setattr(ui_inputs, "st", stub)
    monkeypatch.setattr(ui_inputs, "get_api_limits", lambda: (100, 1.0))
    monkeypatch.setattr(ui_inputs, "get_default_time_origin_type", lambda: "P")
    monkeypatch.setattr(ui_inputs, "get_tmp_dir", lambda: tmp_path)
    monkeypatch.setattr(ui_inputs.pd, "read_parquet", lambda *_a, **_k: (_ for _ in ()).throw(ValueError("cache invalid")))
    monkeypatch.setattr(ui_inputs, "load_vols_api", lambda *_a, **_k: None)

    cache_path = tmp_path / "vols_api_cache.parquet"
    cache_path.write_bytes(b"invalid")

    state = _build_state(tmp_path)
    state.api_start_date = date(2026, 2, 16)
    state.api_end_date = date(2026, 2, 22)
    state.api_time_origin_type = "X"

    ui_inputs._render_vols_api_controls(state)

    assert state.api_time_origin_type == "P"
    assert any("Erreur lecture cache" in m for m in stub.errors)
    assert any("Aucun vol retourné par l'API" in m for m in stub.warnings)


def test_render_vols_api_controls_warns_when_excel_save_fails(monkeypatch, tmp_path):
    stub = _StubSt()
    stub.set_button_sequence("Appeler l'API Air France", [True])
    monkeypatch.setattr(ui_inputs, "st", stub)
    monkeypatch.setattr(ui_inputs, "get_api_limits", lambda: (100, 1.0))
    monkeypatch.setattr(ui_inputs, "get_default_time_origin_type", lambda: "P")
    monkeypatch.setattr(ui_inputs, "get_tmp_dir", lambda: tmp_path)
    monkeypatch.setattr(
        ui_inputs,
        "load_vols_api",
        lambda *_a, **_k: pd.DataFrame([{"Date_Vol": "16/02/26", "Numero_Vol": "AF822"}]),
    )
    monkeypatch.setattr(
        ui_inputs,
        "store_vols_api_sheet",
        lambda *_a, **_k: (_ for _ in ()).throw(OSError("write failed")),
    )
    state = _build_state(tmp_path)
    state.api_start_date = date(2026, 2, 16)
    state.api_end_date = date(2026, 2, 22)

    ui_inputs._render_vols_api_controls(state)
    assert any("non sauvegardés dans Excel" in m for m in stub.warnings)


def test_render_vols_excel_controls_refresh_and_upload(monkeypatch, tmp_path):
    stub = _StubSt()
    stub.set_button_sequence("🔄 Recharger Vols depuis OneDrive", [True])
    monkeypatch.setattr(ui_inputs, "st", stub)
    called = {"refresh": 0, "overwrite": 0}
    monkeypatch.setattr(
        ui_inputs,
        "refresh_from_onedrive",
        lambda *_a, **_k: called.__setitem__("refresh", called["refresh"] + 1),
    )
    monkeypatch.setattr(ui_inputs, "get_vols_src", lambda: Path("/src/VOLS.xlsx"))
    monkeypatch.setattr(ui_inputs, "_upload_too_large", lambda *_a, **_k: False)
    monkeypatch.setattr(
        ui_inputs,
        "overwrite_tmp_file",
        lambda *_a, **_k: called.__setitem__("overwrite", called["overwrite"] + 1),
    )

    class Upload:
        size = 12

        def read(self):
            return b"x"

    stub.set_uploader(Upload())
    ui_inputs._render_vols_excel_controls(_build_state(tmp_path), cloud_mode=False)

    assert called["refresh"] == 1
    assert called["overwrite"] == 1


def test_render_vols_panel_handles_dataframe_error(monkeypatch, tmp_path):
    stub = _StubSt()
    monkeypatch.setattr(ui_inputs, "st", stub)
    monkeypatch.setattr(ui_inputs, "pretty_mtime", lambda _p: "N/A")
    monkeypatch.setattr(ui_inputs, "_render_vols_excel_controls", lambda *_a, **_k: None)
    monkeypatch.setattr(ui_inputs, "_render_vols_api_controls", lambda *_a, **_k: None)
    state = _build_state(tmp_path)
    state.vols_tmp.write_bytes(b"x")
    state.df_vols = object()

    ui_inputs._render_vols_panel(state, cloud_mode=False)
    assert any("Erreur lecture Vols" in m for m in stub.errors)


def test_render_graph_auth_section_flow_not_completed(monkeypatch):
    stub = _StubSt()
    stub.set_button_sequence("🔑 Se connecter à OneDrive", [True])
    stub.set_button_sequence("✅ J'ai terminé l'authentification", [True])
    monkeypatch.setattr(ui_inputs, "st", stub)
    monkeypatch.setattr(ui_inputs, "is_graph_onedrive", lambda: True)
    monkeypatch.setattr(
        ui_inputs.cp,
        "get_graph_client",
        lambda: SimpleNamespace(acquire_token_silent=lambda: None),
    )
    monkeypatch.setattr(ui_inputs.cp, "begin_onedrive_device_flow", lambda: {"message": "connect-now"})
    monkeypatch.setattr(ui_inputs.cp, "complete_onedrive_device_flow", lambda _flow: False)

    ui_inputs._render_graph_onedrive_auth_section()
    assert any("connect-now" in msg for msg in stub.infos)
    assert stub.rerun_called is False


def test_render_tab_inputs_source_error_and_cloud_warning(monkeypatch, tmp_path):
    stub = _StubSt()
    stub.session_state["source_error"] = "sources manquantes"
    monkeypatch.setattr(ui_inputs, "st", stub)
    monkeypatch.setattr(ui_inputs, "IS_STREAMLIT_CLOUD", True)
    monkeypatch.setattr(ui_inputs, "is_graph_onedrive", lambda: False)
    state = _build_state(tmp_path)
    for p in (state.tdb_tmp, state.benev_tmp, state.vols_tmp):
        p.write_bytes(b"x")
    monkeypatch.setattr(ui_inputs, "get_state", lambda: state)
    monkeypatch.setattr(ui_inputs, "_render_graph_onedrive_auth_section", lambda: None)
    monkeypatch.setattr(
        ui_inputs,
        "_resolve_inputs_session_context",
        lambda: SimpleNamespace(
            source_paths=SimpleNamespace(
                tableau_de_bord=state.tdb_tmp,
                planning_benevoles=state.benev_tmp,
                vols=state.vols_tmp,
            )
        ),
    )
    monkeypatch.setattr(ui_inputs, "_ensure_inputs_tmp_paths", lambda *_a, **_k: None)
    monkeypatch.setattr(ui_inputs, "_load_input_dataframes", lambda *_a, **_k: None)
    monkeypatch.setattr(ui_inputs, "pick_planning_dates", lambda *_a, **_k: None)
    monkeypatch.setattr(ui_inputs, "_render_inputs_panels", lambda *_a, **_k: None)
    ui_inputs.render_tab_inputs()

    assert any("sources manquantes" in msg for msg in stub.errors)
    assert any(ui_inputs.CLOUD_MESSAGE in msg for msg in stub.warnings)


def test_render_tab_inputs_refresh_button_triggers_refresh(monkeypatch, tmp_path):
    stub = _StubSt()
    stub.set_button_sequence("🔄 Recharger TOUS les fichiers depuis OneDrive", [True])
    monkeypatch.setattr(ui_inputs, "st", stub)
    monkeypatch.setattr(ui_inputs, "IS_STREAMLIT_CLOUD", True)
    monkeypatch.setattr(ui_inputs, "is_graph_onedrive", lambda: True)
    state = _build_state(tmp_path)
    for p in (state.tdb_tmp, state.benev_tmp, state.vols_tmp):
        p.write_bytes(b"x")
    monkeypatch.setattr(ui_inputs, "get_state", lambda: state)
    monkeypatch.setattr(ui_inputs, "_render_graph_onedrive_auth_section", lambda: None)
    monkeypatch.setattr(ui_inputs, "_resolve_inputs_session_context", lambda: None)
    monkeypatch.setattr(ui_inputs, "_ensure_inputs_tmp_paths", lambda *_a, **_k: None)
    monkeypatch.setattr(ui_inputs, "_load_input_dataframes", lambda *_a, **_k: None)
    monkeypatch.setattr(ui_inputs, "pick_planning_dates", lambda *_a, **_k: None)
    monkeypatch.setattr(ui_inputs, "_render_inputs_panels", lambda *_a, **_k: None)
    refreshed = {"count": 0}
    monkeypatch.setattr(
        ui_inputs,
        "refresh_all",
        lambda _state: refreshed.__setitem__("count", refreshed["count"] + 1),
    )

    ui_inputs.render_tab_inputs()
    assert refreshed["count"] == 1
