# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

import asf_app.ui.ui_week_data as ui_week_data


def test_detect_week_from_vols_dataframe():
    state = SimpleNamespace(df_vols=pd.DataFrame({"Date_Vol": ["23/01/26", "24/01/26"]}))
    assert ui_week_data.detect_week(state) == 4


def test_detect_week_handles_empty_or_missing_columns():
    assert ui_week_data.detect_week(SimpleNamespace(df_vols=None)) is None
    assert ui_week_data.detect_week(SimpleNamespace(df_vols=pd.DataFrame())) is None
    assert ui_week_data.detect_week(SimpleNamespace(df_vols=pd.DataFrame({"X": [1]}))) is None


def test_robust_to_datetime_fallback_when_first_parse_fails(monkeypatch):
    calls = {"count": 0}

    def _fake_parse(series, *args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise TypeError("boom")
        return pd.to_datetime(series, errors="coerce", dayfirst=True)

    monkeypatch.setattr(ui_week_data, "parse_date_series", _fake_parse)

    out = ui_week_data.robust_to_datetime(pd.Series(["23/01/26"]))
    assert calls["count"] == 2
    assert out.notna().all()


def test_load_be_moteur_returns_error_on_loader_failure(monkeypatch, tmp_path):
    state = SimpleNamespace(
        df_param_be=pd.DataFrame([{"A": 1}]),
        tdb_tmp=tmp_path / "TABLEAU_DE_BORD.xlsx",
    )
    monkeypatch.setattr(ui_week_data, "get_state", lambda: state)
    monkeypatch.setattr(
        ui_week_data,
        "load_shipments_df",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("read-fail")),
    )

    df, err = ui_week_data.load_be_moteur()
    assert df is None
    assert "Erreur load_shipments_df" in str(err)


def test_load_be_moteur_success_formats_and_sorts(monkeypatch, tmp_path):
    state = SimpleNamespace(
        df_param_be=pd.DataFrame([{"A": 1}]),
        tdb_tmp=tmp_path / "TABLEAU_DE_BORD.xlsx",
    )
    monkeypatch.setattr(ui_week_data, "get_state", lambda: state)

    raw = pd.DataFrame(
        [
            {
                "BE_Numero": "260002",
                "BE_Type": "MM",
                "Destination": "RUN",
                "BE_Expediteur": "ASF",
                "BE_Nb_Colis": 1,
                "Equiv_Colis": 1,
                "Priorite": 2,
                "BE_Douane": "non",
                "BE_Special": "",
            },
            {
                "BE_Numero": "260001",
                "BE_Type": "FRET",
                "Destination": "DLA",
                "BE_Expediteur": "HIA",
                "BE_Nb_Colis": 3,
                "Equiv_Colis": 4,
                "Priorite": 1,
                "BE_Douane": "oui",
                "BE_Special": "X",
            },
        ]
    )
    monkeypatch.setattr(ui_week_data, "load_shipments_df", lambda *args, **kwargs: raw)

    df, err = ui_week_data.load_be_moteur()
    assert err is None
    assert df is not None
    assert list(df["BE_Numero"]) == ["260001", "260002"]
    assert list(df["Douane"]) == ["OUI", "NON"]
    assert set(["Type", "Destination", "IATA", "Nb_Colis", "Equiv_colis", "Priorité"]).issubset(df.columns)


def test_prepare_be_display_dataframe_maps_destination_and_label():
    src = pd.DataFrame(
        [
            {
                "BE_Numero": "260001",
                "IATA": "RUN",
                "Destination": "RUN",
                "Nb_Colis": 2,
                "Type": "MM",
            }
        ]
    )

    out = ui_week_data._prepare_be_display_dataframe(src, iata_to_city={"RUN": "SAINT-DENIS"})

    assert len(out) == 1
    assert out.iloc[0]["Destination"] == "SAINT-DENIS"
    assert "Label" in out.columns
    assert "RUN" in str(out.iloc[0]["Label"])


def test_prepare_benevoles_dataframe_filters_invalid_slots():
    state = SimpleNamespace(
        api_start_date=None,
        api_end_date=None,
        df_benev=pd.DataFrame(
            [
                {"Nom": "Alice", "Date": "16/02/26", "Heure_Arrivee": "08:00", "Heure_Depart": "13:00"},
                {"Nom": "Bob", "Date": "16/02/26", "Heure_Arrivee": "", "Heure_Depart": "13:00"},
            ]
        ),
    )

    out = ui_week_data._prepare_benevoles_dataframe(state, week=8)

    assert len(out) == 1
    assert out.iloc[0]["Nom"] == "Alice"
    assert out.iloc[0]["Arrivée"] != ""
    assert out.iloc[0]["Départ"] != ""


