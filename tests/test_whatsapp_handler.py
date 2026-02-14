# -*- coding: utf-8 -*-
from __future__ import annotations

import pandas as pd

import asf_app.ui.ui_communication.whatsapp_handler as wa


def test_encode_for_whatsapp_and_normalize_dest():
    encoded = wa._encode_for_whatsapp("Bonjour Alice & Bob")
    assert "%20" in encoded
    assert "%26" in encoded

    df = pd.DataFrame([{"Dest_Ville": "douala", "Destination": "DLA"}])
    norm = wa._normalize_dest(df)
    assert norm.iloc[0] == "DOUALA"
    assert wa._encode_for_whatsapp("") == ""


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


def test_open_whatsapp_darwin_and_linux(monkeypatch):
    monkeypatch.setattr(wa, "IS_STREAMLIT_CLOUD", False)
    calls = []
    monkeypatch.setattr(wa.subprocess, "Popen", lambda *args, **kwargs: calls.append((args, kwargs)))

    monkeypatch.setattr(wa.platform, "system", lambda: "Darwin")
    wa._open_whatsapp("https://wa.me/33600000000?text=test")
    assert calls
    assert list(calls[-1][0][0]) == ["open", "https://wa.me/33600000000?text=test"]

    monkeypatch.setattr(wa.platform, "system", lambda: "Linux")
    wa._open_whatsapp("https://wa.me/33611111111?text=test")
    assert list(calls[-1][0][0]) == ["xdg-open", "https://wa.me/33611111111?text=test"]


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


def test_compute_vols_info_and_generate_messages_multi_benevole():
    df = pd.DataFrame(
        [
            {
                "DATE": "2026-01-23",
                "Destination": "DOUALA",
                "Dest_Ville": "DOUALA",
                "Code_IATA": "DLA",
                "Numero_Vol_Aff": "822",
                "Heure_Vol_Aff": "11:00",
                "Numero_BE_Aff": "260001",
                "Type_Colis": "MM",
                "Nb_Colis": 10,
                "BENEVOLE": "ALBISSER Philippe",
                "BENEVOLE_ID": 1,
                "Benevole_Prenom": "Philippe",
                "Benevole_Prenom_Court": "P.",
                "Benevole_Nom": "ALBISSER",
                "Benevole_Tel": "+33 6 12 34 56 78",
                "Date_Affichage_WA": "Lundi 23/01",
            },
            {
                "DATE": "2026-01-23",
                "Destination": "DOUALA",
                "Dest_Ville": "DOUALA",
                "Code_IATA": "DLA",
                "Numero_Vol_Aff": "AF 822",
                "Heure_Vol_Aff": "11:00",
                "Numero_BE_Aff": "260002",
                "Type_Colis": "MM",
                "Nb_Colis": 5,
                "BENEVOLE": "PIERSON Gilles",
                "BENEVOLE_ID": 2,
                "Benevole_Prenom": "Gilles",
                "Benevole_Prenom_Court": "G.",
                "Benevole_Nom": "PIERSON",
                "Benevole_Tel": "06.11.22.33.44",
                "Date_Affichage_WA": "Lundi 23/01",
            },
        ]
    )

    vols_info = wa._compute_vols_info(df)
    assert ("2026-01-23", "DLA", "AF 822") in vols_info
    assert int(vols_info[("2026-01-23", "DLA", "AF 822")]["total_colis"]) == 15

    messages = wa.generate_whatsapp_messages(df)
    assert len(messages) == 2
    assert all(msg["url"].startswith("https://wa.me/") for msg in messages)
    assert "en double" in messages[0]["message"] or "en double" in messages[1]["message"]


