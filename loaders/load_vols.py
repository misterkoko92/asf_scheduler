# loaders/load_vols.py
# -*- coding: utf-8 -*-

import pandas as pd
from datetime import datetime, date, time
from typing import List, Dict, Any

from scheduler.config_paths import (
    TABLEAU_DE_BORD,
    VOLS,
    SHEET_PARAM_DEST,
)


# -----------------------------------------
#   PARSE DATE
# -----------------------------------------
def parse_date(v) -> date | None:
    try:
        return pd.to_datetime(v, dayfirst=True).date()
    except Exception:
        return None


# -----------------------------------------
#   PARSE HEURE EXCEL / STRING
# -----------------------------------------
def parse_excel_time(v) -> time | None:
    """
    Convertit PVOL_HEURE (format Excel ou texte) en datetime.time
    - "10:25"
    - datetime.time
    - Excel float
    """
    if v is None or v == "":
        return None

    if isinstance(v, time):
        return v

    if isinstance(v, datetime):
        return v.time()

    if isinstance(v, str):
        s = v.strip()
        try:
            return datetime.strptime(s, "%H:%M").time()
        except:
            pass
        try:
            return pd.to_datetime(s).time()
        except:
            pass

    try:
        vf = float(v)
        total_seconds = int(vf * 24 * 3600)
        hh = total_seconds // 3600
        mm = (total_seconds % 3600) // 60
        ss = total_seconds % 60
        return time(hh, mm, ss)
    except:
        return None


# -----------------------------------------
#   PARSE ROUTING
# -----------------------------------------
def parse_routing(s) -> List[str]:
    if not isinstance(s, str):
        return []
    s = s.strip().strip("[]")
    return [x.strip().strip("'").strip('"') for x in s.split(",") if x.strip()]


# -----------------------------------------
#   LOAD VOLs
# -----------------------------------------
def load_vols() -> List[Dict[str, Any]]:
    """
    Charge les vols depuis Vols.xlsx
    + les mappings & capacités depuis TABLEAU DE BORD.xlsx / ParamDest
    """

    # ======================================================
    # 1) LECTURE ParamDest (dans TABLEAU_DE_BORD)
    # ======================================================
    df_param = pd.read_excel(
        TABLEAU_DE_BORD,
        sheet_name=SHEET_PARAM_DEST,
        dtype=str
    ).fillna("")

    ville_to_iata: Dict[str, str] = {}
    iata_to_capacity: Dict[str, int | None] = {}

    for _, r in df_param.iterrows():
        ville = str(r.get("Ville", "")).upper().strip()
        iata = str(r.get("Destination", "")).upper().strip()

        raw_cap = str(r.get("Max_Colis_Par_Vol", "")).strip()
        try:
            cap = int(raw_cap) if raw_cap else None
        except:
            cap = None

        if ville:
            ville_to_iata[ville] = iata
        if iata:
            iata_to_capacity[iata] = cap

    print("[VOL_LOADER] Mapping villes -> IATA :", ville_to_iata)
    print("[VOL_LOADER] Capacités :", iata_to_capacity)

    # ======================================================
    # 2) LECTURE Vols.xlsx
    # ======================================================
    df_vols = pd.read_excel(VOLS, dtype=str).fillna("")

    vols_dict: Dict[str, Dict[str, Any]] = {}

    for _, r in df_vols.iterrows():

        num = str(r.get("PVOL_NUMERO", "")).strip()

        d = parse_date(r.get("PVOL_DATE", ""))
        t = parse_excel_time(r.get("PVOL_HEURE", ""))
        if t is None:
            t = time(0, 0)

        ville_raw = str(r.get("PVOL_FK_DESTINATION", "")).upper().strip()

        # Nettoyage robuste ville
        ville_clean = (
            ville_raw.replace("(CAMEROUN)", "")
                     .replace("(COTE D'IVOIRE)", "")
                     .replace("(COTE D’IVOIRE)", "")
                     .replace(",", "")
                     .replace("É", "E")
                     .replace("È", "E")
                     .replace("Ê", "E")
                     .strip()
        )

        routing = parse_routing(r.get("PVOL_ROUTE_API", ""))

        iata = (
            ville_to_iata.get(ville_clean)
            or ville_to_iata.get(ville_raw)
            or None
        )

        cap = iata_to_capacity.get(iata)

        print(f"[VOL_LOADER] {num} {d} {t} ville={ville_raw} → IATA={iata} CAP={cap}")

        if d is None:
            continue

        flight_id = f"{num}_{d}"

        if flight_id not in vols_dict:
            vols_dict[flight_id] = {
                "flight_number": num.zfill(4),
                "date": d,
                "departure_time": t,
                "routing": routing,
                "max_colis_base": cap,
            }

    return list(vols_dict.values())
