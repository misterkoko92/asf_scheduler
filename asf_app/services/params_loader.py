# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from loaders.universal_loader import load_and_normalize
from scheduler.column_map import (
    column_map_param_be,
    column_map_param_benev,
    column_map_param_dest,
    column_map_param_expediteur,
)
from scheduler.config_paths import (
    PLANNING_BENEVOLES,
    SHEET_PARAM_BE,
    SHEET_PARAM_BENEV,
    SHEET_PARAM_DEST,
    SHEET_PARAM_EXP,
    TABLEAU_DE_BORD,
)


def load_parameters(*, tdb_path: Path | None = None, benev_path: Path | None = None):
    tdb_use = tdb_path or TABLEAU_DE_BORD
    benev_use = benev_path or PLANNING_BENEVOLES

    df_paramdest = load_and_normalize(
        path=tdb_use,
        sheet_name=SHEET_PARAM_DEST,
        mapping=column_map_param_dest,
    )

    df_paramexp = load_and_normalize(
        path=tdb_use,
        sheet_name=SHEET_PARAM_EXP,
        mapping=column_map_param_expediteur,
    )

    df_parambenev = load_and_normalize(
        path=benev_use,
        sheet_name=SHEET_PARAM_BENEV,
        mapping=column_map_param_benev,
    )

    df_parambe = load_and_normalize(
        path=tdb_use,
        sheet_name=SHEET_PARAM_BE,
        mapping=column_map_param_be,
    )

    return df_paramdest, df_paramexp, df_parambenev, df_parambe
