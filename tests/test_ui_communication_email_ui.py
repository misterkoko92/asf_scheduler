# -*- coding: utf-8 -*-
from __future__ import annotations

import pandas as pd

import asf_app.ui.ui_communication.email_airfrance_ui as air_ui
import asf_app.ui.ui_communication.email_asf_ui as asf_ui
import asf_app.ui.ui_communication.email_destinations_ui as dest_ui
import asf_app.ui.ui_communication.email_expediteurs_ui as exp_ui


class _Ctx:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        _ = exc_type, exc, tb
        return False


class _StubSt:
    def __init__(self):
        self.session_state: dict[str, object] = {}
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.infos: list[str] = []
        self.successes: list[str] = []
        self.markdowns: list[str] = []
        self._button_values: dict[str, bool] = {}
        self._selectbox_values: dict[str, object] = {}
        self._text_inputs: list[tuple[str, object]] = []
        self._text_areas: list[tuple[str, object]] = []

    def subheader(self, *_args, **_kwargs):
        return None

    def columns(self, n, **_kwargs):
        return [_Ctx() for _ in range(int(n))]

    def expander(self, *_args, **_kwargs):
        return _Ctx()

    def divider(self):
        return None

    def text(self, *_args, **_kwargs):
        return None

    def markdown(self, msg, **_kwargs):
        self.markdowns.append(str(msg))

    def info(self, msg):
        self.infos.append(str(msg))

    def warning(self, msg):
        self.warnings.append(str(msg))

    def success(self, msg):
        self.successes.append(str(msg))

    def error(self, msg):
        self.errors.append(str(msg))

    def text_input(self, label, value="", **_kwargs):
        self._text_inputs.append((str(label), value))
        return value

    def text_area(self, label, value="", **_kwargs):
        self._text_areas.append((str(label), value))
        return value

    def button(self, label, **_kwargs):
        return bool(self._button_values.get(str(label), False))

    def selectbox(self, label, options, index=0, **_kwargs):
        key = str(label)
        if key in self._selectbox_values:
            return self._selectbox_values[key]
        return options[index]


def test_detect_week_year_helpers_for_airfrance_and_asf():
    df = pd.DataFrame({"DATE": ["2026-01-19", "2026-01-20"]})
    assert air_ui._detect_week_year_from_df(df) == (4, 2026)
    assert asf_ui._detect_week_year_from_df(df) == (4, 2026)
    assert air_ui._detect_week_year_from_df(pd.DataFrame()) == (None, None)
    assert asf_ui._detect_week_year_from_df(pd.DataFrame({"DATE": ["invalid"]})) == (None, None)


def test_render_email_airfrance_ui_requires_week_year(monkeypatch):
    stub = _StubSt()
    monkeypatch.setattr(air_ui, "st", stub)

    air_ui.render_email_airfrance_ui(df_comm=pd.DataFrame())

    assert any("Impossible de détecter la semaine" in msg for msg in stub.errors)


def test_render_email_airfrance_ui_generates_success(monkeypatch, tmp_path):
    stub = _StubSt()
    stub.session_state["current_week"] = 4
    stub.session_state["current_year"] = 2026
    stub._button_values["📤 Générer le mail Air France"] = True
    monkeypatch.setattr(air_ui, "st", stub)
    monkeypatch.setattr(
        air_ui,
        "get_email_defaults",
        lambda: {"airfrance": {"to": "to@example.org", "cc": "cc@example.org", "bcc": ""}},
    )

    sent: list[dict[str, object]] = []

    def _fake_generate(**kwargs):
        sent.append(kwargs)
        return True

    monkeypatch.setattr(air_ui, "generate_airfrance_email", _fake_generate)

    pdf_path = tmp_path / "planning.pdf"
    pdf_path.write_text("pdf", encoding="utf-8")

    air_ui.render_email_airfrance_ui(
        df_comm=pd.DataFrame({"DATE": ["2026-01-19"]}),
        pdf_attachment_path=pdf_path,
    )

    assert sent
    assert sent[0]["week"] == 4
    assert sent[0]["year"] == 2026
    assert sent[0]["attachments"] == [str(pdf_path)]
    assert any("Pièce jointe" in msg for msg in stub.infos)
    assert any("Brouillon Air France créé" in msg for msg in stub.successes)


