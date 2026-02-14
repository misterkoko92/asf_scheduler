# -*- coding: utf-8 -*-
from __future__ import annotations

import pandas as pd
import pytest

from scheduler.data_sources import (
    AsfBenevDataSource,
    AsfWmsDataSource,
    BaseDataSource,
    CompositeDataSource,
    ExcelDataSource,
    ExcelSourcePaths,
    ExternalRepoPaths,
    _detect_repo_root,
    _format_time,
    _parse_iso_date,
    _unwrap_list,
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


def test_base_data_source_methods_raise_not_implemented():
    base = BaseDataSource()
    with pytest.raises(NotImplementedError):
        base.load_param_be()
    with pytest.raises(NotImplementedError):
        base.load_param_dest()
    with pytest.raises(NotImplementedError):
        base.load_param_benev()
    with pytest.raises(NotImplementedError):
        base.load_shipments_df()
    with pytest.raises(NotImplementedError):
        base.load_vols_df()
    with pytest.raises(NotImplementedError):
        base.load_benevoles_df()


def test_detect_repo_root_and_external_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("ASF_WMS_ROOT", str(tmp_path / "wms"))
    monkeypatch.setenv("ASF_BENEV_ROOT", str(tmp_path / "benev"))
    assert _detect_repo_root("ASF_WMS_ROOT", "fallback") == (tmp_path / "wms").resolve()
    paths = ExternalRepoPaths.detect()
    assert paths.wms_root == (tmp_path / "wms").resolve()
    assert paths.benev_root == (tmp_path / "benev").resolve()


def test_unwrap_and_format_helpers_cover_all_variants():
    assert _unwrap_list(None) == []
    assert _unwrap_list({"results": [1, 2]}) == [1, 2]
    assert _unwrap_list([3]) == [3]
    assert str(_parse_iso_date("2026-01-23")) == "2026-01-23"
    assert _format_time("13h05") == "13:05"


def test_asf_wms_get_post_raise_when_api_url_missing(tmp_path):
    ds = AsfWmsDataSource(tmp_path, enabled=True)
    with pytest.raises(RuntimeError, match="ASF_WMS_API_URL"):
        ds._get("integrations/test")
    with pytest.raises(RuntimeError, match="ASF_WMS_API_URL"):
        ds._post("integrations/test", {})


def test_asf_benev_get_post_raise_when_api_url_missing(tmp_path):
    ds = AsfBenevDataSource(tmp_path, enabled=True)
    with pytest.raises(RuntimeError, match="ASF_BENEV_API_URL"):
        ds._get("integrations/test")
    with pytest.raises(RuntimeError, match="ASF_BENEV_API_URL"):
        ds._post("integrations/test", {})


def test_asf_sources_default_param_and_not_implemented_methods(tmp_path):
    wms = AsfWmsDataSource(tmp_path, enabled=False)
    benev = AsfBenevDataSource(tmp_path, enabled=False)

    assert wms.is_available() is False
    assert benev.is_available() is False
    assert wms.load_param_be().iloc[0]["Type"] == "AUTRE"

    with pytest.raises(NotImplementedError):
        wms.load_vols_df()
    with pytest.raises(NotImplementedError):
        wms.load_benevoles_df()
    with pytest.raises(NotImplementedError):
        benev.load_param_be()
    with pytest.raises(NotImplementedError):
        benev.load_param_dest()
    with pytest.raises(NotImplementedError):
        benev.load_shipments_df()
    with pytest.raises(NotImplementedError):
        benev.load_vols_df()


def test_asf_benev_load_benevoles_df_handles_invalid_ids(monkeypatch, tmp_path):
    monkeypatch.setenv("ASF_BENEV_API_URL", "https://benev.example.test/api")
    ds = AsfBenevDataSource(tmp_path, enabled=True)
    monkeypatch.setattr(
        ds,
        "_get",
        lambda path, params=None: [{"volunteer_id": "x", "date": "2026-01-20", "start_time": "08:00", "end_time": "09:00"}]
        if path == "integrations/availabilities/"
        else [{"volunteer_id": 7, "full_name": "Alice", "constraints": {}}],
    )
    param_benev = pd.DataFrame([{"ID": "bad", "Benevole": "Unknown"}])
    out = ds.load_benevoles_df(param_benev)
    assert len(out) == 1
    assert out.iloc[0]["Benevole"] == ""
    assert out.iloc[0]["Heure_Arrivee"] == "08:00"


def test_composite_can_use_dedicated_vols_source():
    class _Source:
        def __init__(self, value):
            self.value = value

        def is_available(self):
            return True

        def load_param_be(self):
            return pd.DataFrame([{"Type": self.value}])

        def load_param_dest(self):
            return pd.DataFrame([{"Dest_IATA": self.value}])

        def load_param_benev(self):
            return pd.DataFrame([{"Benevole": self.value}])

        def load_shipments_df(self, param_be=None, *, planifiables_only=True):
            _ = param_be, planifiables_only
            return pd.DataFrame([{"BE_Numero": self.value}])

        def load_vols_df(self, param_dest=None):
            _ = param_dest
            return pd.DataFrame([{"Numero_Vol": self.value}])

        def load_benevoles_df(self, param_benev=None):
            _ = param_benev
            return pd.DataFrame([{"Benevole": self.value}])

    composite = CompositeDataSource(base=_Source("base"), vols_source=_Source("vols"))
    assert composite.load_param_dest().iloc[0]["Dest_IATA"] == "vols"
    assert composite.load_vols_df().iloc[0]["Numero_Vol"] == "vols"


def test_resolve_data_source_composite_and_unknown(monkeypatch, tmp_path):
    monkeypatch.setenv("ASF_WMS_ENABLE", "1")
    monkeypatch.setenv("ASF_BENEV_ENABLE", "1")
    paths = ExternalRepoPaths(wms_root=tmp_path / "wms", benev_root=tmp_path / "benev")

    source = resolve_data_source("composite", external_paths=paths)
    assert isinstance(source, CompositeDataSource)

    unknown = resolve_data_source("unknown", external_paths=paths)
    assert isinstance(unknown, ExcelDataSource)


def test_base_data_source_is_available_true():
    assert BaseDataSource().is_available() is True


def test_excel_data_source_loads_missing_param_inputs(monkeypatch, tmp_path):
    source = ExcelDataSource(
        paths=ExcelSourcePaths(
            tableau_de_bord=tmp_path / "tdb.xlsx",
            planning_benevoles=tmp_path / "benev.xlsx",
            vols=tmp_path / "vols.xlsx",
        )
    )

    captured: dict[str, object] = {}
    monkeypatch.setattr(source, "load_param_be", lambda: pd.DataFrame([{"Type": "A"}]))
    monkeypatch.setattr(source, "load_param_dest", lambda: pd.DataFrame([{"Dest_IATA": "DLA"}]))
    def _fake_load_shipments_df(**kwargs):
        captured["ship_kwargs"] = kwargs
        return pd.DataFrame([{"BE_Numero": "1"}])

    def _fake_load_vols_df(**kwargs):
        captured["vol_kwargs"] = kwargs
        return pd.DataFrame([{"Numero_Vol": "100"}])

    monkeypatch.setattr("scheduler.data_sources.load_shipments_df", _fake_load_shipments_df)
    monkeypatch.setattr("scheduler.data_sources.load_vols_df", _fake_load_vols_df)

    out_ship = source.load_shipments_df()
    out_vols = source.load_vols_df()

    assert not out_ship.empty
    assert not out_vols.empty
    assert "param_be_raw" in captured["ship_kwargs"]
    assert "param_dest_df" in captured["vol_kwargs"]


def test_asf_wms_get_and_post_use_requests(monkeypatch, tmp_path):
    monkeypatch.setenv("ASF_WMS_API_URL", "https://wms.example.test/api")
    ds = AsfWmsDataSource(tmp_path, enabled=True)

    calls: list[tuple[str, str]] = []

    class _Resp:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    monkeypatch.setattr(
        "scheduler.data_sources.requests.get",
        lambda url, headers=None, params=None, timeout=None: (
            calls.append(("get", url)),
            _Resp({"ok": "get"}),
        )[1],
    )
    monkeypatch.setattr(
        "scheduler.data_sources.requests.post",
        lambda url, headers=None, json=None, timeout=None: (
            calls.append(("post", url)),
            _Resp({"ok": "post"}),
        )[1],
    )

    assert ds._get("integrations/test", params={"x": 1}) == {"ok": "get"}
    assert ds._post("integrations/test", {"x": 1}) == {"ok": "post"}
    assert calls[0][1].endswith("/integrations/test")
    assert calls[1][1].endswith("/integrations/test")


def test_asf_wms_load_param_benev_not_implemented(tmp_path):
    with pytest.raises(NotImplementedError):
        AsfWmsDataSource(tmp_path, enabled=True).load_param_benev()


def test_asf_benev_get_and_post_use_requests(monkeypatch, tmp_path):
    monkeypatch.setenv("ASF_BENEV_API_URL", "https://benev.example.test/api")
    ds = AsfBenevDataSource(tmp_path, enabled=True)

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"ok": True}

    monkeypatch.setattr("scheduler.data_sources.requests.get", lambda *args, **kwargs: _Resp())
    monkeypatch.setattr("scheduler.data_sources.requests.post", lambda *args, **kwargs: _Resp())

    assert ds._get("integrations/test") == {"ok": True}
    assert ds._post("integrations/test", {"a": 1}) == {"ok": True}


