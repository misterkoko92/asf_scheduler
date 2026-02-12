# -*- coding: utf-8 -*-
from __future__ import annotations

import pandas as pd

from asf_app.ui.ui_communication import email_destinations_handler as dest_h
from asf_app.ui.ui_communication import email_expediteurs_handler as exp_h


def test_get_emails_for_destination_city_and_iata():
    df_paramdest = pd.DataFrame(
        [
            {
                "Dest_Ville": "Douala",
                "Dest_IATA": "DLA",
                "Contact_Email": "to@example.org",
                "Contact_Copie": "cc@example.org",
            }
        ]
    )

    to_city, cc_city = dest_h._get_emails_for_destination(df_paramdest, "DOUALA")
    to_iata, cc_iata = dest_h._get_emails_for_destination(df_paramdest, "DLA")

    assert to_city == "to@example.org"
    assert cc_city == "cc@example.org"
    assert to_iata == "to@example.org"
    assert cc_iata == "cc@example.org"


def test_generate_destination_email_for_destination_calls_outlook(monkeypatch):
    df_comm = pd.DataFrame(
        [
            {"Destination": "DLA", "Numero_BE_Aff": "250001", "Nb_Colis": 2, "Type_Colis": "MM"},
        ]
    )
    df_paramdest = pd.DataFrame(
        [
            {"Dest_Ville": "DLA", "Dest_IATA": "DLA", "Contact_Email": "to@example.org", "Contact_Copie": "cc@example.org"},
        ]
    )

    captured = {}
    monkeypatch.setattr(dest_h, "build_comm_table_html", lambda df: "<table>ok</table>")
    monkeypatch.setattr(dest_h, "find_be_pdf_attachments", lambda *args, **kwargs: [])

    def _fake_outlook(**kwargs):
        captured.update(kwargs)
        return True

    monkeypatch.setattr(dest_h, "create_outlook_draft", _fake_outlook)

    ok = dest_h.generate_destination_email_for_destination(
        df_comm=df_comm,
        df_paramdest=df_paramdest,
        destination="DLA",
        week=4,
        year=2026,
    )

    assert ok is True
    assert captured["to_list"] == "to@example.org"
    assert captured["cc_list"] == "cc@example.org"
    assert captured["subject"] == "ASF / Expédition DLA / Semaine 4"
    assert "<table>ok</table>" in captured["body_html"]


def test_get_correspondant_for_destination_formats_contact():
    df_paramdest = pd.DataFrame(
        [
            {
                "Dest_Ville": "Douala",
                "Contact_Titre": "Dr",
                "Contact_Prenom": "Jean",
                "Contact_Nom": "Dupont",
                "Contact_Email": "j.dupont@example.org",
                "Contact_Tel1": "+33 6 12 34 56 78",
                "Contact_Tel2": "",
                "Contact_Tel3": "",
            }
        ]
    )

    val = exp_h._get_correspondant_for_destination(df_paramdest, "DOUALA")
    assert val.startswith("Dr Jean DUPONT")
    assert "j.dupont@example.org" in val
    assert "+33 6 12 34 56 78" in val


def test_generate_expediteur_email_for_pair_allows_empty_subset(monkeypatch):
    df_comm = pd.DataFrame(
        [
            {"Expediteur": "ASF", "Destination": "DLA"},
        ]
    )
    df_paramdest = pd.DataFrame([{"Dest_Ville": "DLA"}])
    df_paramexpediteur = pd.DataFrame(
        [
            {"Expediteur_Nom": "HOPITAL", "Expediteur_Email": "to@example.org", "Expediteur_Copie": "cc@example.org"},
        ]
    )

    captured = {}
    monkeypatch.setattr(exp_h, "find_be_pdf_attachments", lambda *args, **kwargs: [])

    def _fake_outlook(**kwargs):
        captured.update(kwargs)
        return True

    monkeypatch.setattr(exp_h, "create_outlook_draft", _fake_outlook)

    ok = exp_h.generate_expediteur_email_for_pair(
        df_comm=df_comm,
        df_paramdest=df_paramdest,
        df_paramexpediteur=df_paramexpediteur,
        expediteur="HOPITAL",
        destination="DLA",
        week=4,
        year=2026,
    )

    assert ok is True
    assert captured["to_list"] == "to@example.org"
    assert captured["cc_list"] == "cc@example.org"
    assert "Aucun colis cette semaine" in captured["body_html"]
