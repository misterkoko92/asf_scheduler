# -*- coding: utf-8 -*-
from __future__ import annotations

import pandas as pd

from loaders.universal_loader import normalize_header, fuzzy_match_columns


def test_normalize_header_strips_accents_and_spaces():
    assert normalize_header("Téléphone 1") == "TELEPHONE 1"
    assert normalize_header("  DATE  DE  DEPART  ") == "DATE DE DEPART"


def test_fuzzy_match_columns_basic():
    df = pd.DataFrame({"N° BE": [1], "DATE IMPRESSION BE": ["01/01/2025"]})
    mapping = {"N° BE": "BE_Numero", "DATE IMPRESSION BE": "BE_Date_Impression"}
    df2 = fuzzy_match_columns(df, mapping)
    assert "BE_Numero" in df2.columns
    assert "BE_Date_Impression" in df2.columns
