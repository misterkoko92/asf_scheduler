# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from asf_app.config.paths import AppPaths
import scheduler.config_paths as cp


def test_app_paths_sync_to_engine(tmp_path):
    tdb = tmp_path / "TABLEAU_DE_BORD.xlsx"
    benev = tmp_path / "PLANNING_BENEVOLES.xlsx"
    vols = tmp_path / "VOLS.xlsx"
    for p in (tdb, benev, vols):
        p.touch()

    paths = AppPaths(tdb=tdb, benev=benev, vols=vols)
    paths.sync_to_engine()

    assert Path(cp.TABLEAU_DE_BORD) == tdb
    assert Path(cp.PLANNING_BENEVOLES) == benev
    assert Path(cp.VOLS) == vols
