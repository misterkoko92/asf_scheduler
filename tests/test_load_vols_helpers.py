# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import date, datetime, time

import pandas as pd

import loaders.load_vols as lv
from loaders.load_vols import (
    _destinations_from_routing,
    _normalize_flight_number,
    _unique_ordered_codes,
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


def test_parse_date_handles_to_datetime_error(monkeypatch):
    monkeypatch.setattr(lv.pd, "to_datetime", lambda *_a, **_k: (_ for _ in ()).throw(TypeError("boom")))
    assert parse_date("23/01/2026") is None


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
    assert parse_routing("   ") == []


def test_clean_city_strips_suffixes_and_accents():
    assert clean_city("Douala (CAMEROUN)") == "DOUALA"
    assert clean_city("Abidjan (COTE D'IVOIRE),") == "ABIDJAN"
    assert clean_city("Lome,") == "LOME"
    assert clean_city(123) == ""


def test_unique_ordered_codes_and_destinations_from_routing():
    assert _unique_ordered_codes(["DLA", "dla", "", "SSG", "DLA"]) == ["DLA", "SSG"]
    assert _destinations_from_routing(["CDG", "SSG", "DLA"]) == ["SSG", "DLA"]
    assert _destinations_from_routing(["CDG"], fallback_iata="RUN") == ["RUN"]
    assert _destinations_from_routing(["CDG"]) == []


def test_load_vols_can_ingest_api_sheet_when_main_sheet_is_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(lv, "load_and_normalize", lambda **_kwargs: pd.DataFrame())
    monkeypatch.setattr(
        lv.pd,
        "read_excel",
        lambda *_args, **_kwargs: {
            "API-S04-2026": pd.DataFrame(
                [
                    {
                        "Date": "23/01/2026",
                        "Heure": "11:00",
                        "Numéro": "AF0652",
                        "Routing": "CDG,SSG,DLA",
                        "Max_Colis": "50",
                    }
                ]
            )
        },
    )
    monkeypatch.setattr(lv, "warn_ui", lambda *_args, **_kwargs: None)

    param_dest = pd.DataFrame(
        [
            {"Dest_Ville": "DOUALA", "Dest_IATA": "DLA", "Max_Colis_Par_Vol": 20},
        ]
    )
    out = lv.load_vols(vols_path=tmp_path / "Vols.xlsx", param_dest_df=param_dest)
    assert len(out) == 2

    by_dest = {row["dest_iata"]: row for row in out}
    assert by_dest["DLA"]["routing_full"] == ["CDG", "SSG", "DLA"]
    assert by_dest["DLA"]["max_colis_base"] == 20
    assert by_dest["DLA"]["source"] == "api"
    assert by_dest["SSG"]["max_colis_base"] == 50
    assert by_dest["SSG"]["route_pos"] == 1
    assert by_dest["DLA"]["route_pos"] == 2


def test_load_vols_warns_and_returns_empty_when_api_sheets_are_unreadable(monkeypatch, tmp_path):
    monkeypatch.setattr(lv, "load_and_normalize", lambda **_kwargs: pd.DataFrame())
    monkeypatch.setattr(
        lv.pd,
        "read_excel",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(lv.BadZipFile("bad xlsx")),
    )
    warns: list[str] = []
    monkeypatch.setattr(lv, "warn_ui", lambda msg: warns.append(msg))

    out = lv.load_vols(vols_path=tmp_path / "Vols.xlsx", param_dest_df=pd.DataFrame())
    assert out == []
    assert warns


def test_load_vols_skips_invalid_rows_and_handles_capacity_parse_errors(monkeypatch, tmp_path):
    monkeypatch.setattr(
        lv,
        "load_and_normalize",
        lambda **_kwargs: pd.DataFrame(
            [
                {"Numero_Vol": "", "Date_Vol": "16/02/26", "Heure_Vol": "11:00", "Destination_Nom": "DOUALA", "Route_API": "CDG-DLA"},
                {"Numero_Vol": "AF100", "Date_Vol": "invalid", "Heure_Vol": "11:00", "Destination_Nom": "DOUALA", "Route_API": "CDG-DLA"},
                {"Numero_Vol": "AF101", "Date_Vol": "16/02/26", "Heure_Vol": "11:00", "Destination_Nom": "", "Route_API": "CDG"},
                {"Numero_Vol": "AF102", "Date_Vol": "16/02/26", "Heure_Vol": "11:00", "Destination_Nom": "DOUALA", "Route_API": "CDG-DLA-CDG"},
            ]
        ),
    )
    monkeypatch.setattr(lv.pd, "read_excel", lambda *_a, **_k: {})
    monkeypatch.setattr(lv, "warn_ui", lambda *_a, **_k: None)

    param_dest = pd.DataFrame(
        [{"Dest_Ville": "DOUALA", "Dest_IATA": "DLA", "Max_Colis_Par_Vol": "bad-cap"}]
    )
    out = lv.load_vols(vols_path=tmp_path / "Vols.xlsx", param_dest_df=param_dest)

    assert len(out) == 1
    assert out[0]["dest_iata"] == "DLA"
    assert out[0]["routing_full"] == ["CDG", "DLA"]
    assert out[0]["max_colis_base"] is None


def test_load_vols_df_handles_dest_fallback_and_routing_display(monkeypatch):
    monkeypatch.setattr(
        lv,
        "load_vols",
        lambda **_kwargs: [
            {
                "routing": ["CDG", "DLA"],
                "routing_full": ["CDG", "DLA"],
                "dest_iata": "",
                "flight_number": "00652",
                "date": date(2026, 2, 16),
                "departure_time": time(11, 0),
                "route_pos": 1,
                "max_colis_base": 20,
                "source": "excel",
            },
            {
                "routing": [],
                "routing_full": ["CDG", "RUN"],
                "dest_iata": "",
                "flight_number": "00653",
                "date": date(2026, 2, 17),
                "departure_time": time(12, 0),
                "route_pos": 1,
                "max_colis_base": 24,
                "source": "api",
            },
            {
                "routing": [],
                "routing_full": [],
                "dest_iata": "",
                "flight_number": "00654",
                "date": date(2026, 2, 17),
                "departure_time": time(12, 0),
                "route_pos": 1,
                "max_colis_base": 24,
                "source": "api",
            },
            {
                "routing": [],
                "routing_full": [],
                "dest_iata": "DLA",
                "flight_number": "AFX",
                "date": date(2026, 2, 18),
                "departure_time": time(13, 0),
                "route_pos": "x",
                "max_colis_base": "",
                "source": "excel",
            },
        ],
    )
    param_dest = pd.DataFrame(
        [
            {"Dest_IATA": "DLA", "Dest_Ville": "DOUALA"},
            {"Dest_IATA": "RUN", "Dest_Ville": "SAINT DENIS"},
        ]
    )

    df = lv.load_vols_df(param_dest_df=param_dest)
    assert len(df) == 3
    assert set(df["IATA"]) == {"DLA", "RUN"}
    assert "CDG-DLA" in set(df["Routing"])
    assert "CDG-RUN" in set(df["Routing"])
    assert any(v.endswith("AF AFX") for v in df["Numero_Vol"])


def test_vols_cache_wrappers(monkeypatch, tmp_path):
    vols_path = tmp_path / "VOLS.xlsx"
    tdb_path = tmp_path / "TABLEAU_DE_BORD.xlsx"
    vols_path.write_text("x", encoding="utf-8")
    tdb_path.write_text("x", encoding="utf-8")

    captured: dict[str, object] = {}

    class _FakeCached:
        def __call__(self, vols_path_arg, vols_mtime, tdb_path_arg, tdb_mtime):
            captured["args"] = (vols_path_arg, vols_mtime, tdb_path_arg, tdb_mtime)
            return pd.DataFrame([{"A": 1}])

        def clear(self):
            captured["clear"] = True

    monkeypatch.setattr(lv, "_get_vols_df_cached", _FakeCached(), raising=False)
    monkeypatch.setattr(lv, "file_mtime", lambda _p: 123.0)
    out = lv.get_vols_df_cached(vols_path=vols_path, tdb_path=tdb_path)
    lv.clear_vols_cache()

    assert len(out) == 1
    assert captured["args"] == (str(vols_path), 123.0, str(tdb_path), 123.0)
    assert captured["clear"] is True


def test_clear_vols_cache_ignores_clear_errors(monkeypatch):
    class _BadCached:
        def clear(self):
            raise RuntimeError("boom")

    monkeypatch.setattr(lv, "_get_vols_df_cached", _BadCached(), raising=False)
    lv.clear_vols_cache()