def test_prepare_flights_dataframe_returns_empty_when_no_vols(monkeypatch):
    state = SimpleNamespace(
        df_vols=pd.DataFrame(),
        df_param_dest=pd.DataFrame(),
        df_be=pd.DataFrame(),
        api_start_date=None,
        api_end_date=None,
    )
    monkeypatch.setattr(
        ui_week_data,
        "get_excel_source_paths",
        lambda _state: SimpleNamespace(vols="dummy.xlsx"),
    )
    import loaders.load_vols as lv

    monkeypatch.setattr(lv, "load_vols_df", lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    out = ui_week_data._prepare_flights_dataframe(state, week=8, iata_to_city={})

    assert out.empty


class _StubWeekContainer:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        _ = exc_type, exc, tb
        return False


class _StubWeekSt:
    def __init__(self):
        self.infos: list[str] = []
        self._sort = None
        self.captured_df = None

    def container(self):
        return _StubWeekContainer()

    def markdown(self, *_args, **_kwargs):
        return None

    def subheader(self, *_args, **_kwargs):
        return None

    def info(self, msg):
        self.infos.append(str(msg))

    def selectbox(self, _label, options, index=0, **_kwargs):
        if self._sort in options:
            return self._sort
        return options[index]

    def data_editor(self, df, **_kwargs):
        self.captured_df = df.copy()
        return df


def test_bloc_with_sort_handles_empty_and_sorted_dataframe(monkeypatch):
    stub = _StubWeekSt()
    monkeypatch.setattr(ui_week_data, "st", stub)

    ui_week_data.bloc_with_sort(
        title="Bloc vide",
        df=pd.DataFrame(),
        sort_options=["A"],
        default_sort="A",
    )
    assert any("Aucune donnée" in msg for msg in stub.infos)

    stub._sort = "A"
    src = pd.DataFrame([{"A": 2}, {"A": 1}])
    ui_week_data.bloc_with_sort(
        title="Bloc tri",
        df=src,
        sort_options=["A"],
        default_sort="A",
    )
    assert stub.captured_df is not None
    assert stub.captured_df["A"].tolist() == [1, 2]


class _RenderCtx:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        _ = exc_type, exc, tb
        return False


class _RenderWeekSt:
    def __init__(self):
        self.infos: list[str] = []
        self.errors: list[str] = []

    def header(self, *_args, **_kwargs):
        return None

    def columns(self, n, **_kwargs):
        _ = _kwargs
        return [_RenderCtx() for _ in range(int(n))]

    def error(self, msg):
        self.errors.append(str(msg))

    def info(self, msg):
        self.infos.append(str(msg))

    def expander(self, *_args, **_kwargs):
        return _RenderCtx()

    def dataframe(self, *_args, **_kwargs):
        return None


def test_render_tab_week_data_builds_unique_flights_with_real_routing(monkeypatch):
    stub = _RenderWeekSt()
    monkeypatch.setattr(ui_week_data, "st", stub)
    captured: dict[str, pd.DataFrame] = {}
    monkeypatch.setattr(
        ui_week_data,
        "bloc_with_sort",
        lambda title, df, **_kwargs: captured.__setitem__(title, df.copy() if df is not None else pd.DataFrame()),
    )
    monkeypatch.setattr(
        ui_week_data,
        "load_be_moteur",
        lambda: (
            pd.DataFrame(
                [
                    {
                        "BE_Numero": "260001",
                        "Type": "MM",
                        "Destination": "DOUALA",
                        "IATA": "DLA",
                        "Expéditeur": "test",
                        "Nb_Colis": 10,
                        "Equiv_colis": 10,
                        "Priorité": 1,
                        "Douane": "NON",
                        "Special": "",
                    }
                ]
            ),
            None,
        ),
    )
    monkeypatch.setattr(ui_week_data, "_compute_week_dates", lambda **_kwargs: [])
    monkeypatch.setattr(ui_week_data, "_build_day_labels", lambda _week_dates: [])
    monkeypatch.setattr(
        ui_week_data,
        "_build_benev_week_table",
        lambda *_args, **_kwargs: (pd.DataFrame(), pd.DataFrame()),
    )
    monkeypatch.setattr(
        ui_week_data,
        "_build_flights_week_table",
        lambda *_args, **_kwargs: (pd.DataFrame(), pd.DataFrame()),
    )
    state = SimpleNamespace(
        api_start_date="2026-02-16",
        api_end_date="2026-02-22",
        df_param_dest=pd.DataFrame([{"Dest_IATA": "DLA", "Ville": "DOUALA"}]),
        df_be=pd.DataFrame([{"Status_BE": "D", "Dest_IATA": "DLA"}]),
        df_benev=pd.DataFrame(
            [
                {
                    "Nom": "ALBISSER Philippe",
                    "Date": "16/02/26",
                    "Heure_Arrivee": "08:00",
                    "Heure_Depart": "13:00",
                }
            ]
        ),
        df_vols=pd.DataFrame(
            [
                {
                    "Date_Vol": "16/02/26",
                    "Heure_Vol": "11h00",
                    "Routing": "CDG-SSG-DLA",
                    "Numero_Vol": "AF 822",
                    "Source": "excel",
                },
                {
                    "Date_Vol": "16/02/26",
                    "Heure_Vol": "11h00",
                    "Routing": "CDG-SSG-DLA",
                    "Numero_Vol": "AF 822",
                    "Source": "api",
                },
            ]
        ),
        tdb_tmp=None,
    )
    monkeypatch.setattr(ui_week_data, "get_state", lambda: state)

    ui_week_data.render_tab_week_data()

    assert "Vols disponibles" in captured
    flights = captured["Vols disponibles"]
    assert len(flights) == 1
    assert flights.iloc[0]["Routing"] == "CDG-SSG-DLA"
    assert flights.iloc[0]["Source"] == "api"
