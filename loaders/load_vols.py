# loaders/load_vols.py
# -*- coding: utf-8 -*-

from datetime import datetime, date, time
from typing import List, Dict, Any
import pandas as pd

from scheduler.config_paths import (
    TABLEAU_DE_BORD,
    VOLS,
    SHEET_PARAM_DEST,
    SHEET_VOLS,
)

from loaders.universal_loader import load_and_normalize
from scheduler.column_map import (
    column_map_param_dest,
    column_map_vols,
)

# =====================================================================
# PARSING UNIFIÉ : DATES, HEURES, ROUTING
# =====================================================================

def parse_date(v) -> date | None:
    try:
        dt = pd.to_datetime(v, dayfirst=True, errors="coerce")
        if pd.isna(dt):
            return None
        return dt.date()
    except Exception:
        return None


def parse_excel_time(v) -> time | None:
    if v is None or str(v).strip() == "":
        return None

    if isinstance(v, time):
        return v
    if isinstance(v, datetime):
        return v.time()

    s = str(v).strip()
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).time()
        except Exception:
            pass

    try:
        vf = float(v)
        sec = int(vf * 86400)
        return time(sec // 3600, (sec % 3600) // 60, sec % 60)
    except Exception:
        return None


def parse_routing(v) -> List[str]:
    if not isinstance(v, str):
        return []
    v = v.strip().strip("[]")
    if not v:
        return []
    return [
        x.strip().strip("'").strip('"').upper()
        for x in v.split(",")
        if x.strip()
    ]


def clean_city(v: str) -> str:
    if not isinstance(v, str):
        return ""
    return (
        v.upper()
         .replace("(CAMEROUN)", "")
         .replace("(COTE D'IVOIRE)", "")
         .replace("(COTE D’IVOIRE)", "")
         .replace(",", "")
         .replace("É", "E")
         .replace("È", "E")
         .replace("Ê", "E")
         .strip()
    )


# =====================================================================
# CHARGEMENT DES VOLS — VERSION STABLE
# =====================================================================

def load_vols() -> List[Dict[str, Any]]:
    """
    Charge les vols normalisés.
    Retourne TOUJOURS une liste (jamais None).
    """

    print("\n=== LOAD_VOLS ===")

    # --------------------------------------------------------------
    # 1) ParamDest → ville → IATA / capacité
    # --------------------------------------------------------------
    df_param = load_and_normalize(
        path=TABLEAU_DE_BORD,
        sheet_name=SHEET_PARAM_DEST,
        mapping=column_map_param_dest,
        header=0,
    ).fillna("")

    ville_to_iata: Dict[str, str] = {}
    iata_to_capacity: Dict[str, int | None] = {}

    for _, r in df_param.iterrows():
        raw_ville = str(r.get("Dest_Ville", "")).strip().upper()
        ville_clean = clean_city(raw_ville)
        iata = str(r.get("Dest_IATA", "")).strip().upper()

        raw_cap = str(r.get("Max_Colis_Par_Vol", "")).strip()
        try:
            cap = int(raw_cap) if raw_cap else None
        except Exception:
            cap = None

        if raw_ville:
            ville_to_iata[raw_ville] = iata
        if ville_clean:
            ville_to_iata[ville_clean] = iata
        if iata:
            iata_to_capacity[iata] = cap

    print(f"ParamDest chargés : {len(df_param)} lignes")

    # --------------------------------------------------------------
    # 2) Vols.xlsx
    # --------------------------------------------------------------
    df_vols = load_and_normalize(
        path=VOLS,
        sheet_name=SHEET_VOLS,
        mapping=column_map_vols,
        header=0,
    ).fillna("")

    print(f"Vols bruts : {len(df_vols)}")
    try:
        print(df_vols.head(5))
    except Exception:
        pass

    vols_dict: Dict[str, Dict[str, Any]] = {}

    for _, r in df_vols.iterrows():

        num = str(r.get("Numero_Vol", "")).strip()
        if not num:
            continue

        d = parse_date(r.get("Date_Vol"))
        if d is None:
            continue

        t = parse_excel_time(r.get("Heure_Vol")) or time(0, 0)

        raw_city = str(r.get("Destination_Nom", "")).strip().upper()
        city_clean = clean_city(raw_city)

        # Routing
        routing_val = r.get("Route_API") or r.get("Routing") or ""
        routing = parse_routing(str(routing_val))

        # IATA : via ParamDest OU via routing
        iata = (
            ville_to_iata.get(city_clean)
            or ville_to_iata.get(raw_city)
            or (routing[1] if len(routing) > 1 else None)
        )

        cap = iata_to_capacity.get(iata)

        flight_id = f"{num}_{d}"

        if flight_id not in vols_dict:
            vols_dict[flight_id] = {
                "flight_number": str(num).zfill(4),
                "date": d,
                "departure_time": t,
                "routing": routing,
                "max_colis_base": cap,
            }

    print(f"➡ Vols retenus : {len(vols_dict)}")

    if vols_dict:
        print("\n=== DEBUG VOLS NORMALISÉS (aperçu) ===")
        for i, v in enumerate(list(vols_dict.values())[:10]):
            print(
                f" - Vol {v['flight_number']} | "
                f"Date={v['date']} | Heure={v['departure_time']} | "
                f"Routing={v['routing']} | Max={v['max_colis_base']}"
            )
        print("====================================\n")
    else:
        print("⚠️ Aucun vol après normalisation.\n")

    # 🔥 RETURN FINAL — TOUJOURS UNE LISTE
    return list(vols_dict.values())


# =====================================================================
# VERSION DATAFRAME — audit & communication
# =====================================================================

def load_vols_df() -> pd.DataFrame:
    vols = load_vols()
    if not vols:
        return pd.DataFrame()

    rows = []
    for v in vols:
        routing = v.get("routing", [])
        dest = routing[1] if len(routing) > 1 else ""
        rows.append({
            "Date_Vol": v.get("date"),
            "Heure_Vol": v.get("departure_time"),
            "Numero_Vol": v.get("flight_number"),
            "Destination": dest,
            "IATA": dest,
            "Routing": ",".join(routing),
            "Max_Colis": v.get("max_colis_base"),
        })

    return pd.DataFrame(rows)
