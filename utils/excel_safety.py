# utils/excel_safety.py
# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any

import pandas as pd

_FORMULA_PREFIXES = ("=", "+", "-", "@")


def sanitize_excel_value(value: Any) -> Any:
    """
    Prevent Excel formula injection by prefixing dangerous strings with a quote.
    """
    if isinstance(value, str):
        if value.startswith("'"):
            return value
        stripped = value.lstrip()
        if stripped.startswith(_FORMULA_PREFIXES):
            return "'" + value
    return value


def sanitize_dataframe_for_excel(df: pd.DataFrame | None) -> pd.DataFrame | None:
    if df is None:
        return None
    out = df.copy()
    for col in out.columns:
        if out[col].dtype == object:
            out[col] = out[col].map(sanitize_excel_value)
    return out
