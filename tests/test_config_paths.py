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


def test_get_planning_dirs_and_maquette_path(tmp_path):
    runtime = _build_runtime(tmp_path)
    planning_mab = runtime.asf_onedrive / "Planning MAB"
    year_dir = planning_mab / "ASFmm PLANNING 2026"
    other_dir = planning_mab / "ASFmm PLANNING 2025"
    planning_mab.mkdir(parents=True, exist_ok=True)
    year_dir.mkdir(parents=True, exist_ok=True)
    other_dir.mkdir(parents=True, exist_ok=True)
    runtime.output_planning_dir.mkdir(parents=True, exist_ok=True)
    runtime.planning_template.parent.mkdir(parents=True, exist_ok=True)
    runtime.planning_template.write_text("tpl", encoding="utf-8")

    dirs = cp.get_planning_dirs(year=2026, runtime=runtime)
    assert dirs[0] == year_dir.resolve()
    assert runtime.output_planning_dir.resolve() in dirs

    # Sans maquette OneDrive, fallback template
    assert cp.get_planning_maquette_path(runtime=runtime) == runtime.planning_template


def test_get_planning_maquette_prefers_onedrive_file(tmp_path):
    runtime = _build_runtime(tmp_path)
    runtime.planning_maquette_onedrive.parent.mkdir(parents=True, exist_ok=True)
    runtime.planning_maquette_onedrive.write_text("onedrive", encoding="utf-8")
    assert cp.get_planning_maquette_path(runtime=runtime) == runtime.planning_maquette_onedrive


def test_remote_path_for_local_unknown_path_returns_none(tmp_path):
    runtime = _build_runtime(tmp_path)
    unknown = tmp_path / "other.xlsx"
    unknown.write_text("x", encoding="utf-8")
    assert cp.remote_path_for_local(unknown, runtime=runtime) is None


def test_sync_local_file_to_onedrive_returns_false_when_not_graph(tmp_path):
    runtime = replace(_build_runtime(tmp_path), use_graph_onedrive=False)
    assert cp.sync_local_file_to_onedrive(tmp_path / "x.xlsx", runtime=runtime) is False


def test_sync_local_file_to_onedrive_returns_false_when_remote_cannot_be_resolved(tmp_path):
    runtime = replace(_build_runtime(tmp_path), use_graph_onedrive=True)
    local = tmp_path / "other.xlsx"
    local.write_text("x", encoding="utf-8")
    assert cp.sync_local_file_to_onedrive(local, runtime=runtime) is False


def test_device_flow_helpers_return_none_or_false_when_no_client(monkeypatch):
    monkeypatch.setattr(cp, "get_graph_client", lambda **_kwargs: None)
    assert cp.begin_onedrive_device_flow() is None
    assert cp.complete_onedrive_device_flow({}) is False


def test_download_upload_list_helpers_handle_non_graph_or_auth_required(tmp_path, monkeypatch):
    runtime = replace(_build_runtime(tmp_path), use_graph_onedrive=False)
    assert cp.download_onedrive_file("A/B.xlsx", tmp_path / "x.xlsx", runtime=runtime) is False
    assert cp.upload_onedrive_file(tmp_path / "x.xlsx", "A/B.xlsx", runtime=runtime) is False
    assert cp.list_onedrive_files("A", runtime=runtime) == []

    runtime_graph = replace(_build_runtime(tmp_path), use_graph_onedrive=True)
    from scheduler.onedrive_graph import GraphAuthRequired

    class _FakeClient:
        def download_file(self, *_args, **_kwargs):
            raise GraphAuthRequired("auth")

        def upload_file(self, *_args, **_kwargs):
            raise GraphAuthRequired("auth")

        def list_files_recursive(self, *_args, **_kwargs):
            raise GraphAuthRequired("auth")

    monkeypatch.setattr(cp, "get_graph_client", lambda **_kwargs: _FakeClient())

    assert cp.download_onedrive_file("A/B.xlsx", tmp_path / "x.xlsx", runtime=runtime_graph) is False
    assert cp.upload_onedrive_file(tmp_path / "x.xlsx", "A/B.xlsx", runtime=runtime_graph) is False
    assert cp.list_onedrive_files("A", recursive=True, runtime=runtime_graph) == []


