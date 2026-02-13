# -*- coding: utf-8 -*-
from __future__ import annotations

import pandas as pd

from scheduler.data_sources import (
    AsfBenevDataSource,
    AsfWmsDataSource,
    CompositeDataSource,
    ExcelDataSource,
    ExcelSourcePaths,
    resolve_data_source,
)


def test_excel_data_source(sample_onedrive):
    paths = ExcelSourcePaths.from_defaults()
    source = ExcelDataSource(paths=paths)

    param_be = source.load_param_be()
    param_dest = source.load_param_dest()
    param_benev = source.load_param_benev()
    shipments = source.load_shipments_df(param_be)
    vols = source.load_vols_df(param_dest)
    benev = source.load_benevoles_df(param_benev)

    assert len(param_be) >= 1
    assert len(shipments) == 1
    assert len(vols) == 1
    assert len(benev) == 1


def test_excel_data_source_planifiables_only(sample_onedrive):
    paths = ExcelSourcePaths.from_defaults()
    source = ExcelDataSource(paths=paths)
    param_be = source.load_param_be()

    df_all = source.load_shipments_df(param_be, planifiables_only=False)
    df_planif = source.load_shipments_df(param_be, planifiables_only=True)

    assert len(df_all) == 2
    assert len(df_planif) == 1


def test_composite_data_source_fallback(sample_onedrive, tmp_path):
    base = ExcelDataSource(paths=ExcelSourcePaths.from_defaults())
    wms = AsfWmsDataSource(tmp_path, enabled=False)
    benev = AsfBenevDataSource(tmp_path, enabled=False)
    composite = CompositeDataSource(base=base, shipments_source=wms, volunteers_source=benev)

    shipments = composite.load_shipments_df()
    benev = composite.load_benevoles_df()

    assert len(shipments) == 1
    assert len(benev) == 1


def test_resolve_data_source_env(monkeypatch, sample_onedrive):
    monkeypatch.setenv("ASF_DATA_SOURCE", "excel")
    source = resolve_data_source()
    assert isinstance(source, ExcelDataSource)

    monkeypatch.setenv("ASF_DATA_SOURCE", "asf-wms")
    source = resolve_data_source()
    assert isinstance(source, AsfWmsDataSource)

    monkeypatch.setenv("ASF_DATA_SOURCE", "asf-benev")
    source = resolve_data_source()
    assert isinstance(source, AsfBenevDataSource)


def test_asf_wms_data_source_maps_destinations_shipments_and_events(monkeypatch, tmp_path):
    monkeypatch.setenv("ASF_WMS_API_URL", "https://wms.example.test/api")
    monkeypatch.setenv("ASF_WMS_API_KEY", "k_test")
    monkeypatch.setenv("ASF_WMS_API_TIMEOUT", "12")
    ds = AsfWmsDataSource(tmp_path, enabled=True)

    assert ds.is_available() is True
    assert ds._headers()["X-ASF-Integration-Key"] == "k_test"

    def _fake_get(path, params=None):
        if path == "integrations/destinations/":
            return [
                {
                    "iata_code": "run",
                    "city": "Saint-Denis",
                    "country": "RE",
                    "correspondent_name": "Jean Martin",
                }
            ]
        if path == "integrations/shipments/":
            return [
                {
                    "reference": "BE-1",
                    "status": "draft",
                    "carton_count": "3",
                    "destination_iata": "run",
                    "destination_city": "Saint-Denis",
                    "destination_country": "RE",
                    "shipper_name": "ASF",
                    "recipient_name": "Hopital",
                    "created_at": "2026-01-01",
                    "ready_at": "2026-01-02",
                    "requested_delivery_date": "2026-01-03",
                    "notes": "fragile",
                },
                {
                    "reference": "BE-2",
                    "status": "delivered",
                    "carton_count": "x",
                    "destination_city": "Douala",
                    "destination_country": "CM",
                    "shipper_name": "ASF",
                    "recipient_name": "Centre",
                },
            ]
        if path == "integrations/events/":
            assert params == {"direction": "out", "status": "pending", "source": "scheduler"}
            return {"results": [{"id": 10}]}
        raise AssertionError(f"unexpected path: {path}")

    posted: list[tuple[str, dict]] = []

    def _fake_post(path, payload):
        posted.append((path, payload))
        return {"ok": True, "payload": payload}

    monkeypatch.setattr(ds, "_get", _fake_get)
    monkeypatch.setattr(ds, "_post", _fake_post)

    df_dest = ds.load_param_dest()
    assert len(df_dest) == 1
    assert df_dest.iloc[0]["Dest_IATA"] == "RUN"
    assert df_dest.iloc[0]["Contact_Nom"] == "Jean Martin"

    df_ship = ds.load_shipments_df(planifiables_only=True)
    assert len(df_ship) == 1
    assert str(df_ship.iloc[0]["BE_Numero"]) == "BE-1"
    assert str(df_ship.iloc[0]["BE_Statut"]) == "D"
    assert int(df_ship.iloc[0]["BE_Nb_Colis"]) == 3

    ev = ds.fetch_events(direction="out", status="pending", source="scheduler")
    assert isinstance(ev, list)
    assert ev[0]["id"] == 10

    out = ds.push_event(
        "planning.updated",
        {"week": 4},
        source="scheduler",
        target="wms",
        external_id="abc",
    )
    assert out["ok"] is True
    assert posted
    assert posted[0][0] == "integrations/events/"
    assert posted[0][1]["event_type"] == "planning.updated"