def test_asf_benev_load_benevoles_df_loads_param_when_missing_and_skips_nan(monkeypatch, tmp_path):
    monkeypatch.setenv("ASF_BENEV_API_URL", "https://benev.example.test/api")
    ds = AsfBenevDataSource(tmp_path, enabled=True)

    monkeypatch.setattr(
        ds,
        "load_param_benev",
        lambda: pd.DataFrame(
            [
                {"ID": pd.NA, "Benevole": "Unknown"},
                {"ID": 7, "Benevole": "Alice", "Nom": "Dupont", "Prenom": "Alice", "Prenom_Court": "Ali"},
            ]
        ),
    )
    monkeypatch.setattr(
        ds,
        "_get",
        lambda path, params=None: [{"volunteer_id": 7, "date": "2026-01-20", "start_time": "08:00", "end_time": "09:00"}]
        if path == "integrations/availabilities/"
        else [],
    )

    out = ds.load_benevoles_df(param_benev=None)
    assert len(out) == 1
    assert out.iloc[0]["Benevole"] == "Alice"


def test_asf_benev_fetch_events_and_push_event(monkeypatch, tmp_path):
    monkeypatch.setenv("ASF_BENEV_API_URL", "https://benev.example.test/api")
    ds = AsfBenevDataSource(tmp_path, enabled=True)

    captured: dict[str, object] = {}
    def _fake_get(path, params=None):
        captured["get"] = (path, params)
        return {"results": [{"id": 1}]}

    def _fake_post(path, payload):
        captured["post"] = (path, payload)
        return {"ok": True}

    monkeypatch.setattr(ds, "_get", _fake_get)
    monkeypatch.setattr(ds, "_post", _fake_post)

    events = ds.fetch_events(direction="out", status="pending", source="scheduler")
    out = ds.push_event("planning.updated", {"week": 4}, source="scheduler", target="benev", external_id="x")

    assert events == [{"id": 1}]
    assert out == {"ok": True}
    assert captured["get"] == ("integrations/events/", {"direction": "out", "status": "pending", "source": "scheduler"})
    assert captured["post"][0] == "integrations/events/"
