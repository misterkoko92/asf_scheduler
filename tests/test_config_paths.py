# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

import scheduler.config_paths as cp


def _build_runtime(tmp_path: Path) -> cp.RuntimePaths:
    return cp.RuntimePaths(
        asf_onedrive=tmp_path / "onedrive",
        tableau_de_bord_src=tmp_path / "src_tdb.xlsx",
        planning_benevoles_src=tmp_path / "src_benev.xlsx",
        planning_benevoles_src_legacy=tmp_path / "src_benev_legacy.xlsx",
        vols_src=tmp_path / "src_vols.xlsx",
        tmp_dir=tmp_path / "tmp",
        tableau_de_bord=tmp_path / "tmp" / "TABLEAU_DE_BORD.xlsx",
        planning_benevoles=tmp_path / "tmp" / "PLANNING_BENEVOLES.xlsx",
        vols=tmp_path / "tmp" / "VOLS.xlsx",
        output_planning_dir=tmp_path / "out",
        output_planning=tmp_path / "out" / "Planning.xlsx",
        output_bilan=tmp_path / "out" / "Bilan.xlsx",
        planning_template=tmp_path / "Planning_TEMPLATE.xlsx",
        planning_maquette_onedrive=tmp_path / "Planning-maquette.xlsx",
        tableau_de_bord_remote="H/TDB.xlsx",
        planning_benevoles_remote="H/BENEV.xlsx",
        vols_remote="H/VOLS.xlsx",
        output_planning_remote_dir_template="Planning/{year}",
    )


def test_prepare_paths_creates_tmp_files(tmp_path, monkeypatch):
    tmp_dir = tmp_path / "tmp_asf"
    out_dir = tmp_path / "out"

    monkeypatch.setenv("ASF_TMP_DIR", str(tmp_dir))
    monkeypatch.setattr(cp, "OUTPUT_PLANNING_DIR", out_dir)
    monkeypatch.setattr(cp, "ASF_ONEDRIVE", tmp_path)

    runtime = cp.prepare_paths(copy_sources=False)

    assert tmp_dir.exists()
    assert (tmp_dir / "TABLEAU_DE_BORD.xlsx").exists()
    assert (tmp_dir / "PLANNING_BENEVOLES.xlsx").exists()
    assert (tmp_dir / "VOLS.xlsx").exists()
    assert runtime.tmp_dir == tmp_dir


def test_prepare_paths_strict_missing_raises(tmp_path, monkeypatch):
    tmp_dir = tmp_path / "tmp_asf"
    out_dir = tmp_path / "out"
    onedrive_root = tmp_path / "onedrive_missing"

    monkeypatch.setenv("ASF_TMP_DIR", str(tmp_dir))
    monkeypatch.setenv("ASF_ONEDRIVE_ROOT", str(onedrive_root))
    monkeypatch.setattr(cp, "OUTPUT_PLANNING_DIR", out_dir)
    monkeypatch.setattr(cp, "USE_GRAPH_ONEDRIVE", False, raising=False)
    monkeypatch.setattr(cp, "IS_STREAMLIT_CLOUD", False, raising=False)

    with pytest.raises(FileNotFoundError):
        cp.prepare_paths(copy_sources=True, strict_sources=True)


def test_runtime_paths_snapshot_is_immutable():
    runtime = cp.get_runtime_paths()
    assert runtime.tableau_de_bord_src == cp.TABLEAU_DE_BORD_SRC
    with pytest.raises(FrozenInstanceError):
        runtime.tmp_dir = Path("/tmp/other")


def test_get_output_remote_helpers_accept_runtime_snapshot():
    runtime = cp.get_runtime_paths()
    expected_dir = runtime.output_planning_remote_dir_template.format(year=2026)
    assert cp.get_output_remote_dir(2026, runtime=runtime) == expected_dir
    assert cp.get_output_remote_path(2026, "Planning.xlsx", runtime=runtime).endswith(
        "/Planning.xlsx"
    )


def test_remote_path_for_local_uses_runtime_snapshot(tmp_path):
    runtime = _build_runtime(tmp_path)
    runtime.tableau_de_bord.parent.mkdir(parents=True, exist_ok=True)
    runtime.tableau_de_bord.touch()
    runtime.planning_benevoles.touch()
    runtime.vols.touch()

    assert (
        cp.remote_path_for_local(runtime.tableau_de_bord, runtime=runtime)
        == "H/TDB.xlsx"
    )
    assert (
        cp.remote_path_for_local(runtime.planning_benevoles, runtime=runtime)
        == "H/BENEV.xlsx"
    )
    assert cp.remote_path_for_local(runtime.vols, runtime=runtime) == "H/VOLS.xlsx"


def test_cleanup_tmp_uses_runtime_snapshot(tmp_path):
    runtime = _build_runtime(tmp_path)
    runtime.tmp_dir.mkdir(parents=True, exist_ok=True)
    (runtime.tmp_dir / "a.txt").write_text("x", encoding="utf-8")
    (runtime.tmp_dir / "sub").mkdir()
    (runtime.tmp_dir / "sub" / "b.txt").write_text("y", encoding="utf-8")

    cp.cleanup_tmp(runtime=runtime)

    assert runtime.tmp_dir.exists()
    assert list(runtime.tmp_dir.iterdir()) == []


