# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib

import scheduler.config as config_mod


def _reload_config():
    return importlib.reload(config_mod)


def test_config_defaults_when_env_absent(monkeypatch):
    monkeypatch.delenv("ASF_DUREE_MISSION_HEURES", raising=False)
    monkeypatch.delenv("ASF_MIN_HOURS_BETWEEN_FLIGHTS", raising=False)

    cfg = _reload_config()

    assert cfg.DUREE_MISSION_HEURES == 3.0
    assert cfg.MIN_HOURS_BETWEEN_FLIGHTS == 3.0


def test_config_reads_valid_env_values(monkeypatch):
    monkeypatch.setenv("ASF_DUREE_MISSION_HEURES", "1")
    monkeypatch.setenv("ASF_MIN_HOURS_BETWEEN_FLIGHTS", "1.5")

    cfg = _reload_config()

    assert cfg.DUREE_MISSION_HEURES == 1.0
    assert cfg.MIN_HOURS_BETWEEN_FLIGHTS == 1.5


def test_config_ignores_invalid_or_negative_env_values(monkeypatch):
    monkeypatch.setenv("ASF_DUREE_MISSION_HEURES", "abc")
    monkeypatch.setenv("ASF_MIN_HOURS_BETWEEN_FLIGHTS", "-2")

    cfg = _reload_config()

    assert cfg.DUREE_MISSION_HEURES == 3.0
    assert cfg.MIN_HOURS_BETWEEN_FLIGHTS == 3.0


def test_config_summary_contains_core_values():
    cfg = _reload_config()
    summary = cfg.get_config_summary()
    assert "MAX_BE_PER_FLIGHT" in summary
    assert "MAX_EQUIV_PER_VOLUNTEER" in summary
