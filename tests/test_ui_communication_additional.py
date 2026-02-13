# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import pandas as pd

import asf_app.ui.ui_communication.ui_communication as comm


class _StubSt:
    def __init__(self):
        self.session_state: dict[str, object] = {}
        self._button_values: dict[str, list[bool]] = {}
        self._radio_values: dict[str, object] = {}
        self.successes: list[str] = []
        self.warnings: list[str] = []
        self.infos: list[str] = []

    def set_button_sequence(self, label: str, values: list[bool]):
        self._button_values[label] = list(values)

    def button(self, label, **_kwargs):
        seq = self._button_values.get(label)
        if seq:
            return seq.pop(0)
        return False

    def radio(self, label, options, index=0, key=None, **_kwargs):
        if key and key in self._radio_values:
            return self._radio_values[key]
        if label in self._radio_values:
            return self._radio_values[label]
        return options[index]

    def markdown(self, *_args, **_kwargs):
        return None

    def code(self, *_args, **_kwargs):
        return None

    def success(self, msg):
        self.successes.append(str(msg))

    def warning(self, msg):
        self.warnings.append(str(msg))

    def info(self, msg):
        self.infos.append(str(msg))

    def columns(self, n, **_kwargs):
        _ = _kwargs
        return [self for _ in range(int(n))]


def test_resolve_pdf_attachment_path_local_and_graph(monkeypatch, tmp_path):
    stub = _StubSt()
    monkeypatch.setattr(comm, "st", stub)

    monkeypatch.setattr(comm, "is_graph_onedrive", lambda: False)
    monkeypatch.setattr(
        comm,
        "_resolve_pdf_candidates_from_local",
        lambda _week, _year: [Path("a.pdf"), Path("b.pdf")],
    )
    local_path = comm._resolve_pdf_attachment_path(week=4, year=2026)
    assert local_path == Path("a.pdf")

    monkeypatch.setattr(comm, "is_graph_onedrive", lambda: True)
    monkeypatch.setattr(
        comm,
        "_resolve_pdf_candidates_from_graph",
        lambda _week, _year: [{"name": "remote.pdf", "path": "Planning/remote.pdf"}],
    )
    monkeypatch.setattr(comm, "get_tmp_dir", lambda: tmp_path)
    monkeypatch.setattr(comm, "safe_cache_path", lambda _root, _remote: tmp_path / "remote.pdf")
    monkeypatch.setattr(
        comm.cp,
        "download_onedrive_file",
        lambda _remote, local, interactive=False: (Path(local).write_bytes(b"%PDF") or True),
    )

    graph_path = comm._resolve_pdf_attachment_path(week=4, year=2026)
    assert graph_path == tmp_path / "remote.pdf"


def test_render_selected_communication_section_dispatch(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(comm, "_render_whatsapp_section", lambda _df: calls.append("whatsapp"))
    monkeypatch.setattr(comm, "render_email_airfrance_ui", lambda **_kwargs: calls.append("airfrance"))
    monkeypatch.setattr(comm, "render_email_asf_ui", lambda **_kwargs: calls.append("asf"))
    monkeypatch.setattr(comm, "render_email_destinations_ui", lambda **_kwargs: calls.append("dest"))
    monkeypatch.setattr(comm, "render_email_expediteurs_ui", lambda **_kwargs: calls.append("exp"))

    kwargs = {
        "df_comm": pd.DataFrame([{"x": 1}]),
        "df_paramdest": pd.DataFrame(),
        "df_paramexpediteur": pd.DataFrame(),
        "week": 4,
        "year": 2026,
        "pdf_attach_path": None,
    }
    comm._render_selected_communication_section(section="whatsapp", **kwargs)
    comm._render_selected_communication_section(section="airfrance", **kwargs)
    comm._render_selected_communication_section(section="asf", **kwargs)
    comm._render_selected_communication_section(section="dest", **kwargs)
    comm._render_selected_communication_section(section="exp", **kwargs)

    assert calls == ["whatsapp", "airfrance", "asf", "dest", "exp"]


def test_render_whatsapp_section_generates_and_opens(monkeypatch):
    stub = _StubSt()
    stub.set_button_sequence("Générer les messages WhatsApp", [True])
    stub.set_button_sequence("📲 Envoyer WhatsApp à ALICE", [True])
    monkeypatch.setattr(comm, "st", stub)

    monkeypatch.setattr(
        comm,
        "generate_whatsapp_messages",
        lambda _df: [
            {
                "benevole": "ALICE",
                "telephone": "0600000000",
                "message": "Bonjour",
                "url": "https://wa.example/alice",
            }
        ],
    )
    opened: list[str] = []
    monkeypatch.setattr(comm, "open_whatsapp_for_benevole", lambda url: opened.append(url))

    comm._render_whatsapp_section(pd.DataFrame([{"x": 1}]))

    assert any("messages générés" in msg for msg in stub.successes)
    assert opened == ["https://wa.example/alice"]


def test_render_comm_sections_bar_switches_section(monkeypatch):
    stub = _StubSt()
    stub.session_state["comm_section"] = "whatsapp"
    stub.set_button_sequence("✈️ Air France", [True])
    monkeypatch.setattr(comm, "st", stub)

    section = comm._render_comm_sections_bar()

    assert section == "airfrance"
    assert stub.session_state["comm_section"] == "airfrance"