def test_generate_whatsapp_messages_skips_empty_phone_and_open_delegate(monkeypatch):
    df = pd.DataFrame(
        [
            {
                "DATE": "2026-01-23",
                "Destination": "RUN",
                "Dest_Ville": "SAINT DENIS",
                "Code_IATA": "RUN",
                "Numero_Vol_Aff": "AF 652",
                "Heure_Vol_Aff": "18:20",
                "Numero_BE_Aff": "260010",
                "Type_Colis": "MM",
                "Nb_Colis": 1,
                "BENEVOLE": "Sans Tel",
                "BENEVOLE_ID": 99,
                "Benevole_Tel": "",
                "Benevole_Prenom": "Sans",
            }
        ]
    )
    assert wa.generate_whatsapp_messages(df) == []

    called = {"url": None}
    monkeypatch.setattr(wa, "_open_whatsapp", lambda url: called.__setitem__("url", url))
    wa.open_whatsapp_for_benevole("https://wa.me/33600000000?text=ok")
    assert called["url"] == "https://wa.me/33600000000?text=ok"


def test_build_message_for_benevole_name_fallbacks_and_iata_mapping():
    df_bene = pd.DataFrame(
        [
            {
                "DATE": "2026-01-23",
                "Destination": "",
                "Dest_Ville": "",
                "Code_IATA": "RUN",
                "Numero_Vol_Aff": "AF 652",
                "Heure_Vol_Aff": "18:20",
                "Numero_BE_Aff": "250001",
                "Type_Colis": "MM",
                "Nb_Colis": 1,
                "_BENE_KEY": "B1",
                "BENEVOLE": "ALBISSER Philippe",
                "Benevole_Prenom": "",
                "Benevole_Prenom_Court": "",
            }
        ]
    )
    msg = wa._build_message_for_benevole(
        df_bene,
        vols_info={("2026-01-23", "RUN", "AF 652"): {"total_colis": 1, "benevoles": {}, "iata": "RUN"}},
        map_iata_city={"RUN": "SAINT DENIS"},
    )
    assert "Bonjour ALBISSER" in msg
    assert "SAINT DENIS" in msg

    df_blank = pd.DataFrame(columns=df_bene.columns)
    msg_blank = wa._build_message_for_benevole(df_blank, vols_info={}, map_iata_city={})
    assert "Bonjour  ," in msg_blank


def test_compute_vols_info_fallbacks_to_benevole_name_initial():
    df = pd.DataFrame(
        [
            {
                "DATE": "2026-01-23",
                "Destination": "DOUALA",
                "Dest_Ville": "DOUALA",
                "Code_IATA": "DLA",
                "Numero_Vol_Aff": "AF 822",
                "Heure_Vol_Aff": "11:00",
                "Numero_BE_Aff": "260001",
                "Type_Colis": "MM",
                "Nb_Colis": 2,
                "BENEVOLE": "Jean Dupont",
                "BENEVOLE_ID": "",
                "Benevole_Prenom": "",
                "Benevole_Prenom_Court": "",
                "Benevole_Nom": "",
            }
        ]
    )
    info = wa._compute_vols_info(df)
    key = ("2026-01-23", "DLA", "AF 822")
    assert key in info
    bene = info[key]["benevoles"]
    assert "JEAN DUPONT" in bene
    assert bene["JEAN DUPONT"][0] == "J."


def test_generate_whatsapp_messages_handles_missing_columns_and_empty_inputs():
    assert wa.generate_whatsapp_messages(None) == []
    assert wa.generate_whatsapp_messages(pd.DataFrame()) == []

    df = pd.DataFrame(
        [
            {
                "DATE": "2026-01-23",
                "Destination": "RUN",
                "Dest_Ville": "SAINT DENIS",
                "Code_IATA": "RUN",
                "Numero_Vol_Aff": "AF 652",
                "Heure_Vol_Aff": "18:20",
                "Numero_BE_Aff": "260010",
                "Type_Colis": "MM",
                "Nb_Colis": 1,
                "Benevole": "Sans Colonnes",
                "ID": "",
                "Telephone": "+33 6 00 00 00 00",
            }
        ]
    )
    out = wa.generate_whatsapp_messages(df)
    assert len(out) == 1
    assert out[0]["telephone"] == "33600000000"
