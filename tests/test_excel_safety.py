# -*- coding: utf-8 -*-
from __future__ import annotations

import pandas as pd

from utils.excel_safety import sanitize_excel_value, sanitize_dataframe_for_excel


def test_sanitize_excel_value_formula_prefixes():
    assert sanitize_excel_value("=1+1") == "'=1+1"
    assert sanitize_excel_value("+SUM(A1)") == "'+SUM(A1)"
    assert sanitize_excel_value(" -1") == "' -1"
    assert sanitize_excel_value("@cmd") == "'@cmd"
    assert sanitize_excel_value("'=1+1") == "'=1+1"
    assert sanitize_excel_value(123) == 123


def test_sanitize_dataframe_for_excel():
    df = pd.DataFrame({"a": ["=1", "ok"], "b": [1, 2]})
    out = sanitize_dataframe_for_excel(df)
    assert out["a"].tolist() == ["'=1", "ok"]
    assert out["b"].tolist() == [1, 2]
