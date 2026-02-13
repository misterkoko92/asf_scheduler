# -*- coding: utf-8 -*-
from __future__ import annotations

import pandas as pd

from asf_app.ui.ui_communication.helpers_email_tables import build_comm_table_html


def test_build_comm_table_html_escapes_values():
    df = pd.DataFrame(
        {
            "Date_Affichage": ["01/01"],
            "Destination": ["<b>TEST</b>"],
            "Numero_Vol_Aff": ["AF123"],
            "Numero_BE_Aff": ['"BE"'],
            "Nb_Colis": [1],
            "Type_Colis": ["<img src=x onerror=alert(1)>"] ,
            "Expediteur": ["ACME"],
            "Destinataire": ["Bob & Alice"],
        }
    )
    html = build_comm_table_html(df)
    assert "<b>" not in html
    assert "&lt;b&gt;TEST&lt;/b&gt;" in html
    assert "&lt;img" in html
    assert "&amp;" in html
    assert "&quot;BE&quot;" in html


def test_build_comm_table_html_returns_empty_message_when_dataframe_is_empty():
    assert "Aucun colis cette semaine" in build_comm_table_html(pd.DataFrame())
    assert "Aucun colis cette semaine" in build_comm_table_html(None)


def test_build_comm_table_html_uses_fallback_numero_vol_column_and_handles_nan():
    df = pd.DataFrame(
        {
            "Date_Affichage": ["01/01"],
            "Destination": ["TEST"],
            "NUMERO VOL": [123.0],
            "Numero_BE_Aff": ["250001"],
            "Nb_Colis": [None],
            "Type_Colis": ["MM"],
            "Expediteur": ["ACME"],
            "Destinataire": ["Alice"],
        }
    )
    html = build_comm_table_html(df)
    assert "AF 123" in html
    assert ">None<" not in html


def test_build_comm_table_html_formats_af_vol_when_identifier_helper_is_empty(monkeypatch):
    monkeypatch.setattr(
        "asf_app.ui.ui_communication.helpers_email_tables.format_vol_display",
        lambda _v: "",
    )
    df = pd.DataFrame(
        {
            "Date_Affichage": ["01/01", "02/01", "03/01"],
            "Destination": ["TEST", "TEST", "TEST"],
            "Numero_Vol_Aff": ["AF822", "822", ""],
            "Numero_BE_Aff": ["250001", "250002", "250003"],
            "Nb_Colis": [1, 1, 1],
            "Type_Colis": ["MM", "MM", "MM"],
            "Expediteur": ["ACME", "ACME", "ACME"],
            "Destinataire": ["Alice", "Bob", "Charly"],
        }
    )
    html = build_comm_table_html(df)
    assert "AF 822" in html
    assert html.count("AF 822") >= 2
