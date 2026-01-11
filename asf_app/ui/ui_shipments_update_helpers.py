# -*- coding: utf-8 -*-

from __future__ import annotations

import pandas as pd

from utils.identifiers import format_vol_display, normalize_be_number


def _norm_be(val: object) -> str:
    return normalize_be_number(val)


def _fmt_date_long(val: object) -> str:
    try:
        d = pd.to_datetime(val)
    except Exception:
        return str(val)
    if pd.isna(d):
        return ""
    jours = {
        "Monday": "Lundi",
        "Tuesday": "Mardi",
        "Wednesday": "Mercredi",
        "Thursday": "Jeudi",
        "Friday": "Vendredi",
        "Saturday": "Samedi",
        "Sunday": "Dimanche",
    }
    return f"{jours.get(d.day_name(), d.strftime('%A'))} {d.strftime('%d/%m/%y')}"


def _fmt_time(val: object) -> str:
    t = pd.to_datetime(str(val), errors="coerce")
    if pd.isna(t):
        return str(val)
    return t.strftime("%Hh%M")


def _fmt_vol(val: object) -> str:
    return format_vol_display(val) or str(val)


def _wrap_body(lines: list[str]) -> str:
    body = "<br>".join([str(l) for l in lines if l is not None])
    return f"<div style='font-family: Aptos, Segoe UI, sans-serif; font-size: 12pt;'>{body}</div>"
