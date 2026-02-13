# -*- coding: utf-8 -*-
from __future__ import annotations

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
