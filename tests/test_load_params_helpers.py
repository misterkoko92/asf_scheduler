# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pandas as pd

import loaders.load_params as lp


def test_clear_param_caches_ignores_clear_errors(monkeypatch):
    class _DummyCache:
        def clear(self):
            raise RuntimeError("boom")

    monkeypatch.setattr(lp, "st", object(), raising=False)
    monkeypatch.setattr(lp, "_param_be_cached", _DummyCache(), raising=False)
    monkeypatch.setattr(lp, "_param_dest_cached", _DummyCache(), raising=False)
    monkeypatch.setattr(lp, "_param_exp_cached", _DummyCache(), raising=False)
    monkeypatch.setattr(lp, "_param_benev_cached", _DummyCache(), raising=False)

    lp.clear_param_caches()


def test_clear_param_caches_noop_when_streamlit_is_none(monkeypatch):
    monkeypatch.setattr(lp, "st", None, raising=False)
    lp.clear_param_caches()


def test_clear_param_caches_calls_clear_when_available(monkeypatch):
    class _DummyCache:
        def __init__(self):
            self.cleared = 0

        def clear(self):
            self.cleared += 1

    be = _DummyCache()
    dest = _DummyCache()
    exp = _DummyCache()
    benev = _DummyCache()
    monkeypatch.setattr(lp, "st", object(), raising=False)
    monkeypatch.setattr(lp, "_param_be_cached", be, raising=False)
    monkeypatch.setattr(lp, "_param_dest_cached", dest, raising=False)
    monkeypatch.setattr(lp, "_param_exp_cached", exp, raising=False)
    monkeypatch.setattr(lp, "_param_benev_cached", benev, raising=False)

    lp.clear_param_caches()

    assert be.cleared == 1
    assert dest.cleared == 1
    assert exp.cleared == 1
    assert benev.cleared == 1


def test_load_param_dest_normalizes_frequencies_iata_and_capacity(monkeypatch):
    monkeypatch.setattr(
        lp,
        "load_and_normalize",
        lambda *_args, **_kwargs: pd.DataFrame(
            [
                {
                    "Dest_IATA": " dla ",
                    "Freq_Lundi": "ok",
                    "Freq_Mardi": "",
                    "Freq_Mercredi": None,
                    "Freq_Jeudi": "x",
                    "Max_Colis_Par_Vol": "12",
                }
            ]
        ),
    )

    out = lp._load_param_dest(tableau_de_bord_path=Path("/tmp/tdb.xlsx"))
    row = out.iloc[0]
    assert row["Dest_IATA"] == "DLA"
    assert int(row["Freq_Lundi"]) == 1
    assert int(row["Freq_Mardi"]) == 0
    assert int(row["Freq_Mercredi"]) == 0
    assert int(row["Freq_Jeudi"]) == 0
    assert int(row["Max_Colis_Par_Vol"]) == 12


def test_load_param_exp_passthrough(monkeypatch):
    monkeypatch.setattr(
        lp,
        "load_and_normalize",
        lambda *_args, **_kwargs: pd.DataFrame([{"Nom": "ACME", "Email": "a@example.org"}]),
    )
    out = lp._load_param_exp(tableau_de_bord_path=Path("/tmp/tdb.xlsx"))
    assert len(out) == 1
    assert out.iloc[0]["Nom"] == "ACME"


def test_load_param_be_normalizes_type_and_numeric(monkeypatch):
    monkeypatch.setattr(
        lp,
        "load_and_normalize",
        lambda *_args, **_kwargs: pd.DataFrame(
            [
                {"Type": " mm ", "Priorite_Type": "3", "Equiv": "2"},
                {"Type": "cn", "Priorite_Type": "x", "Equiv": ""},
            ]
        ),
    )

    out = lp._load_param_be(tableau_de_bord_path=Path("/tmp/tdb.xlsx"))
    assert out["Type"].tolist() == ["MM", "CN"]
    assert out["Priorite_Type"].dtype.name == "Int64"
    assert out["Equiv"].dtype.name == "Int64"
    assert pd.isna(out.loc[1, "Priorite_Type"])
    assert pd.isna(out.loc[1, "Equiv"])


def test_load_param_benev_normalizes_numeric_columns(monkeypatch):
    monkeypatch.setattr(
        lp,
        "load_and_normalize",
        lambda *_args, **_kwargs: pd.DataFrame(
            [
                {
                    "ID": "7",
                    "Max_Jours_Semaine": "2",
                    "Max_Exp_Semaine": "3",
                    "Max_Exp_Jour": "1",
                    "Max_Colis_Vol": "10",
                    "Attente_Max_Heures": "1.5",
                }
            ]
        ),
    )

    out = lp._load_param_benev(planning_benevoles_path=Path("/tmp/benev.xlsx"))
    row = out.iloc[0]
    assert int(row["ID"]) == 7
    assert int(row["Max_Jours_Semaine"]) == 2
    assert int(row["Max_Exp_Semaine"]) == 3
    assert int(row["Max_Exp_Jour"]) == 1
    assert int(row["Max_Colis_Vol"]) == 10
    assert float(row["Attente_Max_Heures"]) == 1.5