def test_ensure_tmp_up_to_date_uses_runtime_snapshot(tmp_path, monkeypatch):
    runtime = _build_runtime(tmp_path)
    calls: list[tuple[bool, bool, cp.RuntimePaths | None]] = []

    def _fake_prepare_paths(
        copy_sources: bool = True,
        *,
        strict_sources: bool = False,
        runtime: cp.RuntimePaths | None = None,
    ):
        calls.append((copy_sources, strict_sources, runtime))
        return runtime if runtime is not None else cp.get_runtime_paths()

    monkeypatch.setattr(cp, "prepare_paths", _fake_prepare_paths)

    cp.ensure_tmp_up_to_date(runtime=runtime)
    assert calls == [(True, False, runtime)]


def test_sync_local_file_to_onedrive_uses_runtime_snapshot(tmp_path, monkeypatch):
    runtime = replace(_build_runtime(tmp_path), use_graph_onedrive=True)
    runtime.vols.parent.mkdir(parents=True, exist_ok=True)
    runtime.vols.touch()

    captured: dict[str, object] = {}

    def _fake_upload(local_path: Path, remote_path: str, **_kwargs):
        captured["local"] = local_path
        captured["remote"] = remote_path
        return True

    monkeypatch.setattr(cp, "USE_GRAPH_ONEDRIVE", True, raising=False)
    monkeypatch.setattr(cp, "upload_onedrive_file", _fake_upload)

    ok = cp.sync_local_file_to_onedrive(runtime.vols, runtime=runtime)

    assert ok is True
    assert captured["local"] == runtime.vols
    assert captured["remote"] == "H/VOLS.xlsx"


def test_prepare_paths_accepts_runtime_snapshot(tmp_path):
    runtime = _build_runtime(tmp_path)
    prepared = cp.prepare_paths(copy_sources=False, runtime=runtime)
    assert prepared.tmp_dir == runtime.tmp_dir
    assert prepared.tableau_de_bord.exists()
    assert prepared.planning_benevoles.exists()
    assert prepared.vols.exists()


def test_get_graph_client_uses_runtime_cache_key(tmp_path, monkeypatch):
    runtime1 = replace(
        _build_runtime(tmp_path),
        use_graph_onedrive=True,
        graph_client_id="client",
        graph_tenant_id="tenant",
        graph_scopes=("scope1",),
        graph_token_cache=tmp_path / "cache-a.json",
    )
    runtime2 = replace(runtime1, graph_token_cache=tmp_path / "cache-b.json")
    calls: list[Path] = []

    def _fake_build_graph_client(*, runtime=None):
        assert runtime is not None
        calls.append(runtime.graph_token_cache)
        return {"cache": runtime.graph_token_cache}

    monkeypatch.setattr(cp, "_GRAPH_CLIENTS", {})
    monkeypatch.setattr(cp, "_build_graph_client", _fake_build_graph_client)

    c1 = cp.get_graph_client(runtime=runtime1)
    c1_again = cp.get_graph_client(runtime=runtime1)
    c2 = cp.get_graph_client(runtime=runtime2)

    assert c1 is c1_again
    assert c1 is not c2
    assert calls == [runtime1.graph_token_cache, runtime2.graph_token_cache]


def test_print_config_paths_uses_logger(tmp_path, caplog):
    runtime = _build_runtime(tmp_path)
    caplog.set_level("INFO", logger="ASF-SCHEDULER")

    cp.print_config_paths(runtime=runtime)

    assert "=== CONFIG PATHS ===" in caplog.text
    assert str(runtime.asf_onedrive) in caplog.text


def test_download_to_tmp_creates_placeholder_when_download_fails(tmp_path, monkeypatch):
    runtime = _build_runtime(tmp_path)

    def _raise(*args, **kwargs):
        raise RuntimeError("download failed")

    monkeypatch.setattr(cp, "download_onedrive_file", _raise)

    out = cp._download_to_tmp("H/TDB.xlsx", "TABLEAU_DE_BORD.xlsx", strict=False, runtime=runtime)

    assert out.exists()
    assert out.name == "TABLEAU_DE_BORD.xlsx"


def test_download_to_tmp_strict_raises_when_download_fails(tmp_path, monkeypatch):
    runtime = _build_runtime(tmp_path)

    def _raise(*args, **kwargs):
        raise RuntimeError("download failed")

    monkeypatch.setattr(cp, "download_onedrive_file", _raise)

    with pytest.raises(FileNotFoundError):
        cp._download_to_tmp("H/TDB.xlsx", "TABLEAU_DE_BORD.xlsx", strict=True, runtime=runtime)


def test_copy_to_tmp_non_strict_uses_placeholder_on_copy_error(tmp_path, monkeypatch):
    runtime = _build_runtime(tmp_path)
    src = tmp_path / "source.xlsx"
    src.write_text("x", encoding="utf-8")

    def _raise(*args, **kwargs):
        raise OSError("copy failed")

    monkeypatch.setattr(cp.shutil, "copy2", _raise)

    out = cp._copy_to_tmp(src, "TABLEAU_DE_BORD.xlsx", strict=False, runtime=runtime)

    assert out.exists()
    assert out.name == "TABLEAU_DE_BORD.xlsx"
