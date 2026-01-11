# utils/ui_notifications.py
# -*- coding: utf-8 -*-

from __future__ import annotations


def warn_ui(message: str) -> None:
    try:
        import streamlit as st
        st.warning(message)
    except Exception:
        pass


def info_ui(message: str) -> None:
    try:
        import streamlit as st
        st.info(message)
    except Exception:
        pass


def error_ui(message: str) -> None:
    try:
        import streamlit as st
        st.error(message)
    except Exception:
        pass
