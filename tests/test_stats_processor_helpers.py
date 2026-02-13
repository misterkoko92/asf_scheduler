# -*- coding: utf-8 -*-
from __future__ import annotations

import pandas as pd
import pytest

pytest.importorskip("reportlab")
from asf_app.ui.ui_stats import stats_processor as sp  # noqa: E402


def test_compute_transfer_delay_returns_empty_when_invalid():
    df = pd.DataFrame(
        {
            "date": ["not-a-date"],
            "heure": ["bad-time"],
            "date_transfert": ["also-bad"],
        }
    )

    out = sp.compute_transfer_delay(df)

    assert isinstance(out, pd.Series)
    assert out.empty or out.isna().all()
