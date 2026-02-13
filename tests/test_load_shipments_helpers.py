# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd

import loaders.load_shipments as ls
from scheduler.config_paths import SHEET_MAG_CENTRAL


def test_parse_time_generic_variants():
    assert ls._parse_time_generic("") is None
    assert ls._parse_time_generic(None) is None
    assert ls._parse_time_generic(dt.time(10, 30)) == dt.time(10, 30)
    assert ls._parse_time_generic("10h30") == dt.time(10, 30)
    assert ls._parse_time_generic("10:30:00") == dt.time(10, 30)
    assert ls._parse_time_generic("10:30") == dt.time(10, 30)
    assert ls._parse_time_generic("10.5") == dt.time(10, 30)
    assert ls._parse_time_generic("invalid") is None


def test_list_mag_central_sheets_filters_by_min_year(tmp_path):
    path = tmp_path / "tdb.xlsx"
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame([{"A": 1}]).to_excel(writer, sheet_name="MAG CENTRAL 2024", index=False)
        pd.DataFrame([{"A": 1}]).to_excel(writer, sheet_name="MAG CENTRAL 2025", index=False)
        pd.DataFrame([{"A": 1}]).to_excel(writer, sheet_name="MAG CENTRAL 2026", index=False)
        pd.DataFrame([{"A": 1}]).to_excel(writer, sheet_name="Other", index=False)

    all_names = ls._list_mag_central_sheets(path)
    filtered = ls._list_mag_central_sheets(path, min_year=2025)

    assert all_names == ["MAG CENTRAL 2024", "MAG CENTRAL 2025", "MAG CENTRAL 2026"]
    assert filtered == ["MAG CENTRAL 2025", "MAG CENTRAL 2026"]


def test_list_mag_central_sheets_returns_empty_on_excel_error(monkeypatch, tmp_path):
    path = tmp_path / "missing.xlsx"
    monkeypatch.setattr(ls.pd, "ExcelFile", lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("boom")))

    out = ls._list_mag_central_sheets(path)

    assert out == []


def test_list_mag_central_sheets_returns_empty_when_no_mag_central_sheet(tmp_path):
    path = tmp_path / "tdb.xlsx"
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame([{"A": 1}]).to_excel(writer, sheet_name="Other", index=False)
    assert ls._list_mag_central_sheets(path, min_year=2025) == []


def test_load_shipments_df_handles_priority_and_equiv_types(monkeypatch):
    base_rows = []
    for idx in range(6):
        base_rows.append(
            {
                "BE_Numero": 260100 + idx,
                "BE_Nb_Colis": idx + 1,
                "BE_Type": "MM",
                "BE_Expediteur": "ASF",
                "BE_Douane": "",
                "BE_Statut": "D",
                "BE_Special": "",
                "Destination": "dla",
            }
        )
    df_raw = pd.DataFrame(base_rows)

    monkeypatch.setattr(ls, "_list_mag_central_sheets", lambda *_args, **_kwargs: [])
    captured = {}

    def _load_and_normalize(**kwargs):
        captured.update(
            {
                "sheet_name": kwargs.get("sheet_name"),
                "header": kwargs.get("header"),
                "mapping_size": len(kwargs.get("mapping", {})),
            }
        )
        return df_raw.copy()

    monkeypatch.setattr(ls, "load_and_normalize", _load_and_normalize)
    monkeypatch.setattr(ls.be_manager, "normalize_param_be", lambda df: df)

    priorities = iter([pd.DataFrame([[5]]), [4], pd.Series([3]), np.array([2]), {"x": 1}, 0])
    equivs = iter([pd.DataFrame([[10]]), [9], pd.Series([8]), np.array([7]), {"x": 6}, 5])
    monkeypatch.setattr(ls, "compute_be_priority", lambda *_args, **_kwargs: next(priorities))
    monkeypatch.setattr(ls, "compute_equiv_colis", lambda *_args, **_kwargs: next(equivs))

    out = ls.load_shipments_df(
        planifiables_only=True,
        tdb_path=Path("dummy.xlsx"),
        param_be_raw=pd.DataFrame([{"Type": "MM"}]),
    )

    assert captured["sheet_name"] == SHEET_MAG_CENTRAL
    assert captured["header"] == 5
    assert len(out) == 6
    assert out["Priorite"].astype(int).tolist() == [5, 4, 3, 2, 1, 0]
    assert out["Equiv_Colis"].astype(int).tolist() == [10, 9, 8, 7, 6, 5]
    assert set(out["Destination"]) == {"DLA"}


def test_load_shipments_df_warns_when_parambe_missing(monkeypatch):
    monkeypatch.setattr(ls, "_list_mag_central_sheets", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        ls,
        "load_and_normalize",
        lambda **_kwargs: pd.DataFrame(
            [
                {
                    "BE_Numero": 260200,
                    "BE_Nb_Colis": 1,
                    "BE_Type": "MM",
                    "BE_Expediteur": "ASF",
                    "BE_Douane": "",
                    "BE_Statut": "D",
                    "BE_Special": "",
                    "Destination": "RUN",
                }
            ]
        ),
    )
    monkeypatch.setattr(ls, "get_param_be", lambda: (_ for _ in ()).throw(OSError("missing")))
    monkeypatch.setattr(ls.be_manager, "normalize_param_be", lambda df: df)
    monkeypatch.setattr(ls, "compute_be_priority", lambda *_args, **_kwargs: 1)
    monkeypatch.setattr(ls, "compute_equiv_colis", lambda *_args, **_kwargs: 1)
    messages: list[str] = []
    monkeypatch.setattr(ls, "warn_ui", lambda msg: messages.append(str(msg)))

    out = ls.load_shipments_df(planifiables_only=True, tdb_path=Path("dummy.xlsx"), param_be_raw=None)

    assert len(out) == 1
    assert any("ParamBE introuvable" in msg for msg in messages)


