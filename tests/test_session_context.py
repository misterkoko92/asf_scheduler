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
