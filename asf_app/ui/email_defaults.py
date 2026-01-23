# asf_app/ui/email_defaults.py
# -*- coding: utf-8 -*-

from __future__ import annotations

from copy import deepcopy

try:
    import streamlit as st
except Exception:
    st = None

from asf_app.config.email_defaults import (
    load_email_defaults,
    normalize_email_defaults,
    save_email_defaults,
)


def get_email_defaults() -> dict:
    if st is not None:
        cached = st.session_state.get("email_defaults")
        if isinstance(cached, dict):
            return deepcopy(cached)
    defaults = load_email_defaults()
    if st is not None:
        st.session_state["email_defaults"] = deepcopy(defaults)
    return deepcopy(defaults)


def set_email_defaults(data: dict, *, persist: bool = False) -> dict:
    normalized = normalize_email_defaults(data)
    if persist:
        save_email_defaults(normalized)
    if st is not None:
        st.session_state["email_defaults"] = deepcopy(normalized)
        st.session_state["airfrance_to"] = normalized["airfrance"]["to"]
        st.session_state["airfrance_cc"] = normalized["airfrance"]["cc"]
        st.session_state["airfrance_bcc"] = normalized["airfrance"]["bcc"]
        st.session_state["asf_to"] = normalized["asf_interne"]["to"]
        st.session_state["asf_cc"] = normalized["asf_interne"]["cc"]
        st.session_state["asf_bcc"] = normalized["asf_interne"]["bcc"]
    return deepcopy(normalized)
