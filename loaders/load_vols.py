# loaders/load_vols.py
# -*- coding: utf-8 -*-

from datetime import datetime, date, time
from typing import List, Dict, Any
from pathlib import Path
import pandas as pd

from scheduler.config_paths import (
    TABLEAU_DE_BORD,
    VOLS,
    VOLS_SRC,
    SHEET_PARAM_DEST,
    SHEET_VOLS,
)
import scheduler.config_paths as cp

from loaders.universal_loader import load_and_normalize
from scheduler.column_map import (
    column_map_param_dest,
    column_map_vols,
)
from loaders.load_params import get_param_dest
from utils.datetime_utils import (
    parse_date_series,
    parse_time_series,
    normalize_hour_str,
    hour_min_from_series,
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

    s = str(v).strip().replace("h", ":")
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
    # Accepte séparateur virgule ou tiret
    parts: List[str] = []
    for chunk in v.replace(" ", "").replace("-", ",").split(","):
        if chunk:
            parts.append(chunk.upper())
    return parts


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

def load_vols(
    *,
    vols_path: Path | None = None,
    param_dest_df: pd.DataFrame | None = None,
) -> List[Dict[str, Any]]:
    """
    Charge les vols normalisés.
    Retourne TOUJOURS une liste (jamais None).
    """

    print("\n=== LOAD_VOLS ===")

    # --------------------------------------------------------------
    # 1) ParamDest → ville → IATA / capacité
    # --------------------------------------------------------------
    df_param = (param_dest_df.copy() if param_dest_df is not None else get_param_dest().copy())
    # Remplir uniquement les colonnes non numériques avec ""
    obj_cols = df_param.select_dtypes(exclude=["number"]).columns
    for c in obj_cols:
        df_param[c] = df_param[c].fillna("")

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
    # 2) Vols.xlsx (onglet Vols) — source principale
    # --------------------------------------------------------------
    df_vols = load_and_normalize(
        path=(vols_path or VOLS),
        sheet_name=SHEET_VOLS,
        mapping=column_map_vols,
        header=0,
    ).fillna("")

    # Appliquer le même normalisateur aux onglets API pour récupérer date/heure/routing IATA
    def normalize_api_sheet(df_api_raw: pd.DataFrame) -> pd.DataFrame:
        df_api = df_api_raw.copy().fillna("")
        # Alignement minimal pour reuse du parse
        rename_map = {
            "Date": "Date_Vol",
            "Heure": "Heure_Vol",
            "Numéro": "Numero_Vol",
        }
        for old, new in rename_map.items():
            if old in df_api.columns and new not in df_api.columns:
                df_api[new] = df_api[old]
        return df_api

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
        # normalisation numéro de vol (int -> str sans décimale) et suppression préfixe AF éventuel
        num_clean = num.replace("AF", "").replace("af", "").strip()
        try:
            num_int = int(float(num_clean))
            num = str(num_int)
        except Exception:
            # fallback: extraire les chiffres si possible
            digits = "".join(ch for ch in num_clean if ch.isdigit())
            num = digits if digits else num_clean

        d = parse_date(r.get("Date_Vol"))
        if d is None:
            continue

        t = parse_excel_time(r.get("Heure_Vol")) or time(0, 0)

        raw_city = str(r.get("Destination_Nom", "")).strip().upper()
        city_clean = clean_city(raw_city)

        # Routing
        routing_val = r.get("Route_API") or r.get("Routing") or ""
        routing = parse_routing(str(routing_val))
        if routing and routing[-1] == "CDG":
            routing = routing[:-1]

        # IATA : via ParamDest OU via routing
        iata = (
            ville_to_iata.get(city_clean)
            or ville_to_iata.get(raw_city)
            or (routing[1] if len(routing) > 1 else None)
        )

        cap = iata_to_capacity.get(iata)

        dest_iata = routing[1] if len(routing) > 1 else ""
        if not dest_iata:
            continue

        flight_id = f"{num}_{d}_{dest_iata}"

        vols_dict[flight_id] = {
            "flight_number": str(num).zfill(4),
            "date": d,
            "departure_time": t,
            "routing": routing,
            "max_colis_base": cap,
            "source": "excel",
        }

    # ------------------------------------------------------------------
    # 2bis) Onglets API-Sxx-YYYY (fichier source) + fallback si aucun vol
    # ------------------------------------------------------------------
    def _ingest_api_sheets(path_excel: str):
        try:
            api_book = pd.read_excel(path_excel, sheet_name=None, dtype=str, engine="openpyxl")
        except Exception:
            return
        for sheet_name, df_api in api_book.items():
            if not str(sheet_name).upper().startswith("API-"):
                continue
            if df_api is None or df_api.empty:
                continue
            df_api = normalize_api_sheet(df_api)
            for _, r in df_api.iterrows():
                num_raw = str(r.get("Numero_Vol", "")).strip()
                if not num_raw:
                    continue
                num_clean = num_raw.replace("AF", "").replace("af", "").strip()
                try:
                    num_int = int(float(num_clean))
                    num_api = str(num_int)
                except Exception:
                    digits = "".join(ch for ch in num_clean if ch.isdigit())
                    num_api = digits if digits else num_clean

                d = parse_date(r.get("Date_Vol"))
                if d is None:
                    continue
                t = parse_excel_time(r.get("Heure_Vol")) or time(0, 0)

                routing_full = parse_routing(r.get("Routing", ""))
                if routing_full and routing_full[-1] == "CDG":
                    routing_full = routing_full[:-1]
                if len(routing_full) < 2:
                    continue
                cap = r.get("Max_Colis")
                try:
                    cap = int(cap) if cap not in ("", None) else None
                except Exception:
                    cap = None

                # Crée une entrée par destination, avec le routing complet (sans retour CDG)
                full_route = routing_full
                for idx in range(1, len(full_route)):
                    dest_key = full_route[idx]
                    flight_id = f"{num_api}_{d}_{dest_key}"
                    vols_dict[flight_id] = {
                        "flight_number": str(num_api).zfill(4),
                        "date": d,
                        "departure_time": t,
                        "routing": full_route,
                        "max_colis_base": cap,
                        "source": "api",
                    }

    # Ingestion des feuilles API du source
    vols_src_path = vols_path or cp.VOLS_SRC
    _ingest_api_sheets(vols_src_path)
    # Fallback : si aucun vol retenu après le sheet principal, on lit aussi les feuilles API de la copie TMP
    if not vols_dict:
        _ingest_api_sheets(vols_path or cp.VOLS)

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

def load_vols_df(
    *,
    vols_path: Path | None = None,
    param_dest_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    vols = load_vols(vols_path=vols_path, param_dest_df=param_dest_df)
    if not vols:
        return pd.DataFrame()

    # mapping IATA -> ville depuis ParamDest
    df_param = param_dest_df if param_dest_df is not None else get_param_dest()
    iata_to_city = {str(r.get("Dest_IATA", "")).upper(): str(r.get("Dest_Ville", "")).upper() for _, r in df_param.iterrows()}

    rows = []
    for v in vols:
        routing = v.get("routing", [])
        # Routing complet sans retour CDG (si présent)
        routing_use = routing

        dest_iata = routing_use[1] if len(routing_use) > 1 else ""
        dest_city = iata_to_city.get(dest_iata, dest_iata)
        raw_num = str(v.get("flight_number", "")).strip()
        num_formatted = raw_num
        try:
            num_formatted = str(int(raw_num))  # retire les zéros superflus
        except Exception:
            pass
        rows.append({
            "Date_Vol": v.get("date"),
            "Heure_Vol": v.get("departure_time"),
            "Numero_Vol": f"AF {num_formatted}",
            "Destination": dest_city,
            "IATA": dest_iata,
            "Routing": "-".join(routing_use),
            "Max_Colis": v.get("max_colis_base"),
            "Source": v.get("source", "excel"),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df["Max_Colis"] = pd.to_numeric(df["Max_Colis"], errors="coerce").astype("Int64")
        df = df.drop_duplicates(subset=["Date_Vol", "Numero_Vol", "Destination"]).reset_index(drop=True)
        # Formattage heures / dates via helpers
        if "Date_Vol" in df.columns:
            df["Date_Vol_dt"] = parse_date_series(df["Date_Vol"])
            df["Date_Vol"] = df["Date_Vol_dt"].dt.strftime("%d/%m/%y")
        if "Heure_Vol" in df.columns:
            df["Heure_Vol_dt"] = parse_time_series(df["Heure_Vol"])
            df["Heure_Vol"] = normalize_hour_str(df["Heure_Vol"]).fillna("")
            df["HEURE_MIN"] = hour_min_from_series(df["Heure_Vol"])
    return df


# Cache Streamlit optionnel
try:
    import streamlit as st

    @st.cache_data(show_spinner=False)
    def get_vols_df_cached() -> pd.DataFrame:
        return load_vols_df()

except Exception:
    def get_vols_df_cached() -> pd.DataFrame:
        return load_vols_df()


def clear_vols_cache() -> None:
    cached = globals().get("get_vols_df_cached")
    if cached is not None and hasattr(cached, "clear"):
        try:
            cached.clear()
        except Exception:
            pass