def test_load_shipments_df_warns_when_mag_central_invalid(monkeypatch):
    monkeypatch.setattr(ls, "_list_mag_central_sheets", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(ls, "load_and_normalize", lambda **_kwargs: "invalid")
    monkeypatch.setattr(ls.be_manager, "normalize_param_be", lambda df: df)
    messages: list[str] = []
    monkeypatch.setattr(ls, "warn_ui", lambda msg: messages.append(str(msg)))

    out = ls.load_shipments_df(
        planifiables_only=True,
        tdb_path=Path("dummy.xlsx"),
        param_be_raw=pd.DataFrame([{"Type": "MM"}]),
    )

    assert isinstance(out, pd.DataFrame)
    assert out.empty
    assert any("MAG CENTRAL illisible" in msg for msg in messages)


def test_get_shipments_df_cached_and_clear(monkeypatch, tmp_path):
    path = tmp_path / "TABLEAU_DE_BORD.xlsx"
    path.write_text("x", encoding="utf-8")
    captured = {"args": None, "cleared": False}

    class _FakeCached:
        def __call__(self, planifiables_only, tdb_path, tdb_mtime):
            captured["args"] = (planifiables_only, tdb_path, tdb_mtime)
            return pd.DataFrame([{"A": 1}])

        def clear(self):
            captured["cleared"] = True

    monkeypatch.setattr(ls, "_get_shipments_df_cached", _FakeCached(), raising=False)
    monkeypatch.setattr(ls, "file_mtime", lambda _p: 123.0)

    out = ls.get_shipments_df_cached(planifiables_only=False, tdb_path=path)
    ls.clear_shipments_cache()

    assert len(out) == 1
    assert captured["args"] == (False, str(path), 123.0)
    assert captured["cleared"] is True


def test_clear_shipments_cache_ignores_clear_errors(monkeypatch):
    class _BadCached:
        def clear(self):
            raise RuntimeError("boom")

    monkeypatch.setattr(ls, "_get_shipments_df_cached", _BadCached(), raising=False)

    ls.clear_shipments_cache()


def test_load_shipments_df_multisheet_branch_and_date_fallbacks(monkeypatch):
    monkeypatch.setattr(
        ls,
        "_list_mag_central_sheets",
        lambda *_args, **_kwargs: ["MAG CENTRAL 2025", "MAG CENTRAL 2026"],
    )
    rows = pd.DataFrame(
        [
            {
                "BE_Numero": 260301,
                "BE_Nb_Colis": 1,
                "BE_Type": "MM",
                "BE_Expediteur": "ASF",
                "BE_Special": "",
                "Heure_Vol": "10:15",
                "BE_Date_Vol": "16/02/26",
                "SomeDate": "bad-date",
                "BE_Date_Impression": "bad-date",
            },
            {
                "BE_Numero": 260302,
                "BE_Nb_Colis": 2,
                "BE_Type": "MM",
                "BE_Expediteur": "ASF",
                "BE_Special": "",
                "Heure_Vol": "11h30",
                "BE_Date_Vol": "17/02/26",
                "SomeDate": "bad-date",
                "BE_Date_Impression": "bad-date",
            },
        ]
    )

    def _load_and_normalize(**kwargs):
        if kwargs.get("sheet_name") == "MAG CENTRAL 2025":
            return pd.DataFrame()
        return rows.copy()

    monkeypatch.setattr(ls, "load_and_normalize", _load_and_normalize)
    monkeypatch.setattr(ls.be_manager, "normalize_param_be", lambda df: df)
    priorities = iter([pd.DataFrame(), {}])
    equivs = iter([pd.DataFrame(), {}])
    monkeypatch.setattr(ls, "compute_be_priority", lambda *_args, **_kwargs: next(priorities))
    monkeypatch.setattr(ls, "compute_equiv_colis", lambda *_args, **_kwargs: next(equivs))

    orig_to_datetime = ls.pd.to_datetime

    def _to_datetime(arg, *args, **kwargs):
        if getattr(arg, "name", "") == "BE_Date_Impression":
            raise TypeError("boom-impression")
        if getattr(arg, "name", "") == "SomeDate":
            raise ValueError("boom-loop")
        return orig_to_datetime(arg, *args, **kwargs)

    monkeypatch.setattr(ls.pd, "to_datetime", _to_datetime)
    out = ls.load_shipments_df(
        planifiables_only=False,
        tdb_path=Path("dummy.xlsx"),
        param_be_raw=pd.DataFrame([{"Type": "MM"}]),
    )

    assert len(out) == 2
    assert set(out["Destination"]) == {""}
    assert out["Heure_Display"].tolist() == ["10h15", "11h30"]
    assert out["Date_Display"].notna().all()
    assert out["Priorite"].astype(int).tolist() == [0, 0]
    assert out["Equiv_Colis"].astype(int).tolist() == [0, 0]


def test_internal_cached_shipments_loader_calls_load_shipments(monkeypatch):
    if not hasattr(ls, "_get_shipments_df_cached"):
        return

    called: dict[str, object] = {}

    def _fake_loader(*, planifiables_only: bool = True, tdb_path: Path | None = None, param_be_raw=None):
        _ = param_be_raw
        called["args"] = (planifiables_only, tdb_path)
        return pd.DataFrame([{"A": 1}])

    monkeypatch.setattr(ls, "load_shipments_df", _fake_loader)
    out = ls._get_shipments_df_cached(True, "dummy.xlsx", 1.0)
    assert len(out) == 1
    assert called["args"] == (True, Path("dummy.xlsx"))
