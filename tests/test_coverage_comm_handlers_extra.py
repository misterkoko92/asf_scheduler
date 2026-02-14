# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import pandas as pd

from asf_app.ui.ui_communication import email_destinations_handler as dest_handler
from asf_app.ui.ui_communication import email_expediteurs_handler as exp_handler
from asf_app.ui.ui_communication import email_airfrance_ui as air_ui
from asf_app.ui.ui_communication import pdf_attachments as pa
from asf_app.ui.ui_communication import ui_communication_helpers as comm_helpers


def test_destination_handler_empty_and_missing_subset_paths():
    assert dest_handler._get_emails_for_destination(None, "RUN") == ([], [])

    assert (
        dest_handler.generate_destination_email_for_destination(
            df_comm=pd.DataFrame(),
            df_paramdest=pd.DataFrame(),
            destination="RUN",
            week=4,
            year=2026,
        )
        is False
    )

    assert (
        dest_handler.generate_destination_email_for_destination(
            df_comm=pd.DataFrame([{"Destination": "RUN"}]),
            df_paramdest=pd.DataFrame(),
            destination="DLA",
            week=4,
            year=2026,
        )
        is False
    )

    assert (
        dest_handler.generate_all_destination_emails(
            df_comm=pd.DataFrame(),
            df_paramdest=pd.DataFrame(),
            week=4,
            year=2026,
        )
        == 0
    )


def test_expediteur_handler_branches_for_empty_and_non_empty_paths(monkeypatch):
    assert exp_handler._get_emails_for_expediteur(pd.DataFrame(), "MSF") == ([], [])
    assert (
        exp_handler._get_emails_for_expediteur(
            pd.DataFrame([{"Expediteur_Nom": "ASF"}]),
            "MSF",
        )
        == ([], [])
    )

    assert exp_handler._get_correspondant_for_destination(pd.DataFrame(), "DLA") == ""
    assert (
        exp_handler._get_correspondant_for_destination(
            pd.DataFrame([{"Dest_Ville": "RUN"}]),
            "DLA",
        )
        == ""
    )
    corr = exp_handler._get_correspondant_for_destination(
        pd.DataFrame(
            [
                {
                    "Dest_Ville": "DLA",
                    "Contact_Titre": "Dr",
                    "Contact_Prenom": "Jean",
                    "Contact_Nom": "Dupont",
                    "Contact_Email": "d@example.org",
                    "Contact_Tel1": "0101",
                    "Contact_Tel2": "",
                    "Contact_Tel3": "0303",
                }
            ]
        ),
        "DLA",
    )
    assert corr.endswith("0303")

    captured: dict[str, object] = {}
    monkeypatch.setattr(exp_handler, "build_comm_table_html", lambda _df: "<table>ok</table>")
    monkeypatch.setattr(exp_handler, "find_be_pdf_attachments", lambda *_a, **_k: [])
    monkeypatch.setattr(
        exp_handler,
        "create_outlook_draft",
        lambda **kwargs: captured.update(kwargs) or True,
    )

    ok = exp_handler.generate_expediteur_email_for_pair(
        df_comm=pd.DataFrame([{"Expediteur": "MSF", "Destination": "DLA", "Numero_BE_Aff": "250001"}]),
        df_paramdest=pd.DataFrame([{"Dest_Ville": "DLA", "Contact_Email": "dest@example.org"}]),
        df_paramexpediteur=pd.DataFrame(
            [{"Expediteur_Nom": "MSF", "Expediteur_Email": "msf@example.org", "Expediteur_Copie": ""}]
        ),
        expediteur="MSF",
        destination="DLA",
        week=4,
        year=2026,
    )
    assert ok is True
    assert "<table>ok</table>" in str(captured.get("body_html", ""))

    assert (
        exp_handler.generate_all_expediteurs_emails(
            df_comm=pd.DataFrame(),
            df_paramdest=pd.DataFrame(),
            df_paramexpediteur=pd.DataFrame(),
            week=4,
            year=2026,
        )
        == 0
    )