def test_detect_onedrive_asf_handles_env_override_and_fallbacks(tmp_path, monkeypatch):
    env_root = tmp_path / "env_root"
    monkeypatch.setenv("ASF_ONEDRIVE_ROOT", str(env_root))
    assert cp.detect_onedrive_asf() == env_root.resolve()

    monkeypatch.delenv("ASF_ONEDRIVE_ROOT", raising=False)
    monkeypatch.setattr(cp.Path, "home", lambda: tmp_path)
    (tmp_path / "OneDrive").mkdir(parents=True, exist_ok=True)
    assert cp.detect_onedrive_asf() == (tmp_path / "OneDrive").resolve()

    (tmp_path / "OneDrive").rmdir()
    assert cp.detect_onedrive_asf() == tmp_path.resolve()


def test_download_and_copy_to_tmp_tolerate_placeholder_touch_errors(tmp_path, monkeypatch):
    runtime = _build_runtime(tmp_path)
    monkeypatch.setattr(cp, "download_onedrive_file", lambda *_a, **_k: False)
    monkeypatch.setattr(cp.Path, "touch", lambda *_a, **_k: (_ for _ in ()).throw(OSError("boom")))

    out_dl = cp._download_to_tmp("H/TDB.xlsx", "TABLEAU_DE_BORD.xlsx", strict=False, runtime=runtime)
    out_cp = cp._copy_to_tmp(tmp_path / "missing.xlsx", "PLANNING_BENEVOLES.xlsx", strict=False, runtime=runtime)
    assert out_dl.name == "TABLEAU_DE_BORD.xlsx"
    assert out_cp.name == "PLANNING_BENEVOLES.xlsx"


def test_prepare_paths_graph_mode_downloads_all_sources(tmp_path, monkeypatch):
    runtime = replace(_build_runtime(tmp_path), use_graph_onedrive=True, is_streamlit_cloud=False)
    calls: list[str] = []

    def _fake_download(remote_path, dst_name, *, strict=False, runtime=None):
        _ = strict, runtime
        calls.append(str(remote_path))
        dst = (tmp_path / "tmp") / dst_name
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text("x", encoding="utf-8")
        return dst.resolve()

    monkeypatch.setenv("ASF_OUTPUT_DIR", str(tmp_path / "graph_output"))
    monkeypatch.setattr(cp, "_download_to_tmp", _fake_download)

    prepared = cp.prepare_paths(copy_sources=True, runtime=runtime)
    assert calls == [runtime.tableau_de_bord_remote, runtime.planning_benevoles_remote, runtime.vols_remote]
    assert prepared.tableau_de_bord_src == prepared.tableau_de_bord
    assert prepared.planning_benevoles_src == prepared.planning_benevoles
    assert prepared.vols_src == prepared.vols


def test_prepare_paths_local_mode_uses_legacy_benev_when_main_missing(tmp_path, monkeypatch):
    runtime = replace(_build_runtime(tmp_path), use_graph_onedrive=False, is_streamlit_cloud=False)
    runtime.tableau_de_bord_src.parent.mkdir(parents=True, exist_ok=True)
    runtime.tableau_de_bord_src.write_text("x", encoding="utf-8")
    runtime.vols_src.write_text("x", encoding="utf-8")
    runtime.planning_benevoles_src_legacy.parent.mkdir(parents=True, exist_ok=True)
    runtime.planning_benevoles_src_legacy.write_text("x", encoding="utf-8")

    copied_sources: list[Path] = []

    def _fake_copy(src, dst_name, *, strict=False, runtime=None):
        _ = strict, runtime
        copied_sources.append(Path(src))
        dst = (tmp_path / "tmp") / dst_name
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text("x", encoding="utf-8")
        return dst.resolve()

    monkeypatch.setattr(cp, "_copy_to_tmp", _fake_copy)
    cp.prepare_paths(copy_sources=True, runtime=runtime)
    assert runtime.planning_benevoles_src_legacy in copied_sources