def test_load_param_from_path_helpers_delegate_to_internal_loaders(monkeypatch, tmp_path):
    calls: list[tuple[str, Path]] = []

    monkeypatch.setattr(
        lp,
        "_load_param_be",
        lambda tableau_de_bord_path=None: calls.append(("be", tableau_de_bord_path)) or pd.DataFrame(),
    )
    monkeypatch.setattr(
        lp,
        "_load_param_dest",
        lambda tableau_de_bord_path=None: calls.append(("dest", tableau_de_bord_path)) or pd.DataFrame(),
    )
    monkeypatch.setattr(
        lp,
        "_load_param_exp",
        lambda tableau_de_bord_path=None: calls.append(("exp", tableau_de_bord_path)) or pd.DataFrame(),
    )
    monkeypatch.setattr(
        lp,
        "_load_param_benev",
        lambda planning_benevoles_path=None: calls.append(("benev", planning_benevoles_path)) or pd.DataFrame(),
    )

    tdb = tmp_path / "tdb.xlsx"
    benev = tmp_path / "benev.xlsx"
    lp.load_param_be_from_path(tdb)
    lp.load_param_dest_from_path(tdb)
    lp.load_param_exp_from_path(tdb)
    lp.load_param_benev_from_path(benev)

    assert calls == [
        ("be", tdb),
        ("dest", tdb),
        ("exp", tdb),
        ("benev", benev),
    ]


def test_get_param_cached_wrappers_use_file_mtime_and_cache_functions(monkeypatch, tmp_path):
    calls: list[tuple[str, str, float]] = []
    monkeypatch.setattr(lp, "file_mtime", lambda _path: 12.5)

    monkeypatch.setattr(
        lp,
        "_param_be_cached",
        lambda path, mtime: calls.append(("be", path, mtime)) or pd.DataFrame([{"v": 1}]),
        raising=False,
    )
    monkeypatch.setattr(
        lp,
        "_param_dest_cached",
        lambda path, mtime: calls.append(("dest", path, mtime)) or pd.DataFrame([{"v": 2}]),
        raising=False,
    )
    monkeypatch.setattr(
        lp,
        "_param_exp_cached",
        lambda path, mtime: calls.append(("exp", path, mtime)) or pd.DataFrame([{"v": 3}]),
        raising=False,
    )
    monkeypatch.setattr(
        lp,
        "_param_benev_cached",
        lambda path, mtime: calls.append(("benev", path, mtime)) or pd.DataFrame([{"v": 4}]),
        raising=False,
    )

    tdb = tmp_path / "tdb.xlsx"
    benev = tmp_path / "benev.xlsx"
    tdb.write_text("x", encoding="utf-8")
    benev.write_text("x", encoding="utf-8")

    assert int(lp.get_param_be(tdb).iloc[0]["v"]) == 1
    assert int(lp.get_param_dest(tdb).iloc[0]["v"]) == 2
    assert int(lp.get_param_exp(tdb).iloc[0]["v"]) == 3
    assert int(lp.get_param_benev(benev).iloc[0]["v"]) == 4

    assert calls == [
        ("be", str(tdb), 12.5),
        ("dest", str(tdb), 12.5),
        ("exp", str(tdb), 12.5),
        ("benev", str(benev), 12.5),
    ]


def test_get_param_wrappers_fallback_when_streamlit_unavailable(monkeypatch, tmp_path):
    real_streamlit = sys.modules.get("streamlit")
    monkeypatch.setitem(sys.modules, "streamlit", None)
    lp_no_st = importlib.reload(lp)
    calls: list[tuple[str, Path | None]] = []

    monkeypatch.setattr(
        lp_no_st,
        "_load_param_be",
        lambda tableau_de_bord_path=None: calls.append(("be", tableau_de_bord_path)) or pd.DataFrame(),
    )
    monkeypatch.setattr(
        lp_no_st,
        "_load_param_dest",
        lambda tableau_de_bord_path=None: calls.append(("dest", tableau_de_bord_path)) or pd.DataFrame(),
    )
    monkeypatch.setattr(
        lp_no_st,
        "_load_param_exp",
        lambda tableau_de_bord_path=None: calls.append(("exp", tableau_de_bord_path)) or pd.DataFrame(),
    )
    monkeypatch.setattr(
        lp_no_st,
        "_load_param_benev",
        lambda planning_benevoles_path=None: calls.append(("benev", planning_benevoles_path)) or pd.DataFrame(),
    )

    tdb = tmp_path / "tdb.xlsx"
    benev = tmp_path / "benev.xlsx"
    lp_no_st.get_param_be(tdb)
    lp_no_st.get_param_dest(tdb)
    lp_no_st.get_param_exp(tdb)
    lp_no_st.get_param_benev(benev)

    assert calls == [
        ("be", tdb),
        ("dest", tdb),
        ("exp", tdb),
        ("benev", benev),
    ]

    if real_streamlit is None:
        sys.modules.pop("streamlit", None)
    else:
        sys.modules["streamlit"] = real_streamlit
    importlib.reload(lp)
