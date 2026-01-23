# asf_app/config/email_defaults.py
# -*- coding: utf-8 -*-

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


EMAIL_DEFAULTS_PATH = Path(__file__).parent / "email_defaults.yml"

DEFAULT_EMAIL_DEFAULTS = {
    "airfrance": {
        "to": "nafontaine1@airfrance.fr; anchanet@airfrance.fr",
        "cc": (
            "messmed@aviation-sans-frontieres-fr.org; "
            "f.cottence@samsic.aero; m.dorigny@gsf.fr; "
            "a.joyeux@gsf.fr; s.chadli@samsic.aero; pestarland@airfrance.fr"
        ),
        "bcc": "",
    },
    "asf_interne": {
        "to": "messmed@aviation-sans-frontieres-fr.org",
        "cc": "",
        "bcc": (
            "tousmessmed@asf-fr.net; "
            "michael.blanc@aviation-sans-frontieres-fr.org; "
            "myriam.devred@aviation-sans-frontieres-fr.org; "
            "barbara.dibat@aviation-sans-frontieres-fr.org"
        ),
    },
}


def _coerce_emails(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        parts = [str(v).strip() for v in value if str(v).strip()]
        return "; ".join(parts)
    return str(value).strip()


def normalize_email_defaults(data: dict | None) -> dict:
    base = deepcopy(DEFAULT_EMAIL_DEFAULTS)
    if not isinstance(data, dict):
        return base
    for key in base:
        if not isinstance(data.get(key), dict):
            continue
        entry = data.get(key, {})
        base[key]["to"] = _coerce_emails(entry.get("to", base[key]["to"]))
        base[key]["cc"] = _coerce_emails(entry.get("cc", base[key]["cc"]))
        base[key]["bcc"] = _coerce_emails(entry.get("bcc", base[key]["bcc"]))
    return base


def load_email_defaults() -> dict:
    if not EMAIL_DEFAULTS_PATH.exists():
        return deepcopy(DEFAULT_EMAIL_DEFAULTS)
    try:
        with open(EMAIL_DEFAULTS_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        data = {}
    return normalize_email_defaults(data)


def save_email_defaults(data: dict) -> None:
    payload = normalize_email_defaults(data)
    EMAIL_DEFAULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(EMAIL_DEFAULTS_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, allow_unicode=False, sort_keys=False)
