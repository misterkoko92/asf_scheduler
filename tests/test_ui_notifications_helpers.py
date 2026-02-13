# -*- coding: utf-8 -*-
from __future__ import annotations

import sys

from utils import ui_notifications as ui_notif


def test_ui_notifications_ignore_missing_streamlit(monkeypatch):
    monkeypatch.setitem(sys.modules, "streamlit", object())

    ui_notif.warn_ui("warn")
    ui_notif.info_ui("info")
    ui_notif.error_ui("error")
