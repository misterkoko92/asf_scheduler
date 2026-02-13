# loaders/load_vols.py
# -*- coding: utf-8 -*-

import logging
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, Dict, List
from zipfile import BadZipFile

import pandas as pd

import scheduler.config_paths as cp
from loaders.load_params import get_param_dest
from loaders.universal_loader import load_and_normalize
from scheduler.column_map import (
    column_map_vols,
)
from scheduler.config_paths import (
    SHEET_VOLS,
    TABLEAU_DE_BORD,
    VOLS,
)
from utils.cache_utils import file_mtime
from utils.datetime_utils import (
    hour_min_from_series,
    normalize_hour_str,
    parse_date_series,
    parse_time_series,
)
from utils.ui_notifications import warn_ui

logger = logging.getLogger("ASF-SCHEDULER")

# Compat tests/monkeypatch: keep direct module attribute.
VOLS_SRC = cp.VOLS_SRC


# =====================================================================
# PARSING UNIFIÉ : DATES, HEURES, ROUTING
# =====================================================================

def parse_date(v) -> date | None:
    try:
        dt = pd.to_datetime(v, dayfirst=True, errors="coerce")
        if pd.isna(dt):
            return None
        return dt.date()
    except (TypeError, ValueError, AttributeError):
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
        except ValueError:
            pass

    try:
        vf = float(v)
        sec = int(vf * 86400)
        return time(sec // 3600, (sec % 3600) // 60, sec % 60)
    except (TypeError, ValueError, OverflowError):
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


def _normalize_flight_number(raw: object) -> str:
    value = str(raw or "").strip()
    if not value:
        return ""
    clean_value = value.replace("AF", "").replace("af", "").strip()
    try:
        return str(int(float(clean_value)))
    except (TypeError, ValueError, OverflowError):
        digits = "".join(ch for ch in clean_value if ch.isdigit())
        return digits if digits else clean_value


def _unique_ordered_codes(codes: List[str]) -> List[str]:
    deduped: List[str] = []
    seen: set[str] = set()
    for code in codes:
        clean_code = str(code or "").strip().upper()
        if not clean_code or clean_code in seen:
            continue
        deduped.append(clean_code)
        seen.add(clean_code)
    return deduped


def _destinations_from_routing(routing: List[str], fallback_iata: str | None = None) -> List[str]:
    if len(routing) > 1:
        return _unique_ordered_codes(routing[1:])
    if fallback_iata:
        return _unique_ordered_codes([fallback_iata])
    return []


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

    logger.info("LOAD_VOLS start")

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
        iata_code = str(r.get("Dest_IATA", "")).strip().upper()

        raw_cap = str(r.get("Max_Colis_Par_Vol", "")).strip()
        try:
            cap = int(raw_cap) if raw_cap else None
        except (TypeError, ValueError):
            cap = None

        if raw_ville:
            ville_to_iata[raw_ville] = iata_code
        if ville_clean:
            ville_to_iata[ville_clean] = iata_code
        if iata_code:
            iata_to_capacity[iata_code] = cap

    logger.info("ParamDest charges: %s lignes", len(df_param))

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

    logger.info("Vols bruts: %s", len(df_vols))
    try:
        logger.debug("Vols bruts apercu:\n%s", df_vols.head(5).to_string(index=False))
    except (TypeError, ValueError, AttributeError):
        pass

    vols_dict: Dict[str, Dict[str, Any]] = {}

    for _, r in df_vols.iterrows():

        num = str(r.get("Numero_Vol", "")).strip()
        if not num:
            continue
        # normalisation numéro de vol (int -> str sans décimale) et suppression préfixe AF éventuel
        num = _normalize_flight_number(num)

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
        resolved_iata: str | None = (
            ville_to_iata.get(city_clean)
            or ville_to_iata.get(raw_city)
            or (routing[1] if len(routing) > 1 else None)
        )

        origin_iata = routing[0] if routing else "CDG"
        route_pos_map: Dict[str, int] = {}
        for idx, code in enumerate(routing[1:], start=1):
            normalized_code = str(code or "").strip().upper()
            if normalized_code and normalized_code not in route_pos_map:
                route_pos_map[normalized_code] = idx
        destinations = _destinations_from_routing(routing, fallback_iata=resolved_iata)
        if not destinations:
            continue

        for dest_iata in destinations:
            route_pos = route_pos_map.get(dest_iata, 1)
            cap = iata_to_capacity.get(dest_iata)
            flight_id = f"{num}_{d}_{dest_iata}"
            vols_dict[flight_id] = {
                "flight_number": str(num).zfill(4),
                "date": d,
                "departure_time": t,
                "routing": [origin_iata, dest_iata],
                "routing_full": routing or [origin_iata, dest_iata],
                "dest_iata": dest_iata,
                "route_pos": route_pos,
                "max_colis_base": cap,
                "source": "excel",
            }

    # ------------------------------------------------------------------
    # 2bis) Onglets API-Sxx-YYYY (fichier source) + fallback si aucun vol
    # ------------------------------------------------------------------
    def _ingest_api_sheets(path_excel: Path | str):
        try:
            api_book = pd.read_excel(str(path_excel), sheet_name=None, dtype=str, engine="openpyxl")
        except (FileNotFoundError, OSError, ValueError, BadZipFile):
            warn_ui(f"Impossible de lire les onglets API dans {path_excel}.")
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
                num_api = _normalize_flight_number(num_raw)

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
                except (TypeError, ValueError):
                    cap = None

                full_route = routing_full
                origin_iata = full_route[0]
                route_pos_map: Dict[str, int] = {}
                for idx, code in enumerate(full_route[1:], start=1):
                    normalized_code = str(code or "").strip().upper()
                    if normalized_code and normalized_code not in route_pos_map:
                        route_pos_map[normalized_code] = idx
                destinations = _destinations_from_routing(full_route)
                for dest_key in destinations:
                    route_pos = route_pos_map.get(dest_key, 1)
                    cap_for_dest = iata_to_capacity.get(dest_key)
                    max_colis = cap_for_dest if cap_for_dest is not None else cap
                    flight_id = f"{num_api}_{d}_{dest_key}"
                    vols_dict[flight_id] = {
                        "flight_number": str(num_api).zfill(4),
                        "date": d,
                        "departure_time": t,
                        "routing": [origin_iata, dest_key],
                        "routing_full": full_route,
                        "dest_iata": dest_key,
                        "route_pos": route_pos,
                        "max_colis_base": max_colis,
                        "source": "api",
                    }

    # Ingestion des feuilles API du source
    vols_src_path = vols_path or VOLS_SRC
    _ingest_api_sheets(vols_src_path)
    # Fallback : si aucun vol retenu après le sheet principal, on lit aussi les feuilles API de la copie TMP
    if not vols_dict:
        _ingest_api_sheets(vols_path or cp.VOLS)

    logger.info("Vols retenus: %s", len(vols_dict))

    if vols_dict:
        logger.debug("DEBUG VOLS NORMALISES (apercu)")
        for i, v in enumerate(list(vols_dict.values())[:10]):
            logger.debug(
                "Vol %s | Date=%s | Heure=%s | Routing=%s | Max=%s",
                v["flight_number"],
                v["date"],
                v["departure_time"],
                v["routing"],
                v["max_colis_base"],
            )
        logger.debug("Fin debug vols normalises")
    else:
        logger.warning("Aucun vol apres normalisation.")

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
        routing_full = v.get("routing_full", routing)
        dest_iata = str(v.get("dest_iata", "")).strip().upper()
        if not dest_iata and len(routing) > 1:
            dest_iata = str(routing[1]).strip().upper()
        if not dest_iata and len(routing_full) > 1:
            dest_iata = str(routing_full[1]).strip().upper()
        if not dest_iata:
            continue

        origin_iata = ""
        if routing:
            origin_iata = str(routing[0]).strip().upper()
        elif routing_full:
            origin_iata = str(routing_full[0]).strip().upper()
        if not origin_iata:
            origin_iata = "CDG"
        routing_use = [origin_iata, dest_iata]

        dest_city = iata_to_city.get(dest_iata, dest_iata)
        raw_num = str(v.get("flight_number", "")).strip()
        num_formatted = raw_num
        try:
            num_formatted = str(int(raw_num))  # retire les zéros superflus
        except (TypeError, ValueError):
            pass
        rows.append({
            "Date_Vol": v.get("date"),
            "Heure_Vol": v.get("departure_time"),
            "Numero_Vol": f"AF {num_formatted}",
            "Destination": dest_city,
            "IATA": dest_iata,
            "Routing": "-".join(routing_use),
            "Route_Pos": pd.to_numeric(v.get("route_pos", 1), errors="coerce"),
            "Max_Colis": v.get("max_colis_base"),
            "Source": v.get("source", "excel"),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df["Max_Colis"] = pd.to_numeric(df["Max_Colis"], errors="coerce").astype("Int64")
        df["Route_Pos"] = pd.to_numeric(df["Route_Pos"], errors="coerce").fillna(1).astype(int)
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
    def _get_vols_df_cached(vols_path: str, vols_mtime: float, tdb_path: str, tdb_mtime: float) -> pd.DataFrame:
        return load_vols_df(vols_path=Path(vols_path))

    def get_vols_df_cached(vols_path: Path | None = None, tdb_path: Path | None = None) -> pd.DataFrame:
        vpath = vols_path or VOLS
        tpath = tdb_path or TABLEAU_DE_BORD
        return _get_vols_df_cached(str(vpath), file_mtime(vpath), str(tpath), file_mtime(tpath))

except ImportError:
    def get_vols_df_cached(vols_path: Path | None = None, tdb_path: Path | None = None) -> pd.DataFrame:
        return load_vols_df(vols_path=vols_path)


def clear_vols_cache() -> None:
    cached = globals().get("_get_vols_df_cached") or globals().get("get_vols_df_cached")
    if cached is not None and hasattr(cached, "clear"):
        try:
            cached.clear()
        except (AttributeError, RuntimeError):
            pass
