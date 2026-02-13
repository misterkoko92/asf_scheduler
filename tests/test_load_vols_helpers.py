# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, time

from loaders.load_vols import (
    _normalize_flight_number,
    clean_city,
    parse_date,
    parse_excel_time,
    parse_routing,
)


def test_normalize_flight_number_handles_common_formats():
    assert _normalize_flight_number("AF0652") == "652"
    assert _normalize_flight_number("652.0") == "652"
    assert _normalize_flight_number("AF 0652") == "652"


def test_normalize_flight_number_falls_back_to_digits_or_clean_text():
    assert _normalize_flight_number("flight 652A") == "652"
    assert _normalize_flight_number("N/A") == "N/A"
    assert _normalize_flight_number("") == ""


def test_parse_date_valid_and_invalid_values():
    assert parse_date("23/01/2026").isoformat() == "2026-01-23"
    assert parse_date("not-a-date") is None
    assert parse_date(None) is None


def test_parse_excel_time_supports_time_datetime_and_string_variants():
    assert parse_excel_time(time(9, 30)) == time(9, 30)
    assert parse_excel_time(datetime(2026, 1, 23, 10, 45)) == time(10, 45)
    assert parse_excel_time("11h20") == time(11, 20)
    assert parse_excel_time("07:05:00") == time(7, 5)


def test_parse_excel_time_supports_excel_float_and_invalid_input():
    assert parse_excel_time(0.5) == time(12, 0)
    assert parse_excel_time("invalid") is None
    assert parse_excel_time("") is None


def test_parse_routing_handles_commas_dashes_spaces_and_invalid():
    assert parse_routing("CDG, RUN") == ["CDG", "RUN"]
    assert parse_routing("cdg-run") == ["CDG", "RUN"]
    assert parse_routing(" CDG - RUN - CDG ") == ["CDG", "RUN", "CDG"]
    assert parse_routing(None) == []


def test_clean_city_strips_suffixes_and_accents():
    assert clean_city("Douala (CAMEROUN)") == "DOUALA"
    assert clean_city("Abidjan (COTE D'IVOIRE),") == "ABIDJAN"
    assert clean_city("Lome,") == "LOME"