def test_asf_benev_data_source_maps_volunteers_and_availabilities(monkeypatch, tmp_path):
    monkeypatch.setenv("ASF_BENEV_API_URL", "https://benev.example.test/api")
    monkeypatch.setenv("ASF_BENEV_API_KEY", "k_benev")
    monkeypatch.setenv("ASF_BENEV_API_TOKEN", "t_benev")
    monkeypatch.setenv("ASF_BENEV_API_START", "2026-01-01")
    monkeypatch.setenv("ASF_BENEV_API_END", "2026-01-31")
    ds = AsfBenevDataSource(tmp_path, enabled=True)

    assert ds.is_available() is True
    headers = ds._headers()
    assert headers["X-ASF-Integration-Key"] == "k_benev"
    assert headers["Authorization"] == "Token t_benev"

    def _fake_get(path, params=None):
        if path == "integrations/volunteers/":
            return [
                {
                    "volunteer_id": 7,
                    "full_name": "Alice Dupont",
                    "short_name": "Alice",
                    "last_name": "Dupont",
                    "first_name": "Alice",
                    "email": "alice@example.org",
                    "phone": "0600000000",
                    "constraints": {
                        "max_assigned_volunteer_flight": 22,
                        "max_days_per_week": 4,
                        "max_expeditions_per_week": 8,
                        "max_expeditions_per_day": 2,
                        "max_wait_hours": 6,
                    },
                }
            ]
        if path == "integrations/availabilities/":
            assert params == {"start": "2026-01-01", "end": "2026-01-31"}
            return [
                {
                    "volunteer_id": 7,
                    "date": "2026-01-20",
                    "start_time": "08:00:00",
                    "end_time": "13:30:00",
                }
            ]
        raise AssertionError(f"unexpected path: {path}")

    monkeypatch.setattr(ds, "_get", _fake_get)

    param = ds.load_param_benev()
    assert len(param) == 1
    assert int(param.iloc[0]["ID"]) == 7
    assert int(param.iloc[0]["Max_Colis_Vol"]) == 22

    dispo = ds.load_benevoles_df(param)
    assert len(dispo) == 1
    assert int(dispo.iloc[0]["ID"]) == 7
    assert dispo.iloc[0]["Benevole"] == "Alice Dupont"
    assert dispo.iloc[0]["Heure_Arrivee"] == "08:00"
    assert dispo.iloc[0]["Heure_Depart"] == "13:30"


def test_composite_data_source_prefers_available_over_base(tmp_path):
    class _Source:
        def __init__(self, name, available):
            self.name = name
            self._available = available

        def is_available(self):
            return self._available

        def load_param_be(self):
            return pd.DataFrame([{"Type": self.name}])

        def load_param_dest(self):
            return pd.DataFrame([{"Dest_IATA": self.name}])

        def load_param_benev(self):
            return pd.DataFrame([{"Benevole": self.name}])

        def load_shipments_df(self, param_be=None, *, planifiables_only=True):
            _ = param_be, planifiables_only
            return pd.DataFrame([{"BE_Numero": self.name}])

        def load_vols_df(self, param_dest=None):
            _ = param_dest
            return pd.DataFrame([{"Numero_Vol": self.name}])

        def load_benevoles_df(self, param_benev=None):
            _ = param_benev
            return pd.DataFrame([{"Benevole": self.name}])

    base = _Source("base", True)
    shipments = _Source("ship", True)
    volunteers = _Source("benev", False)
    composite = CompositeDataSource(base=base, shipments_source=shipments, volunteers_source=volunteers)

    assert composite.load_param_be().iloc[0]["Type"] == "ship"
    assert composite.load_shipments_df().iloc[0]["BE_Numero"] == "ship"
    # volunteers_source indisponible -> fallback base
    assert composite.load_param_benev().iloc[0]["Benevole"] == "base"
    assert composite.load_benevoles_df().iloc[0]["Benevole"] == "base"
