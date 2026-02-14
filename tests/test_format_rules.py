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


def test_private_helpers_handle_edge_cases():
    class _BadStr:
        def __str__(self):
            raise ValueError("boom")

    assert fr._to_str(None) == ""
    assert fr._to_str(_BadStr()) == ""
    assert fr._digits("AF 0652") == "0652"
    assert fr._to_datetime(float("nan")) is None
    assert fr._to_datetime(datetime(2026, 1, 23, 10, 0)).year == 2026


def test_format_be_numero_rejects_negative_or_invalid_suffix():
    assert fr.format_be_numero("-1", datetime(2025, 1, 23), None) == (None, None)
    assert fr.format_be_numero("abc", datetime(2025, 1, 23), None) == (None, None)


def test_format_flight_number_returns_company_when_number_not_positive():
    assert fr.format_flight_number("AF", "0000") == "AF"
    assert fr.format_flight_number("AF", "ABC") == "AF"


def test_format_date_supports_long_and_default():
    val = datetime(2026, 1, 19)  # Monday
    assert fr.format_date(val, mode="long").startswith("LUN ")
    assert fr.format_date(val) == "19/01/2026"


def test_communication_wrappers_delegate_to_identifier_and_datetime_helpers():
    assert fr.format_be_number("250001") == "250001"
    assert fr.format_vol_number("AF652") == "652"
    assert fr.format_be_display("250001").startswith("BE ")
    assert fr.format_vol_display("652").startswith("AF ")
    assert fr.format_date_fr_long_slash("2026-01-19").startswith("Lundi")
    assert fr.format_date_fr_words("2026-01-19").startswith("Lundi")
    assert fr.format_heure_hh_mm("10:05") == "10h05"


def test_infer_be_year_falls_back_to_current_year(monkeypatch):
    class _FakeDateTime(datetime):
        @classmethod
        def today(cls):
            return cls(2030, 1, 1)

    monkeypatch.setattr(fr, "datetime", _FakeDateTime)
    assert fr.infer_be_year(None, None) == 2030


def test_extract_be_suffix_handles_empty_nan_and_none():
    assert fr.extract_be_suffix("") is None
    assert fr.extract_be_suffix("nan") is None
    assert fr.extract_be_suffix(None) is None


def test_to_dt_handles_objects_with_to_pydatetime_and_invalid():
    ts = pd.Timestamp("2026-01-23 10:00:00")
    assert fr._to_dt(ts) == ts.to_pydatetime()
    assert fr._to_dt(None) is None
    assert fr._to_dt("invalid") is None


def test_private_datetime_helpers_handle_internal_exceptions(monkeypatch):
    monkeypatch.setattr(fr, "coerce_datetime", lambda *_a, **_k: (_ for _ in ()).throw(OverflowError("boom")))
    assert fr._to_datetime("bad") is None
    assert fr._to_dt("bad") is None


def test_to_dt_handles_bad_to_pydatetime_then_falls_back(monkeypatch):
    class _BadTs:
        def to_pydatetime(self):
            raise ValueError("boom")

    monkeypatch.setattr(fr, "coerce_datetime", lambda *_a, **_k: pd.Timestamp("2026-01-23 11:00:00"))
    out = fr._to_dt(_BadTs())
    assert out == datetime(2026, 1, 23, 11, 0)


def test_format_flight_number_handles_non_int_digits_object(monkeypatch):
    class _BadInt:
        def __int__(self):
            raise TypeError("boom")

    monkeypatch.setattr(fr, "_digits", lambda _v: _BadInt())
    assert fr.format_flight_number("AF", "ignored") == "AF"


def test_to_datetime_returns_none_when_coerce_returns_nat(monkeypatch):
    monkeypatch.setattr(fr, "coerce_datetime", lambda *_a, **_k: pd.NaT)
    assert fr._to_datetime("bad-date") is None


def test_to_datetime_returns_raw_object_without_to_pydatetime(monkeypatch):
    class _RawDatetime:
        pass

    raw = _RawDatetime()
    monkeypatch.setattr(fr, "coerce_datetime", lambda *_a, **_k: raw)
    monkeypatch.setattr(fr.pd, "isna", lambda _v: False)
    assert fr._to_datetime("bad-date") is raw
