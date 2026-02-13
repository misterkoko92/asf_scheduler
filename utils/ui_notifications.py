# utils/ui_notifications.py
# -*- coding: utf-8 -*-

from __future__ import annotations

UI_NOTIFICATION_ERRORS = (
    ImportError,
    ModuleNotFoundError,
    AttributeError,
    RuntimeError,
    TypeError,
    ValueError,
)


def warn_ui(message: str) -> None:
    try:
        import streamlit as st
        st.warning(message)
    except UI_NOTIFICATION_ERRORS:
        pass


def info_ui(message: str) -> None:
    try:
        import streamlit as st
        st.info(message)
    except UI_NOTIFICATION_ERRORS:
        pass


def error_ui(message: str) -> None:
    try:
        import streamlit as st
        st.error(message)
    except UI_NOTIFICATION_ERRORS:
        pass
