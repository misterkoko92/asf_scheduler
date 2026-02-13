# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime

import pandas as pd

import scheduler.format_rules as fr


def test_extract_be_suffix_and_format_be_numero():
    assert fr.extract_be_suffix("4") == 4
    assert fr.extract_be_suffix("4.0") == 4
    assert fr.extract_be_suffix("abc") is None

    num, suffix = fr.format_be_numero("4", datetime(2025, 1, 23), None)
    assert num == "250004"
    assert suffix == "0004"


def test_infer_be_year_priority_chain():
    assert fr.infer_be_year(pd.Timestamp("2026-01-23"), pd.Timestamp("2025-01-01")) == 2026
    assert fr.infer_be_year(None, pd.Timestamp("2025-01-01")) == 2025


def test_format_flight_number_and_date_helpers(monkeypatch):
    assert fr.format_flight_number("af", "0652") == "AF652"
    assert fr.format_flight_number("af", "x") == "AF"

    assert fr.format_date("2026-01-23", mode="short") == "23/01"
    assert fr.format_date("2026-01-23", mode="iso") == "2026-01-23"

    monkeypatch.setattr(fr, "coerce_datetime", lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("boom")))
    assert fr.format_date("bad-date") == ""
