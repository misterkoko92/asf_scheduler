# -*- coding: utf-8 -*-
from __future__ import annotations

import pandas as pd

from asf_app.ui.ui_communication import email_destinations_handler as destinations
from asf_app.ui.ui_communication import email_expediteurs_handler as expediteurs


def test_get_emails_for_destination_matches_city_then_iata():
    df_paramdest = pd.DataFrame(
        [
            {
                "Dest_Ville": "Douala",
                "Dest_IATA": "DLA",
                "Contact_Email": "dest@example.org",
                "Contact_Copie": "cc@example.org",
            }
        ]
    )

    to_city, cc_city = destinations._get_emails_for_destination(df_paramdest, "Douala")
    to_iata, cc_iata = destinations._get_emails_for_destination(df_paramdest, "DLA")
    to_none, cc_none = destinations._get_emails_for_destination(df_paramdest, "XYZ")

    assert (to_city, cc_city) == ("dest@example.org", "cc@example.org")
    assert (to_iata, cc_iata) == ("dest@example.org", "cc@example.org")
    assert (to_none, cc_none) == ([], [])


def test_generate_destination_email_for_destination_success(monkeypatch):
    df_comm = pd.DataFrame(
        [
            {"Destination": "DLA", "Numero_BE_Aff": "250123"},
            {"Destination": "RUN", "Numero_BE_Aff": "250124"},
        ]
    )
    df_paramdest = pd.DataFrame(
        [
            {
                "Dest_Ville": "DLA",
                "Dest_IATA": "DLA",
                "Contact_Email": "dla@example.org",
                "Contact_Copie": "copy@example.org",
            }
        ]
    )
    captured: dict[str, object] = {}
    monkeypatch.setattr(destinations, "build_comm_table_html", lambda df: "<table>ok</table>")
    monkeypatch.setattr(
        destinations,
        "find_be_pdf_attachments",
        lambda df_subset, pdf_index=None: ["/tmp/be_250123.pdf"],
    )
    monkeypatch.setattr(
        destinations,
        "create_outlook_draft",
        lambda **kwargs: captured.update(kwargs) or True,
    )

    ok = destinations.generate_destination_email_for_destination(
        df_comm=df_comm,
        df_paramdest=df_paramdest,
        destination="DLA",
        week=4,
        year=2026,
    )

    assert ok is True
    assert captured["subject"] == "ASF / Expédition DLA / Semaine 4"
    assert "<table>ok</table>" in str(captured["body_html"])
    assert captured["to_list"] == "dla@example.org"
    assert captured["cc_list"] == "copy@example.org"
    assert captured["attachments"] == ["/tmp/be_250123.pdf"]


def test_generate_destination_email_for_destination_requires_to(monkeypatch):
    df_comm = pd.DataFrame([{"Destination": "RUN", "Numero_BE_Aff": "250124"}])
    monkeypatch.setattr(destinations, "_get_emails_for_destination", lambda *args, **kwargs: ("", ""))

    ok = destinations.generate_destination_email_for_destination(
        df_comm=df_comm,
        df_paramdest=pd.DataFrame(),
        destination="RUN",
        week=4,
        year=2026,
    )

    assert ok is False


def test_generate_all_destination_emails_counts_success_and_deduplicates(monkeypatch):
    df_comm = pd.DataFrame(
        [
            {"Destination": "DLA"},
            {"Destination": "dla"},
            {"Destination": "RUN"},
        ]
    )
    calls: list[str] = []
    monkeypatch.setattr(destinations, "index_pdfs_by_be", lambda: {"250123": ["/tmp/a.pdf"]})

    def _fake_generate(**kwargs):
        calls.append(str(kwargs["destination"]))
        return kwargs["destination"] == "DLA"

    monkeypatch.setattr(destinations, "generate_destination_email_for_destination", _fake_generate)

    count = destinations.generate_all_destination_emails(
        df_comm=df_comm,
        df_paramdest=pd.DataFrame(),
        week=4,
        year=2026,
    )

    assert sorted(calls) == ["DLA", "RUN"]
    assert count == 1


def test_get_expediteur_emails_and_correspondant():
    df_param_exp = pd.DataFrame(
        [
            {
                "Expediteur_Nom": "MSF",
                "Expediteur_Email": "msf@example.org",
                "Expediteur_Copie": "copie@example.org",
            }
        ]
    )
    df_param_dest = pd.DataFrame(
        [
            {
                "Dest_Ville": "Douala",
                "Contact_Titre": "Dr",
                "Contact_Prenom": "Jean",
                "Contact_Nom": "Dupont",
                "Contact_Email": "dest@example.org",
                "Contact_Tel1": "0101",
                "Contact_Tel2": "0202",
                "Contact_Tel3": "",
            }
        ]
    )

    to_raw, cc_raw = expediteurs._get_emails_for_expediteur(df_param_exp, "msf")
    corr = expediteurs._get_correspondant_for_destination(df_param_dest, "douala")

    assert (to_raw, cc_raw) == ("msf@example.org", "copie@example.org")
    assert corr == "Dr Jean DUPONT / dest@example.org / 0101 / 0202"


def test_generate_expediteur_email_for_pair_with_empty_subset(monkeypatch):
    df_comm = pd.DataFrame([{"Expediteur": "MSF", "Destination": "RUN", "Numero_BE_Aff": "250123"}])
    df_param_exp = pd.DataFrame(
        [{"Expediteur_Nom": "MSF", "Expediteur_Email": "msf@example.org", "Expediteur_Copie": ""}]
    )
    captured: dict[str, object] = {}
    monkeypatch.setattr(expediteurs, "create_outlook_draft", lambda **kwargs: captured.update(kwargs) or True)
    monkeypatch.setattr(expediteurs, "find_be_pdf_attachments", lambda *args, **kwargs: [])
    monkeypatch.setattr(expediteurs, "_get_correspondant_for_destination", lambda *args, **kwargs: "Contact X")

    ok = expediteurs.generate_expediteur_email_for_pair(
        df_comm=df_comm,
        df_paramdest=pd.DataFrame(),
        df_paramexpediteur=df_param_exp,
        expediteur="MSF",
        destination="DLA",
        week=4,
        year=2026,
    )

    assert ok is True
    assert "Aucun colis cette semaine" in str(captured["body_html"])
    assert captured["to_list"] == "msf@example.org"
    assert captured["attachments"] is None


def test_generate_all_expediteurs_emails_excludes_asf(monkeypatch):
    df_comm = pd.DataFrame(
        [
            {"Expediteur": "ASF", "Destination": "RUN"},
            {"Expediteur": "MSF", "Destination": "RUN"},
            {"Expediteur": "MSF", "Destination": "RUN"},
            {"Expediteur": "CROIX ROUGE", "Destination": "DLA"},
        ]
    )
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(expediteurs, "index_pdfs_by_be", lambda: {})

    def _fake_generate(**kwargs):
        calls.append((str(kwargs["expediteur"]), str(kwargs["destination"])))
        return True

    monkeypatch.setattr(expediteurs, "generate_expediteur_email_for_pair", _fake_generate)

    count = expediteurs.generate_all_expediteurs_emails(
        df_comm=df_comm,
        df_paramdest=pd.DataFrame(),
        df_paramexpediteur=pd.DataFrame(),
        week=4,
        year=2026,
    )

    assert sorted(calls) == [("CROIX ROUGE", "DLA"), ("MSF", "RUN")]
    assert count == 2
