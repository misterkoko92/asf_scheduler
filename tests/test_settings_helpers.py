# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime as dt
import importlib
import sys
import types


def _ensure_yaml_stub() -> None:
    if "yaml" in sys.modules:
        return
    yaml_stub = types.ModuleType("yaml")
    yaml_stub.safe_load = lambda *args, **kwargs: {}
    yaml_stub.safe_dump = lambda *args, **kwargs: None
    sys.modules["yaml"] = yaml_stub


_ensure_yaml_stub()
settings_mod = importlib.import_module("asf_app.config.settings")


def test_coerce_int():
    assert settings_mod._coerce_int("12", default=0) == 12
    assert settings_mod._coerce_int("", default=7) == 7
    assert settings_mod._coerce_int("x", default=7) == 7


def test_coerce_optional_int():
    assert settings_mod._coerce_optional_int("42") == 42
    assert settings_mod._coerce_optional_int("") is None
    assert settings_mod._coerce_optional_int("bad") is None


def test_coerce_time():
    fallback = dt.time(6, 30)
    assert settings_mod._coerce_time("07:45", fallback) == dt.time(7, 45)
    assert settings_mod._coerce_time("bad", fallback) == fallback
    assert settings_mod._coerce_time(None, fallback) == fallback


def test_settings_load_save_reset_and_to_dict(monkeypatch, tmp_path):
    cfg_path = tmp_path / "config_defaults.yml"
    cfg_path.write_text("x: 1\n", encoding="utf-8")
    monkeypatch.setattr(settings_mod, "CONFIG_YAML", cfg_path)

    loaded = {
        "MAX_BE_PER_FLIGHT": "12",
        "MAX_EQUIV_PER_VOLUNTEER": "22",
        "DUREE_MISSION_HEURES": "4",
        "MAX_BENEV_PER_VOL": "3",
        "DEFAULT_FLIGHT_TIME": "08:45",
        "MAX_CAPACITE_PAR_VOL": "99",
    }
    monkeypatch.setattr(settings_mod.yaml, "safe_load", lambda *_args, **_kwargs: loaded)

    dumped: dict[str, object] = {}

    def _safe_dump(data, _stream, **_kwargs):
        dumped.update(data)

    monkeypatch.setattr(settings_mod.yaml, "safe_dump", _safe_dump)

    settings = settings_mod.Settings()
    settings.load_from_yaml()

    assert settings.max_be_per_flight == 12
    assert settings.max_equiv_per_volunteer == 22
    assert settings.duree_mission_heures == 4
    assert settings.max_benev_per_vol == 3
    assert settings.default_flight_time == dt.time(8, 45)
    assert settings.max_capacite_par_vol == 99

    # Setter ignoré pour valeur non time
    settings.default_flight_time = "bad-value"  # type: ignore[assignment]
    assert settings.default_flight_time == dt.time(8, 45)

    as_dict = settings.to_dict()
    assert as_dict["MAX_BE_PER_FLIGHT"] == 12
    assert as_dict["DEFAULT_FLIGHT_TIME"] == "08:45"

    settings.save_to_yaml()
    assert dumped["MAX_BE_PER_FLIGHT"] == 12
    assert dumped["MAX_CAPACITE_PAR_VOL"] == 99

    # Reset vers config moteur
    settings.max_be_per_flight = 2
    settings.reset_to_defaults()
    assert settings.max_be_per_flight == int(settings_mod.engine_cfg.MAX_BE_PER_FLIGHT)


def test_settings_load_from_yaml_missing_file_is_noop(monkeypatch, tmp_path):
    cfg_path = tmp_path / "does_not_exist.yml"
    monkeypatch.setattr(settings_mod, "CONFIG_YAML", cfg_path)

    settings = settings_mod.Settings()
    current = settings.max_be_per_flight
    settings.load_from_yaml()
    assert settings.max_be_per_flight == current


def test_settings_property_coercions():
    settings = settings_mod.Settings()
    settings.max_be_per_flight = "7"  # type: ignore[assignment]
    settings.max_equiv_per_volunteer = ""  # type: ignore[assignment]
    settings.duree_mission_heures = "5"  # type: ignore[assignment]
    settings.max_benev_per_vol = "not-int"
    settings.max_capacite_par_vol = "15"

    assert settings.max_be_per_flight == 7
    assert settings.max_equiv_per_volunteer == 1
    assert settings.duree_mission_heures == 5
    assert settings.max_benev_per_vol is None
    assert settings.max_capacite_par_vol == 15
