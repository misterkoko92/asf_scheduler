# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import scheduler.config_paths as cp


def test_prepare_paths_creates_tmp_files(tmp_path, monkeypatch):
    tmp_dir = tmp_path / "tmp_asf"
    out_dir = tmp_path / "out"

    monkeypatch.setenv("ASF_TMP_DIR", str(tmp_dir))
    monkeypatch.setattr(cp, "OUTPUT_PLANNING_DIR", out_dir)
    monkeypatch.setattr(cp, "ASF_ONEDRIVE", tmp_path)

    cp.prepare_paths(copy_sources=False)

    assert tmp_dir.exists()
    assert (tmp_dir / "TABLEAU_DE_BORD.xlsx").exists()
    assert (tmp_dir / "PLANNING_BENEVOLES.xlsx").exists()
    assert (tmp_dir / "VOLS.xlsx").exists()
