# -*- coding: utf-8 -*-
from __future__ import annotations

import pandas as pd

from loaders.load_params import load_param_benev_from_path


def test_parambenev_loads_max_colis_vol(tmp_path):
    path = tmp_path / "benev.xlsx"
    df = pd.DataFrame(
        [
            {
                "ID": "1",
                "BENEVOLE": "TEST",
                "MAX_COLIS_VOL": "30",
            }
        ]
    )
    df.to_excel(path, sheet_name="ParamBenev", index=False)

    out = load_param_benev_from_path(path)
    assert "Max_Colis_Vol" in out.columns
    assert int(out["Max_Colis_Vol"].iloc[0]) == 30