def test_render_email_asf_ui_reports_generation_error(monkeypatch):
    stub = _StubSt()
    stub.session_state["current_week"] = 5
    stub.session_state["current_year"] = 2026
    stub._button_values["📤 Générer le mail ASF Interne"] = True
    monkeypatch.setattr(asf_ui, "st", stub)
    monkeypatch.setattr(
        asf_ui,
        "get_email_defaults",
        lambda: {"asf_interne": {"to": "to@example.org", "cc": "", "bcc": ""}},
    )
    monkeypatch.setattr(asf_ui, "generate_asf_email", lambda **_kwargs: False)

    asf_ui.render_email_asf_ui(df_comm=pd.DataFrame({"DATE": ["2026-01-26"]}))

    assert any("Échec de création du mail ASF" in msg for msg in stub.errors)


def test_render_email_asf_ui_detects_week_year_and_success_with_attachment(monkeypatch, tmp_path):
    stub = _StubSt()
    stub._button_values["📤 Générer le mail ASF Interne"] = True
    monkeypatch.setattr(asf_ui, "st", stub)
    monkeypatch.setattr(
        asf_ui,
        "get_email_defaults",
        lambda: {"asf_interne": {"to": "to@example.org", "cc": "cc@example.org", "bcc": "bcc@example.org"}},
    )
    payloads: list[dict[str, object]] = []
    monkeypatch.setattr(
        asf_ui,
        "generate_asf_email",
        lambda **kwargs: payloads.append(kwargs) or True,
    )

    pdf_path = tmp_path / "planning.pdf"
    pdf_path.write_text("pdf", encoding="utf-8")
    asf_ui.render_email_asf_ui(
        df_comm=pd.DataFrame({"DATE": ["2026-01-19"]}),
        pdf_attachment_path=pdf_path,
    )

    assert payloads
    assert payloads[0]["week"] == 4
    assert payloads[0]["year"] == 2026
    assert payloads[0]["attachments"] == [str(pdf_path)]
    assert any("Pièce jointe" in msg for msg in stub.infos)
    assert any("Brouillon ASF Interne créé" in msg for msg in stub.successes)


def test_render_email_asf_ui_reports_error_when_week_year_cannot_be_detected(monkeypatch):
    stub = _StubSt()
    monkeypatch.setattr(asf_ui, "st", stub)
    asf_ui.render_email_asf_ui(df_comm=pd.DataFrame({"X": ["2026-01-19"]}))
    assert any("Impossible de détecter la semaine / année" in msg for msg in stub.errors)


def test_render_email_destinations_ui_covers_empty_and_single_destination_paths(monkeypatch):
    stub = _StubSt()
    monkeypatch.setattr(dest_ui, "st", stub)

    dest_ui.render_email_destinations_ui(
        df_comm=pd.DataFrame(),
        df_paramdest=pd.DataFrame([{"Dest_IATA": "RUN"}]),
        week=4,
        year=2026,
    )
    assert any("Aucun planning communication chargé" in msg for msg in stub.infos)

    stub2 = _StubSt()
    stub2._button_values["📤 Générer les mails pour toutes les destinations"] = True
    stub2._button_values["📤 Générer le mail pour RUN"] = True
    stub2._selectbox_values["Sélectionner une destination pour un envoi individuel"] = "RUN"
    monkeypatch.setattr(dest_ui, "st", stub2)
    monkeypatch.setattr(dest_ui, "generate_all_destination_emails", lambda **_kwargs: 2)
    monkeypatch.setattr(dest_ui, "generate_destination_email_for_destination", lambda **_kwargs: False)

    dest_ui.render_email_destinations_ui(
        df_comm=pd.DataFrame([{"Destination": "RUN"}]),
        df_paramdest=pd.DataFrame([{"Dest_IATA": "RUN"}]),
        week=4,
        year=2026,
    )

    assert any("2 mails Destinations générés" in msg for msg in stub2.successes)
    assert any("Échec pour la destination RUN" in msg for msg in stub2.errors)


