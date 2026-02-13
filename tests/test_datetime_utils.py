import datetime as dt
import warnings

import pandas as pd

from utils.datetime_utils import (
    coerce_datetime,
    format_date_long_fr,
    format_date_value,
    format_time_hm_loose,
    format_time_value,
    hour_min_from_series,
    hour_min_value,
    normalize_hour_str,
    normalize_hour_value,
    parse_date_long_fr,
    parse_date_series,
    parse_date_value_as_date,
    parse_iso_date_value,
    parse_iso_datetime,
    parse_time_series,
    parse_time_value_as_time,
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


def test_parse_iso_datetime_handles_z_suffix_and_invalid():
    dt_ok = parse_iso_datetime("2026-01-23T10:15:00Z")
    assert dt_ok is not None
    assert dt_ok.isoformat() == "2026-01-23T10:15:00+00:00"
    assert parse_iso_datetime("not-a-date") is None


def test_parse_time_value_as_time_supports_decimal_hours():
    t = parse_time_value_as_time(14.5)
    assert t is not None
    assert t.hour == 14
    assert t.minute == 30
    assert parse_time_value_as_time("xx") is None


def test_parse_date_long_fr_fallback_and_format_time_value():
    parsed = parse_date_long_fr("Lundi 01/12", default_year=2026)
    assert str(parsed.date()) == "2026-12-01"
    assert format_date_long_fr("01/12/26") == "Mardi 01/12/26"
    assert format_time_value("10:05") == "10h05"


def test_parse_iso_date_value_and_parse_date_value_as_date():
    assert str(parse_iso_date_value("2026-01-23T10:00:00Z")) == "2026-01-23"
    assert parse_iso_date_value("bad") is None
    assert str(parse_date_value_as_date("23/01/26")) == "2026-01-23"
    assert parse_date_value_as_date("bad") is None


def test_format_date_value_and_format_time_hm_loose_defaults():
    assert format_date_value("bad", default="N/A") == "N/A"
    assert format_date_value("bad", default=None) == "bad"
    assert format_time_hm_loose("10h30") == "10:30"
    assert format_time_hm_loose("  ") == ""


def test_normalize_hour_value_and_hour_min_value_wrappers():
    assert normalize_hour_value("07", allow_hour_only=True) == "07h00"
    assert normalize_hour_value("invalid") == ""
    assert hour_min_value("07", allow_hour_only=True) == 420
    assert hour_min_value("invalid") is None


def test_parse_iso_datetime_accepts_datetime_and_date_objects():
    dt_obj = dt.datetime(2026, 1, 23, 10, 15)
    d_obj = dt.date(2026, 1, 23)
    assert parse_iso_datetime(dt_obj) == dt_obj
    assert parse_iso_datetime(d_obj) == dt.datetime(2026, 1, 23, 0, 0)


def test_format_time_value_handles_time_and_datetime_inputs():
    assert format_time_value(dt.time(8, 5)) == "08h05"
    assert format_time_value(dt.datetime(2026, 1, 23, 9, 10)) == "09h10"


def test_format_date_value_handles_date_like_inputs():
    assert format_date_value(dt.date(2026, 1, 23), fmt="%Y-%m-%d") == "2026-01-23"
    assert format_date_value(pd.Timestamp("2026-01-24"), fmt="%Y-%m-%d") == "2026-01-24"


def test_format_date_long_fr_invalid_value_returns_default():
    assert format_date_long_fr("bad-date", default="--") == "--"


def test_format_heure_hh_mm_variants():
    from utils.datetime_utils import format_heure_hh_mm

    assert format_heure_hh_mm(None) == ""
    assert format_heure_hh_mm("10h40") == "10h40"
    assert format_heure_hh_mm(dt.time(10, 5)) == "10h05"
    assert format_heure_hh_mm(dt.datetime(2026, 1, 23, 11, 6)) == "11h06"
    assert format_heure_hh_mm("10:30") == "10h30"


def test_parse_date_value_as_date_handles_date_and_datetime():
    assert parse_date_value_as_date(dt.date(2026, 2, 1)) == dt.date(2026, 2, 1)
    assert parse_date_value_as_date(dt.datetime(2026, 2, 1, 12, 0)) == dt.date(2026, 2, 1)


def test_parse_time_value_as_time_handles_empty_and_datetime_and_time():
    assert parse_time_value_as_time("") is None
    assert parse_time_value_as_time(dt.time(7, 45)) == dt.time(7, 45)
    assert parse_time_value_as_time(dt.datetime(2026, 1, 23, 7, 45)) == dt.time(7, 45)


def test_format_time_hm_loose_handles_datetime_and_time():
    assert format_time_hm_loose(dt.datetime(2026, 1, 23, 14, 30)) == "14:30"
    assert format_time_hm_loose(dt.time(14, 31)) == "14:31"


def test_parse_date_long_fr_handles_nat_empty_and_short_text():
    assert pd.isna(parse_date_long_fr(pd.NaT))
    assert pd.isna(parse_date_long_fr(""))
    assert pd.isna(parse_date_long_fr("Lundi"))
