# -*- coding: utf-8 -*-
from __future__ import annotations

import asf_app.ui.ui_planning.utils as planning_utils


class _StubSt:
    def __init__(self):
        self.session_state: dict[str, object] = {}
        self.infos: list[str] = []
        self.warnings: list[str] = []

    def info(self, msg):
        self.infos.append(str(msg))

    def warning(self, msg):
        self.warnings.append(str(msg))


def test_show_mag_central_status_all_modes(monkeypatch):
    stub = _StubSt()
    monkeypatch.setattr(planning_utils, "st", stub)

    for mode in ["excel", "openpyxl", "no_updates", "missing", "read_error"]:
        stub.session_state["mag_central_write_method"] = mode
        planning_utils.show_mag_central_status()

    assert any("Excel" in msg for msg in stub.infos)
    assert any("openpyxl" in msg for msg in stub.warnings)
    assert any("aucune cellule" in msg for msg in stub.infos)
    assert any("introuvable" in msg for msg in stub.warnings)
    assert any("erreur d’ouverture" in msg for msg in stub.warnings)
