# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import scheduler.config_paths as cp
from asf_app.config import session_context


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _setup_sources(tmp_path: Path) -> dict[str, Path]:
    onedrive = tmp_path / "onedrive"
    tdb_src = onedrive / "Hélida" / "TABLEAU DE BORD.xlsx"
    benev_src = onedrive / "Planning Bénévoles" / "Planning BENEVOLE.xlsx"
    vols_src = onedrive / "Planning MAB" / "Fichiers Source" / "aVols" / "Vols.xlsx"
    _write(tdb_src, "TDB")
    _write(benev_src, "BENEV")
    _write(vols_src, "VOLS")
    return {
        "onedrive": onedrive,
        "tdb": tdb_src,
        "benev": benev_src,
        "vols": vols_src,
    }


def test_create_session_context_copies_sources(tmp_path, monkeypatch):
    sources = _setup_sources(tmp_path)
    tmp_dir = tmp_path / "tmp_asf"

    monkeypatch.setenv("ASF_ONEDRIVE_ROOT", str(sources["onedrive"]))
    monkeypatch.setenv("ASF_TMP_DIR", str(tmp_dir))
    monkeypatch.setattr(cp, "USE_GRAPH_ONEDRIVE", False, raising=False)
    monkeypatch.setattr(cp, "IS_STREAMLIT_CLOUD", False, raising=False)
    monkeypatch.setattr(session_context.st, "session_state", {})

    ctx = session_context.create_session_context(strict_sources=True)

    assert ctx.tmp_dir.exists()
    assert ctx.source_paths.tableau_de_bord.exists()
    assert ctx.source_paths.planning_benevoles.exists()
    assert ctx.source_paths.vols.exists()
    assert ctx.source_paths.tableau_de_bord.read_text(encoding="utf-8") == "TDB"
    assert ctx.source_paths.planning_benevoles.read_text(encoding="utf-8") == "BENEV"
    assert ctx.source_paths.vols.read_text(encoding="utf-8") == "VOLS"


def test_refresh_session_context_updates_sources(tmp_path, monkeypatch):
    sources = _setup_sources(tmp_path)
    tmp_dir = tmp_path / "tmp_asf"

    monkeypatch.setenv("ASF_ONEDRIVE_ROOT", str(sources["onedrive"]))
    monkeypatch.setenv("ASF_TMP_DIR", str(tmp_dir))
    monkeypatch.setattr(cp, "USE_GRAPH_ONEDRIVE", False, raising=False)
    monkeypatch.setattr(cp, "IS_STREAMLIT_CLOUD", False, raising=False)
    monkeypatch.setattr(session_context.st, "session_state", {})

    ctx = session_context.ensure_session_context(strict_sources=True)
    assert ctx.source_paths.tableau_de_bord.read_text(encoding="utf-8") == "TDB"

    _write(sources["tdb"], "TDB_V2")
    new_ctx = session_context.refresh_session_context(strict_sources=True)

    assert new_ctx.session_id == ctx.session_id
    assert new_ctx.source_paths.tableau_de_bord.read_text(encoding="utf-8") == "TDB_V2"


def test_download_source_strict_raises_on_download_error(tmp_path, monkeypatch):
    target = tmp_path / "target.xlsx"
    monkeypatch.setattr(cp, "download_onedrive_file", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    session_context._download_source("/remote/file.xlsx", target, strict=False)
    assert not target.exists()

    try:
        session_context._download_source("/remote/file.xlsx", target, strict=True)
        raised = False
    except FileNotFoundError:
        raised = True
    assert raised is True


def test_copy_source_non_strict_creates_placeholder_for_missing_source(tmp_path):
    src = tmp_path / "missing.xlsx"
    dst = tmp_path / "target.xlsx"
    session_context._copy_source(src, dst, strict=False)
    assert dst.exists()


def test_copy_source_strict_raises_for_missing_source(tmp_path):
    src = tmp_path / "missing.xlsx"
    dst = tmp_path / "target.xlsx"
    try:
        session_context._copy_source(src, dst, strict=True)
        raised = False
    except FileNotFoundError:
        raised = True
    assert raised is True


def test_download_source_strict_raises_when_download_does_not_create_file(tmp_path, monkeypatch):
    dst = tmp_path / "target.xlsx"
    monkeypatch.setattr(cp, "download_onedrive_file", lambda *_a, **_k: True)
    try:
        session_context._download_source("/remote/file.xlsx", dst, strict=True)
        raised = False
    except FileNotFoundError:
        raised = True
    assert raised is True


def test_prepare_session_sources_graph_mode_uses_downloads(tmp_path):
    calls: list[tuple[str, Path, bool]] = []

    def _fake_download(remote_path: str, dst: Path, *, strict: bool):
        calls.append((remote_path, dst, strict))
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(remote_path, encoding="utf-8")

    cfg = session_context.AppConfig(
        onedrive_root=tmp_path,
        tmp_dir_base=tmp_path / "tmp",
        output_planning_dir=tmp_path / "out",
        use_graph_onedrive=True,
        is_streamlit_cloud=False,
        tableau_de_bord_src=tmp_path / "unused_tdb.xlsx",
        planning_benevoles_src=tmp_path / "unused_benev.xlsx",
        planning_benevoles_src_legacy=tmp_path / "unused_legacy.xlsx",
        vols_src=tmp_path / "unused_vols.xlsx",
        tableau_de_bord_remote="H/TDB.xlsx",
        planning_benevoles_remote="H/BENEV.xlsx",
        vols_remote="H/VOLS.xlsx",
        listes_colisage_remote_dir="",
        output_planning_remote_dir_template="Planning/{year}",
    )

    original_download = session_context._download_source
    session_context._download_source = _fake_download  # type: ignore[assignment]
    try:
        paths = session_context._prepare_session_sources(cfg, tmp_path / "session", strict_sources=True)
    finally:
        session_context._download_source = original_download  # type: ignore[assignment]

    assert paths.tableau_de_bord.exists()
    assert paths.planning_benevoles.exists()
    assert paths.vols.exists()
    assert [c[0] for c in calls] == ["H/TDB.xlsx", "H/BENEV.xlsx", "H/VOLS.xlsx"]


def test_get_session_context_returns_none_when_wrong_type(monkeypatch):
    monkeypatch.setattr(session_context.st, "session_state", {session_context.SESSION_CTX_KEY: object()})
    assert session_context.get_session_context() is None
