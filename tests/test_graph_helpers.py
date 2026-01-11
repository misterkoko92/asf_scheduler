# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest
import scheduler.config_paths as cp


def test_output_remote_path_template(monkeypatch):
    monkeypatch.setattr(cp, "OUTPUT_PLANNING_REMOTE_DIR_TEMPLATE", "Planning/Exports/{year}")
    assert cp.get_output_remote_dir(2025) == "Planning/Exports/2025"
    assert cp.get_output_remote_path(2025, "Planning.xlsx") == "Planning/Exports/2025/Planning.xlsx"


def test_encode_path_quotes_and_strips(tmp_path, monkeypatch):
    pytest.importorskip("msal")
    import scheduler.onedrive_graph as odg

    class _DummyApp:
        def __init__(self, *args, **kwargs) -> None:
            return None

    monkeypatch.setattr(odg.msal, "PublicClientApplication", _DummyApp)
    GraphConfig = odg.GraphConfig
    OneDriveGraphClient = odg.OneDriveGraphClient

    cfg = GraphConfig(
        tenant_id="tenant-id",
        client_id="client-id",
        scopes=["User.Read"],
        token_cache_path=tmp_path / "cache.json",
    )
    client = OneDriveGraphClient(cfg)
    assert (
        client._encode_path("/Planning MAB/Resultat/Plan #1.xlsx")
        == "Planning%20MAB/Resultat/Plan%20%231.xlsx"
    )
