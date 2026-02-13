# -*- coding: utf-8 -*-
from __future__ import annotations

import types
from pathlib import Path
from types import SimpleNamespace

import scheduler.config_paths as cp
from asf_app.config import runtime


def test_get_session_context_returns_none_when_import_fails(monkeypatch):
    fake_module = types.ModuleType("asf_app.config.session_context")
    monkeypatch.setitem(__import__("sys").modules, "asf_app.config.session_context", fake_module)

    assert runtime._get_session_context() is None


def test_runtime_falls_back_to_config_paths(monkeypatch):
    monkeypatch.setattr(runtime, "_get_session_context", lambda: None)
    assert runtime.get_tmp_dir() == cp.TMP_DIR


def test_runtime_uses_session_context_and_config_values(monkeypatch, tmp_path):
    cfg = SimpleNamespace(
        onedrive_root=tmp_path / "od",
        output_planning_dir=tmp_path / "out",
        use_graph_onedrive=True,
        tableau_de_bord_src=tmp_path / "TABLEAU_DE_BORD.xlsx",
        planning_benevoles_src=tmp_path / "PLANNING_BENEVOLES.xlsx",
        planning_benevoles_src_legacy=tmp_path / "PLANNING_BENEVOLES_LEGACY.xlsx",
        vols_src=tmp_path / "VOLS.xlsx",
        tableau_de_bord_remote="/tdb.xlsx",
        planning_benevoles_remote="/benev.xlsx",
        vols_remote="/vols.xlsx",
        listes_colisage_remote_dir="/colisage",
        output_planning_remote_dir_template="Planning/{year}",
    )
    ctx = SimpleNamespace(config=cfg, tmp_dir=tmp_path / "tmp-session")
    monkeypatch.setattr(runtime, "_get_session_context", lambda: ctx)

    assert runtime.get_tmp_dir() == ctx.tmp_dir
    assert runtime.get_onedrive_root() == cfg.onedrive_root
    assert runtime.get_output_planning_dir() == cfg.output_planning_dir
    assert runtime.is_graph_onedrive() is True
    assert runtime.get_tableau_de_bord_src() == cfg.tableau_de_bord_src
    assert runtime.get_planning_benevoles_src() == cfg.planning_benevoles_src
    assert runtime.get_planning_benevoles_src_legacy() == cfg.planning_benevoles_src_legacy
    assert runtime.get_vols_src() == cfg.vols_src
    assert runtime.get_tableau_de_bord_remote() == cfg.tableau_de_bord_remote
    assert runtime.get_planning_benevoles_remote() == cfg.planning_benevoles_remote
    assert runtime.get_vols_remote() == cfg.vols_remote
    assert runtime.get_listes_colisage_remote_dir() == cfg.listes_colisage_remote_dir
    assert runtime.get_output_remote_dir_template() == cfg.output_planning_remote_dir_template
    assert runtime.get_output_remote_dir(2026) == "Planning/2026"
    assert runtime.get_output_remote_path(2026, "Planning.xlsx") == "Planning/2026/Planning.xlsx"


def test_runtime_output_remote_path_strips_leading_slash(monkeypatch):
    monkeypatch.setattr(runtime, "get_output_remote_dir", lambda _year: "/Planning/Exports/2026/")
    assert runtime.get_output_remote_path(2026, "Planning.xlsx") == "Planning/Exports/2026/Planning.xlsx"


def test_runtime_get_app_config_returns_none_without_context(monkeypatch):
    monkeypatch.setattr(runtime, "_get_session_context", lambda: None)
    assert runtime.get_app_config() is None


def test_runtime_get_tmp_dir_returns_path_instance(monkeypatch, tmp_path):
    ctx = SimpleNamespace(config=None, tmp_dir=tmp_path / "session-tmp")
    monkeypatch.setattr(runtime, "_get_session_context", lambda: ctx)
    out = runtime.get_tmp_dir()
    assert isinstance(out, Path)
    assert out == tmp_path / "session-tmp"
