# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import pytest

import asf_app.services.airfrance_api as af


class _FakeResponse:
    def __init__(self, status_code: int, payload=None, text: str = "", headers=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text
        self.headers = headers or {}

    def json(self):
        return self._payload


def test_read_env_var_from_file_supports_export_and_quotes(tmp_path: Path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "export AF_API_KEY='abc123'\nAF_MIN_DELAY_SECONDS=\"1.5\"\n",
        encoding="utf-8",
    )
    assert af._read_env_var_from_file("AF_API_KEY", env_path) == "abc123"
    assert af._read_env_var_from_file("AF_MIN_DELAY_SECONDS", env_path) == "1.5"
    assert af._read_env_var_from_file("MISSING", env_path) is None


def test_get_api_limits_from_config(monkeypatch):
    values = {
        "AF_MAX_CALLS_PER_DAY": "42",
        "AF_MIN_DELAY_SECONDS": "1.8",
    }
    monkeypatch.setattr(af, "_get_config_value", lambda name: values.get(name))
    max_calls, min_delay = af.get_api_limits()
    assert max_calls == 42
    assert min_delay == 1.8


def test_get_api_limits_invalid_values_fall_back(monkeypatch):
    values = {
        "AF_MAX_CALLS_PER_DAY": "abc",
        "AF_MIN_DELAY_SECONDS": "-2",
    }
    monkeypatch.setattr(af, "_get_config_value", lambda name: values.get(name))
    max_calls, min_delay = af.get_api_limits()
    assert max_calls == af.DEFAULT_AF_MAX_CALLS_PER_DAY
    assert min_delay == af.DEFAULT_AF_MIN_DELAY_SECONDS


def test_get_default_time_origin_type_from_config(monkeypatch):
    monkeypatch.setattr(
        af,
        "_get_config_value",
        lambda name: "M" if name == "AF_TIME_ORIGIN_TYPE" else None,
    )
    assert af.get_default_time_origin_type() == "M"


def test_get_default_time_origin_type_invalid_falls_back(monkeypatch):
    monkeypatch.setattr(
        af,
        "_get_config_value",
        lambda name: "X" if name == "AF_TIME_ORIGIN_TYPE" else None,
    )
    assert af.get_default_time_origin_type() == af.DEFAULT_AF_TIME_ORIGIN_TYPE


def test_fetch_flights_validates_time_origin_type(monkeypatch):
    monkeypatch.setattr(af, "_get_api_key", lambda: "valid-key")
    with pytest.raises(RuntimeError, match="timeOriginType invalide"):
        af.fetch_flights(
            dest="RUN",
            start_date="2026-01-23",
            end_date="2026-01-23",
            origin="CDG",
            airline="AF",
            time_origin_type="X",
        )


def test_fetch_flights_uses_config_default_time_origin_type(monkeypatch):
    monkeypatch.setattr(af, "_get_api_key", lambda: "valid-key")
    monkeypatch.setattr(af, "get_default_time_origin_type", lambda: "M")
    captured = {}

    def _fake_get(url, *, headers, timeout):
        captured["url"] = url
        return _FakeResponse(200, payload={"operationalFlights": []})

    monkeypatch.setattr(af.requests, "get", _fake_get)
    af.fetch_flights(
        dest="RUN",
        start_date="2026-01-23",
        end_date="2026-01-23",
        time_origin_type=None,
    )
    assert "timeOriginType=M" in captured["url"]


def test_fetch_flights_builds_expected_request(monkeypatch):
    monkeypatch.setattr(af, "_get_api_key", lambda: "valid-key")
    captured = {}

    def _fake_get(url, *, headers, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["timeout"] = timeout
        return _FakeResponse(200, payload={"operationalFlights": []})

    monkeypatch.setattr(af.requests, "get", _fake_get)

    data = af.fetch_flights(
        dest="run",
        start_date="2026-01-23",
        end_date="2026-01-23",
        origin="cdg",
        airline="af",
        time_origin_type="M",
    )

    assert data == {"operationalFlights": []}
    assert "origin=CDG" in captured["url"]
    assert "destination=RUN" in captured["url"]
    assert "operatingAirlineCode=AF" in captured["url"]
    assert "timeOriginType=M" in captured["url"]
    assert captured["headers"]["API-Key"] == "valid-key"
    assert captured["headers"]["Accept"] == "application/hal+json"
    assert captured["timeout"] == 20


def test_fetch_flights_404_returns_empty_payload(monkeypatch):
    monkeypatch.setattr(af, "_get_api_key", lambda: "valid-key")
    monkeypatch.setattr(
        af.requests,
        "get",
        lambda *args, **kwargs: _FakeResponse(404, payload={"ignored": True}),
    )
    data = af.fetch_flights(
        dest="RUN",
        start_date="2026-01-23",
        end_date="2026-01-23",
    )
    assert data == {"operationalFlights": []}


def test_extract_routes_prefers_latest_published():
    payload = {
        "operationalFlights": [
            {
                "route": ["CDG", "RUN"],
                "airline": {"code": "AF"},
                "flightNumber": 652,
                "flightLegs": [
                    {
                        "departureInformation": {
                            "departureStation": "CDG",
                            "times": {
                                "scheduled": "2026-01-23T18:20:00.000+01:00",
                                "latestPublished": "2026-01-23T21:01:00.000+01:00",
                            },
                        }
                    }
                ],
            }
        ]
    }

    routes = af.extract_routes(payload)
    assert len(routes) == 1
    assert routes[0].horaire_iso == "2026-01-23T21:01:00.000+01:00"
    assert routes[0].heure_depart == "21h01"
    assert routes[0].date_depart == "23/01/26"


def test_extract_routes_removes_final_cdg_leg():
    payload = {
        "operationalFlights": [
            {
                "route": ["CDG", "RUN", "CDG"],
                "airline": {"code": "AF"},
                "flightNumber": 652,
                "flightLegs": [
                    {
                        "departureInformation": {
                            "departureStation": "CDG",
                            "times": {"scheduled": "2026-01-23T18:20:00.000+01:00"},
                        }
                    }
                ],
            }
        ]
    }
    routes = af.extract_routes(payload)
    assert len(routes) == 1
    assert routes[0].route == "CDG-RUN"
    assert routes[0].destination == "RUN"


def test_fetch_multiple_rejects_quota_overflow(monkeypatch):
    monkeypatch.setattr(af, "get_api_limits", lambda: (1, 1.1))
    with pytest.raises(RuntimeError, match="AF_MAX_CALLS_PER_DAY=1"):
        af.fetch_multiple(
            ["RUN", "DLA"],
            start_date="2026-01-23",
            end_date="2026-01-23",
        )


def test_fetch_multiple_applies_min_delay(monkeypatch):
    monkeypatch.setattr(af, "get_api_limits", lambda: (10, 1.1))
    monkeypatch.setattr(
        af,
        "fetch_flights",
        lambda *args, **kwargs: {"operationalFlights": []},
    )
    monkeypatch.setattr(af, "extract_routes", lambda data: [])
    sleep_calls = []
    monkeypatch.setattr(af.time, "sleep", lambda sec: sleep_calls.append(sec))

    af.fetch_multiple(
        ["RUN", "DLA"],
        start_date="2026-01-23",
        end_date="2026-01-23",
        throttle_sec=0.2,
    )

    assert sleep_calls == [1.1]
