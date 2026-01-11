# utils/identifiers.py
# -*- coding: utf-8 -*-

from __future__ import annotations

import re
from typing import Any


_NON_DIGIT_RE = re.compile(r"\D+")


def digits_only(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return _NON_DIGIT_RE.sub("", text)


def normalize_be_number(value: Any) -> str:
    digits = digits_only(value)
    if not digits:
        return ""
    if len(digits) >= 6:
        return digits[-6:]
    return digits.zfill(6)


def normalize_vol_number(value: Any) -> str:
    digits = digits_only(value)
    if not digits:
        return ""
    digits = digits.lstrip("0")
    return digits or ""


def format_be_number(value: Any) -> str:
    return normalize_be_number(value)


def format_vol_number(value: Any) -> str:
    return normalize_vol_number(value)


def format_be_display(value: Any) -> str:
    base = normalize_be_number(value)
    return f"BE {base}" if base else ""


def format_vol_display(value: Any) -> str:
    base = normalize_vol_number(value)
    return f"AF {base}" if base else ""