def test_pdf_attachments_extra_branches(monkeypatch, tmp_path):
    monkeypatch.delenv("ASF_LISTES_COLISAGE_DIR", raising=False)
    monkeypatch.setattr(pa, "is_graph_onedrive", lambda: False)
    monkeypatch.setattr(pa, "get_onedrive_root", lambda: tmp_path)
    assert str(pa.get_colisage_dir()).endswith("8-Listes de colisage")

    assert pa.collect_be_keys(pd.DataFrame()) == set()

    base = tmp_path / "pdfs"
    base.mkdir()
    (base / "folder.pdf").mkdir()
    (base / "invalid.pdf").write_bytes(b"%PDF-1.4\n")
    assert pa.index_pdfs_by_be(base) == {}

    assert pa.find_be_pdf_attachments(pd.DataFrame(), pdf_index={"250001": ["/tmp/a.pdf"]}) == []

    monkeypatch.setattr(pa, "index_pdfs_by_be", lambda *_a, **_k: {})
    subset = pd.DataFrame([{"NUMERO BE": "250001"}])
    assert pa.find_be_pdf_attachments(subset, pdf_index=None) == []


def test_ui_communication_helpers_private_branches():
    assert comm_helpers._collect_dest_map(None) == {}
    assert (
        comm_helpers._collect_dest_map(
            pd.DataFrame([{"BE_Numero": "250001", "BE_Destinataire": ""}])
        )
        == {}
    )
    assert comm_helpers._key_from_comm_row(pd.Series({"X": "1"})) == ""

    out = comm_helpers.fill_missing_destinataire(
        pd.DataFrame([{"NUMERO BE": "999999"}]),
        mapping={"250001": "HOPITAL"},
    )
    assert "Destinataire" in out.columns
    assert str(out.loc[0, "Destinataire"]).strip() == ""

    fallback_series = comm_helpers._first_existing_series(pd.DataFrame([{"A": 1}]), ["X", "Y"])
    assert fallback_series.tolist() == [""]


class _Ctx:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        _ = exc_type, exc, tb
        return False


class _AirStubSt:
    def __init__(self):
        self.session_state: dict[str, object] = {}
        self.warnings: list[str] = []
        self.errors: list[str] = []
        self.successes: list[str] = []
        self._button_values: dict[str, bool] = {}

    def subheader(self, *_args, **_kwargs):
        return None

    def columns(self, n, **_kwargs):
        return [_Ctx() for _ in range(int(n))]

    def text_input(self, _label, value="", **_kwargs):
        return value

    def text_area(self, _label, value="", **_kwargs):
        return value

    def expander(self, *_args, **_kwargs):
        return _Ctx()

    def text(self, *_args, **_kwargs):
        return None

    def warning(self, msg):
        self.warnings.append(str(msg))

    def error(self, msg):
        self.errors.append(str(msg))

    def success(self, msg):
        self.successes.append(str(msg))

    def info(self, *_args, **_kwargs):
        return None

    def markdown(self, *_args, **_kwargs):
        return None

    def button(self, label, **_kwargs):
        return bool(self._button_values.get(str(label), False))


def test_airfrance_ui_extra_branches(monkeypatch):
    # dates.empty branch in helper
    assert air_ui._detect_week_year_from_df(pd.DataFrame({"DATE": ["invalid"]})) == (None, None)

    stub = _AirStubSt()
    stub.session_state["current_week"] = 4
    stub.session_state["current_year"] = 2026
    stub._button_values["📤 Générer le mail Air France"] = True
    monkeypatch.setattr(air_ui, "st", stub)
    monkeypatch.setattr(air_ui, "get_email_defaults", lambda: {"airfrance": {"to": "", "cc": "", "bcc": ""}})
    monkeypatch.setattr(air_ui, "generate_airfrance_email", lambda **_kwargs: False)

    air_ui.render_email_airfrance_ui(df_comm=pd.DataFrame({"DATE": ["2026-01-19"]}), pdf_attachment_path=None)

    assert any("Pas de planning PDF trouvé" in msg for msg in stub.warnings)
    assert any("Échec de création du mail Air France" in msg for msg in stub.errors)
