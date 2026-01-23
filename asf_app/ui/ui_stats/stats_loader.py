# asf_app/ui/ui_stats/stats_loader.py
# -*- coding: utf-8 -*-

import pandas as pd
from pathlib import Path
from typing import List
import re
from asf_app.ui.ui_stats.ui_stats import load_planning_xlsx


def load_all_plannings(base_dir: Path) -> pd.DataFrame:
    """
    Charge et fusionne tous les plannings ASFmm 2025 (toutes versions).
    Utilise load_planning_xlsx (robuste index-based).

    Retour : DataFrame fusionné, avec colonne 'week'
    """

    files = sorted(
        list(base_dir.glob("ASFmm - PLANNING SEMAINE *.xls*")),
        key=lambda f: f.stat().st_mtime,
    )

    if not files:
        return pd.DataFrame()

    all_rows = []

    for f in files:
        df = load_planning_xlsx(f)
        if df.empty:
            continue

        # Extraire SEMAINE depuis le nom
        wk = None
        try:
            m_new = re.search(r"SEMAINE\s*20\d{2}\D+(\d{1,2})", f.stem, re.IGNORECASE)
            if m_new:
                wk = int(m_new.group(1))
            else:
                m_old = re.search(r"N[°o]?\s*(\d{1,2})", f.stem, re.IGNORECASE)
                if m_old:
                    wk = int(m_old.group(1))
        except Exception:
            wk = None

        df = df.copy()
        df["week"] = wk
        df["filename"] = f.name

        all_rows.append(df)

    if not all_rows:
        return pd.DataFrame()

    return pd.concat(all_rows, ignore_index=True)
