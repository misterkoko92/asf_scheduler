# -*- coding: utf-8 -*-
from __future__ import annotations

from utils.ui_helpers import format_vol_label


class _BadDate:
    def weekday(self):
        raise ValueError("boom")

    def strftime(self, fmt):
        return "01/01/26"


def test_format_vol_label_tolerates_weekday_failure():
    label = format_vol_label(_BadDate(), "RUN", "652", "18h20", "CDG-RUN", "planned")
    assert "AF 652" in label
    assert "RUN" in label