def test_cleanup_tmp_handles_missing_dir_and_errors(tmp_path, monkeypatch):
    runtime_missing = _build_runtime(tmp_path / "missing_case")
    cp.cleanup_tmp(runtime=runtime_missing)

    runtime = _build_runtime(tmp_path / "existing_case")
    runtime.tmp_dir.mkdir(parents=True, exist_ok=True)
    (runtime.tmp_dir / "f.txt").write_text("x", encoding="utf-8")
    (runtime.tmp_dir / "sub").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(cp.Path, "unlink", lambda *_a, **_k: (_ for _ in ()).throw(OSError("boom")))
    monkeypatch.setattr(cp.shutil, "rmtree", lambda *_a, **_k: (_ for _ in ()).throw(OSError("boom")))
    cp.cleanup_tmp(runtime=runtime)


def test_graph_client_builder_and_device_flow_success(tmp_path, monkeypatch):
    runtime_missing = _build_runtime(tmp_path)
    assert cp._build_graph_client(runtime=runtime_missing) is None

    class _DummyConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class _DummyClient:
        def __init__(self, cfg):
            self.cfg = cfg
            self.completed_flow = None

        def begin_device_flow(self):
            return {"user_code": "ABC123"}

        def complete_device_flow(self, flow):
            self.completed_flow = flow

    runtime_ok = replace(
        _build_runtime(tmp_path),
        graph_client_id="cid",
        graph_tenant_id="tid",
        graph_scopes=("scope1",),
        graph_token_cache=tmp_path / "cache.json",
    )
    monkeypatch.setattr("scheduler.onedrive_graph.GraphConfig", _DummyConfig)
    monkeypatch.setattr("scheduler.onedrive_graph.OneDriveGraphClient", _DummyClient)
    built = cp._build_graph_client(runtime=runtime_ok)
    assert isinstance(built, _DummyClient)
    assert built.cfg.kwargs["tenant_id"] == "tid"

    monkeypatch.setattr(cp, "get_graph_client", lambda **_kwargs: built)
    flow = cp.begin_onedrive_device_flow(runtime=runtime_ok)
    assert flow == {"user_code": "ABC123"}
    assert cp.complete_onedrive_device_flow(flow, runtime=runtime_ok) is True


def test_download_upload_list_return_empty_when_graph_client_absent(tmp_path, monkeypatch):
    runtime_graph = replace(_build_runtime(tmp_path), use_graph_onedrive=True)
    monkeypatch.setattr(cp, "get_graph_client", lambda **_kwargs: None)
    assert cp.download_onedrive_file("A/B.xlsx", tmp_path / "x.xlsx", runtime=runtime_graph) is False
    assert cp.upload_onedrive_file(tmp_path / "x.xlsx", "A/B.xlsx", runtime=runtime_graph) is False
    assert cp.list_onedrive_files("A", runtime=runtime_graph) == []


def test_list_onedrive_files_non_recursive_adds_item_paths(tmp_path, monkeypatch):
    runtime_graph = replace(_build_runtime(tmp_path), use_graph_onedrive=True)

    class _Client:
        def list_children(self, remote_dir, interactive=False):
            _ = interactive
            return [{"name": "planning.xlsx"}, {"name": "nested"}]

    monkeypatch.setattr(cp, "get_graph_client", lambda **_kwargs: _Client())
    out = cp.list_onedrive_files("Planning/2026", recursive=False, runtime=runtime_graph)
    assert out[0]["path"] == "Planning/2026/planning.xlsx"
    assert out[1]["path"] == "Planning/2026/nested"
