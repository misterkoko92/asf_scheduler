# -*- coding: utf-8 -*-
from __future__ import annotations

import pandas as pd

import asf_app.ui.ui_communication.whatsapp_handler as wa


def test_open_whatsapp_cloud_mode_does_not_spawn_process(monkeypatch):
    monkeypatch.setattr(wa, "IS_STREAMLIT_CLOUD", True)
    calls = {"info": [], "code": [], "popen": []}

    monkeypatch.setattr(wa.st, "info", lambda msg: calls["info"].append(msg))
    monkeypatch.setattr(wa.st, "code", lambda msg: calls["code"].append(msg))
    monkeypatch.setattr(wa.subprocess, "Popen", lambda *args, **kwargs: calls["popen"].append((args, kwargs)))

    wa._open_whatsapp("https://wa.me/33600000000?text=test")

    assert calls["info"]
    assert calls["code"]
    assert calls["popen"] == []


def test_open_whatsapp_windows_without_shell_true(monkeypatch):
    monkeypatch.setattr(wa, "IS_STREAMLIT_CLOUD", False)
    monkeypatch.setattr(wa.platform, "system", lambda: "Windows")
    calls = []
    monkeypatch.setattr(wa.subprocess, "Popen", lambda *args, **kwargs: calls.append((args, kwargs)))

    wa._open_whatsapp("https://wa.me/33600000000?text=test")

    assert len(calls) == 1
    args, kwargs = calls[0]
    assert list(args[0])[:3] == ["cmd", "/c", "start"]
    assert kwargs.get("shell") is None


def test_build_message_for_benevole_coerces_invalid_nb_colis():
    df_bene = pd.DataFrame(
        [
            {
                "DATE": "2026-01-23",
                "Destination": "RUN",
                "Dest_Ville": "SAINT DENIS",
                "Code_IATA": "RUN",
                "Numero_Vol_Aff": "AF 652",
                "Heure_Vol_Aff": "18:20",
                "Numero_BE_Aff": "250001",
                "Type_Colis": "MM",
                "Nb_Colis": "invalid",
                "_BENE_KEY": "B1",
                "Benevole_Prenom": "Alice",
            }
        ]
    )

    msg = wa._build_message_for_benevole(df_bene, vols_info={}, map_iata_city={})

    assert "0 colis" in msg
