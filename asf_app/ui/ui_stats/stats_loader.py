# asf_app/ui/ui_stats/stats_loader.py
# -*- coding: utf-8 -*-

import pandas as pd
from pathlib import Path
from typing import List
from asf_app.ui.ui_stats.ui_stats import load_planning_xlsx


def load_all_plannings(base_dir: Path) -> pd.DataFrame:
    """
    Charge et fusionne tous les plannings ASFmm 2025 (toutes versions).
    Utilise load_planning_xlsx (robuste index-based).

    Retour : DataFrame fusionné, avec colonne 'week'
    """

    files = sorted(
        list(base_dir.glob("ASFmm - PLANNING SEMAINE N° *.xls*")),
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
        try:
            wk = int(f.stem.split("N°")[1].split("-")[0].strip())
        except Exception:
            wk = None

        df = df.copy()
        df["week"] = wk
        df["filename"] = f.name

        all_rows.append(df)

    if not all_rows:
        return pd.DataFrame()

    return pd.concat(all_rows, ignore_index=True)
