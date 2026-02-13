# -*- coding: utf-8 -*-
from __future__ import annotations

from utils.identifiers import (
    digits_only,
    format_be_display,
    format_vol_display,
    normalize_be_int,
    normalize_be_number,
    normalize_vol_number,
)


def test_digits_only_strips_non_digits():
    assert digits_only("BE 24 1234") == "241234"
    assert digits_only("AF-007") == "007"
    assert digits_only(None) == ""


def test_normalize_be_number_pads_and_truncates():
    assert normalize_be_number("1234") == "001234"
    assert normalize_be_number("BE 24 1234") == "241234"
    assert normalize_be_number("20241234") == "241234"
    assert normalize_be_number("") == ""


def test_normalize_vol_number_removes_leading_zeros():
    assert normalize_vol_number("AF 0007") == "7"
    assert normalize_vol_number("0007") == "7"
    assert normalize_vol_number("AF 718") == "718"
    assert normalize_vol_number("") == ""


def test_display_helpers():
    assert format_be_display("1234") == "BE 001234"
    assert format_vol_display("AF 0007") == "AF 7"
    assert format_vol_display("7") == "AF 7"


def test_normalize_be_int_handles_invalid_values():
    assert normalize_be_int("250001.0") == 250001
    assert normalize_be_int("invalid") is None
