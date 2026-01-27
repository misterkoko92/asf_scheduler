# -*- coding: utf-8 -*-

from __future__ import annotations

from utils.datetime_utils import format_date_long_fr, format_time_value
from utils.identifiers import format_vol_display, normalize_be_number


def _norm_be(val: object) -> str:
    return normalize_be_number(val)


def _fmt_date_long(val: object) -> str:
    if val is None or str(val).strip() == "":
        return ""
    return format_date_long_fr(val, default=None)


def _fmt_time(val: object) -> str:
    out = format_time_value(val, allow_general_fallback=True, default=None)
    return out if out not in (None, "") else str(val)


def _fmt_vol(val: object) -> str:
    return format_vol_display(val) or str(val)


def _wrap_body(lines: list[str]) -> str:
    body = "<br>".join([str(l) for l in lines if l is not None])
    return f"<div style='font-family: Aptos, Segoe UI, sans-serif; font-size: 12pt;'>{body}</div>"
