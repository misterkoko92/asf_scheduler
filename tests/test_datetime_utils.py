import warnings

import pandas as pd

from utils.datetime_utils import (
    coerce_datetime,
    parse_date_series,
    parse_time_series,
    normalize_hour_str,
    hour_min_from_series,
)


def test_parse_date_series_formats():
    ser = pd.Series(["15/12/25", "16/12/2025", "2025-12-17"])
    parsed = parse_date_series(ser)
    assert parsed.dt.year.tolist() == [2025, 2025, 2025]
    assert parsed.dt.month.tolist() == [12, 12, 12]
    assert parsed.dt.day.tolist() == [15, 16, 17]


def test_parse_date_series_no_dayfirst_false():
    ser = pd.Series(["01/02/25"])
    parsed = parse_date_series(ser, allow_dayfirst_false=False)
    assert parsed.dt.day.tolist()[0] == 1
    assert parsed.dt.month.tolist()[0] == 2


def test_parse_time_series_and_normalize():
    ser = pd.Series(["10h00", "18:20", "07:05:00", ""])
    parsed = parse_time_series(ser)
    assert parsed.dt.hour.tolist()[:3] == [10, 18, 7]
    norm = normalize_hour_str(ser)
    assert norm.tolist()[:3] == ["10h00", "18h20", "07h05"]


def test_hour_min_from_series():
    ser = pd.Series(["00h00", "01h30", "18:20"])
    mins = hour_min_from_series(ser)
    assert mins.tolist() == [0, 90, 1100]


def test_parse_time_series_numeric_excel():
    ser = pd.Series([0.5, 0.25, None])
    parsed = parse_time_series(ser)
    assert parsed.dt.hour.tolist()[:2] == [12, 6]
    assert parsed.dt.minute.tolist()[:2] == [0, 0]


def test_parse_time_series_hour_only_string():
    ser = pd.Series(["10"])
    parsed = parse_time_series(ser, allow_hour_only=True)
    assert parsed.dt.hour.tolist()[0] == 10
    assert parsed.dt.minute.tolist()[0] == 0


def test_parse_date_series_dayfirst_iso_emits_no_warning():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        parsed = parse_date_series(pd.Series(["2026-01-23"]))
    assert str(parsed.iloc[0].date()) == "2026-01-23"
    assert not any(
        "Parsing dates in %Y-%m-%d format when dayfirst=True was specified."
        in str(w.message)
        for w in caught
    )


def test_coerce_datetime_dayfirst_iso_emits_no_warning():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        parsed = coerce_datetime("2026-01-23", errors="coerce", dayfirst=True)
    assert str(parsed.date()) == "2026-01-23"
    assert not any(
        "Parsing dates in %Y-%m-%d format when dayfirst=True was specified."
        in str(w.message)
        for w in caught
    )
