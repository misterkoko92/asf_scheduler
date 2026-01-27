# -*- coding: utf-8 -*-
from __future__ import annotations

from asf_app.services.params_loader import load_parameters


def test_load_parameters(sample_onedrive):
    df_paramdest, df_paramexp, df_parambenev, df_parambe = load_parameters()
    assert not df_paramdest.empty
    assert df_paramexp is not None
    assert not df_parambenev.empty
    assert not df_parambe.empty