def test_render_email_destinations_ui_warns_when_paramdest_missing(monkeypatch):
    stub = _StubSt()
    monkeypatch.setattr(dest_ui, "st", stub)

    dest_ui.render_email_destinations_ui(
        df_comm=pd.DataFrame([{"Destination": "RUN"}]),
        df_paramdest=pd.DataFrame(),
        week=4,
        year=2026,
    )
    assert any("ParamDest non chargé" in msg for msg in stub.warnings)


def test_render_email_destinations_ui_handles_empty_destination_values(monkeypatch):
    stub = _StubSt()
    monkeypatch.setattr(dest_ui, "st", stub)

    dest_ui.render_email_destinations_ui(
        df_comm=pd.DataFrame([{"Destination": None}, {"Destination": None}]),
        df_paramdest=pd.DataFrame([{"Dest_IATA": "RUN"}]),
        week=4,
        year=2026,
    )
    assert any("Aucune destination trouvée" in msg for msg in stub.infos)


def test_render_email_destinations_ui_individual_success_path(monkeypatch):
    stub = _StubSt()
    stub._button_values["📤 Générer le mail pour RUN"] = True
    stub._selectbox_values["Sélectionner une destination pour un envoi individuel"] = "RUN"
    monkeypatch.setattr(dest_ui, "st", stub)
    monkeypatch.setattr(dest_ui, "generate_destination_email_for_destination", lambda **_kwargs: True)

    dest_ui.render_email_destinations_ui(
        df_comm=pd.DataFrame([{"Destination": "RUN"}]),
        df_paramdest=pd.DataFrame([{"Dest_IATA": "RUN"}]),
        week=4,
        year=2026,
    )
    assert any("Mail Destination pour RUN généré" in msg for msg in stub.successes)


def test_render_email_expediteurs_ui_covers_global_and_targeted_send(monkeypatch):
    stub = _StubSt()
    stub._button_values["📤 Générer tous les mails Expéditeurs"] = True
    stub._button_values["📤 Générer les mails pour MEDILAB"] = True
    stub._selectbox_values["Sélectionner un expéditeur pour un envoi ciblé (toutes ses destinations)"] = "MEDILAB"
    monkeypatch.setattr(exp_ui, "st", stub)
    monkeypatch.setattr(exp_ui, "generate_all_expediteurs_emails", lambda **_kwargs: 3)
    monkeypatch.setattr(exp_ui, "index_pdfs_by_be", lambda: {})
    monkeypatch.setattr(
        exp_ui,
        "generate_expediteur_email_for_pair",
        lambda **kwargs: kwargs.get("destination") == "RUN",
    )

    df_comm = pd.DataFrame(
        [
            {"Expediteur": "ASF", "Destination": "DLA"},
            {"Expediteur": "MEDILAB", "Destination": "RUN"},
            {"Expediteur": "MEDILAB", "Destination": "DLA"},
        ]
    )

    exp_ui.render_email_expediteurs_ui(
        df_comm=df_comm,
        df_paramdest=pd.DataFrame([{"Dest_IATA": "RUN"}]),
        df_paramexpediteur=pd.DataFrame([{"Expediteur": "MEDILAB"}]),
        week=4,
        year=2026,
    )

    assert any("3 mails Expéditeurs générés" in msg for msg in stub.successes)
    # 1 destination réussit (RUN), 1 échoue (DLA)
    assert any("1 mails générés pour MEDILAB" in msg for msg in stub.successes)
