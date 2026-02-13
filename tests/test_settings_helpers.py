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
