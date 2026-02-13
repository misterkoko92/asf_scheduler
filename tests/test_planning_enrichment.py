# -*- coding: utf-8 -*-
from __future__ import annotations

import pandas as pd

from scheduler import planning_enrichment as pe


def _setup_fake_sources(monkeypatch, *, benev_rows):
    def fake_load_and_normalize(_path, sheet_name, _column_map, header=0):
        _ = header
        if sheet_name == pe.SHEET_MAG_CENTRAL:
            return pd.DataFrame(
                [
                    {
                        "BE_Numero": "123",
                        "BE_Date_Impression": "2026-01-10",
                        "BE_Nb_Colis": 4,
                        "BE_Type": "MED",
                        "BE_Expediteur": "ASF",
                        "BE_Destinataire": "CHU RUN",
                    }
                ]
            )
        if sheet_name == pe.SHEET_PARAM_DEST:
            return pd.DataFrame([{"Dest_IATA": "RUN", "Dest_Ville": "SAINT-DENIS"}])
        if sheet_name == pe.SHEET_PARAM_EXP:
            return pd.DataFrame([{"Expediteur_Nom": "ASF", "Expediteur_Email": "asf@example.org"}])
        if sheet_name == pe.SHEET_PARAM_BE:
            return pd.DataFrame([{"Type": "MED"}])
        if sheet_name == pe.SHEET_PARAM_BENEV:
            return pd.DataFrame(benev_rows)
        raise AssertionError(f"Unexpected sheet requested: {sheet_name}")

    monkeypatch.setattr(pe, "load_and_normalize", fake_load_and_normalize)
    monkeypatch.setattr(
        pe,
        "load_vols_df",
        lambda: pd.DataFrame(
            [
                {
                    "IATA": "RUN",
                    "Routing": "CDG-RUN",
                    "Heure_Vol": "18:20",
                    "Date_Vol": "2026-01-23",
                    "Numero_Vol": "AF0652",
                    "Max_Colis": 40,
                }
            ]
        ),
    )
    monkeypatch.setattr(
        pe,
        "format_be_numero",
        lambda raw_value, date_impression, fallback_latest_date: ("250123", "0123"),
    )


def test_enrich_planning_empty_input_returns_empty_df():
    assert pe.enrich_planning(pd.DataFrame()).empty
    assert pe.enrich_planning(None).empty


def test_enrich_planning_merges_sources_and_builds_standard_columns(monkeypatch):
    _setup_fake_sources(
        monkeypatch,
        benev_rows=[
            {
                "ID": "ID01",
                "Benevole": "ALPHA",
                "Nom": "Martin",
                "Prenom": "Alice",
                "Prenom_Court": "A",
                "Telephone": "0600000000",
            }
        ],
    )

    df_input = pd.DataFrame(
        [
            {
                "BE_Numero": "250123",
                "Destination": "RUN",
                "BE_Expediteur": "ASF",
                "ID": "ID01",
                "Benevole": "ALPHA",
                "Numero_Vol": "AF0652",
                "Date_Vol": "2026-01-23",
            }
        ]
    )

    out = pe.enrich_planning(df_input)

    assert len(out) == 1
    row = out.iloc[0]
    assert row["IATA"] == "RUN"
    assert row["ROUTING"] == "CDG-RUN"
    assert row["HEURE VOL"] == "18:20"
    assert row["TYPE"] == "MED"
    assert row["EXPEDITEUR"] == "ASF"
    assert row["DESTINATAIRE"] == "CHU RUN"
    assert row["ID_BENEVOLE"] == "ID01"
    assert row["TELEPHONE"] == "0600000000"
    assert row["NOM"] == "A. MARTIN"
    assert row["_merge_fail"] == 0
    assert str(row["DATE LONGUE"]).strip() != ""
    assert str(row["ITEM"]).strip() != ""


def test_enrich_planning_fallback_benevole_name_and_merge_fail(monkeypatch):
    _setup_fake_sources(
        monkeypatch,
        benev_rows=[
            {
                "ID": "",
                "Benevole": "BENEV TEST",
                "Nom": "",
                "Prenom": "",
                "Prenom_Court": "",
                "Telephone": "0699999999",
            }
        ],
    )

    df_input = pd.DataFrame(
        [
            {
                "BE_Numero": "250123",
                "Destination": "RUN",
                "BE_Expediteur": "",
                "ID": "",
                "Benevole": "BENEV TEST",
                "Numero_Vol": "AF0652",
                "Date_Vol": "2026-01-23",
            }
        ]
    )

    out = pe.enrich_planning(df_input)
    row = out.iloc[0]

    assert row["NOM"] == "BENEV TEST"
    assert row["TELEPHONE"] == "0699999999"
    assert row["_merge_fail"] == 1
