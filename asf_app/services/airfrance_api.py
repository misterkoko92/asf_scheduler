# asf_app/services/airfrance_api.py
# -*- coding: utf-8 -*-
"""
Client léger pour l'API Air France/KLM (endpoint flightstatus).
Pas de dépendance forte à l'UI : utilisable par un loader ou un script.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import requests

from utils.datetime_utils import parse_iso_datetime, format_date_value, format_time_value
try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional dependency for local .env loading
    def load_dotenv(*args: Any, **kwargs: Any) -> bool:
        return False

try:
    import streamlit as st
except Exception:  # pragma: no cover - streamlit peut être absent hors UI
    st = None


# ---------------------------------------------------------------------------
# Config & helpers
# ---------------------------------------------------------------------------

DEFAULT_AF_MAX_CALLS_PER_DAY = 100
DEFAULT_AF_MIN_DELAY_SECONDS = 1.1
DEFAULT_AF_TIME_ORIGIN_TYPE = "P"
ALLOWED_AF_TIME_ORIGIN_TYPES = {"S", "M", "I", "P"}


def _read_env_var_from_file(var_name: str, env_path: Path) -> str | None:
    """
    Lit une variable dans un fichier .env sans dépendre de python-dotenv.
    Accepte les lignes "KEY=value" et "export KEY=value".
    """
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return None

    for line in lines:
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        if raw.startswith("export "):
            raw = raw[len("export "):].strip()
        if "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        if key.strip() != var_name:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        return value
    return None


def _iter_env_candidate_paths() -> List[Path]:
    return [Path.cwd() / ".env", Path(__file__).resolve().parents[2] / ".env"]


def _get_config_value(var_name: str) -> str | None:
    """
    Récupère une variable depuis env shell/.env, puis Streamlit secrets.
    """
    # Charge automatiquement .env si présent (pour usage local)
    try:
        load_dotenv()
    except Exception:
        pass

    env_val = os.getenv(var_name)
    if env_val:
        return env_val

    # Fallback : lecture directe de .env si python-dotenv est absent.
    seen: set[Path] = set()
    for env_path in _iter_env_candidate_paths():
        try:
            norm = env_path.resolve()
        except Exception:
            norm = env_path
        if norm in seen:
            continue
        seen.add(norm)
        val = _read_env_var_from_file(var_name, env_path)
        if val:
            os.environ.setdefault(var_name, val)
            return val

    # Dernier fallback : secrets Streamlit (utile en déploiement cloud).
    if st and hasattr(st, "secrets"):
        try:
            val = st.secrets.get(var_name)
            if val:
                return str(val)
        except Exception:
            pass
    return None


def _get_api_key() -> str | None:
    """
    Récupère la clé API depuis les secrets Streamlit ou les variables d'env.
    """
    return _get_config_value("AF_API_KEY")


def _as_positive_int(raw: str | None, default: int) -> int:
    if raw is None:
        return default
    try:
        val = int(str(raw).strip())
        return val if val > 0 else default
    except Exception:
        return default


def _as_positive_float(raw: str | None, default: float) -> float:
    if raw is None:
        return default
    try:
        val = float(str(raw).strip())
        return val if val > 0 else default
    except Exception:
        return default


def get_api_limits() -> tuple[int, float]:
    """
    Retourne (max_calls_per_day, min_delay_seconds) depuis la config locale.
    """
    max_calls = _as_positive_int(
        _get_config_value("AF_MAX_CALLS_PER_DAY"),
        DEFAULT_AF_MAX_CALLS_PER_DAY,
    )
    min_delay = _as_positive_float(
        _get_config_value("AF_MIN_DELAY_SECONDS"),
        DEFAULT_AF_MIN_DELAY_SECONDS,
    )
    return max_calls, min_delay


def _normalize_time_origin_type(raw: str | None, *, default: str, strict: bool) -> str:
    val = (raw or default or DEFAULT_AF_TIME_ORIGIN_TYPE).strip().upper()
    if val in ALLOWED_AF_TIME_ORIGIN_TYPES:
        return val
    if strict:
        raise RuntimeError(
            f"timeOriginType invalide: '{val}' (attendu: S, M, I, P)"
        )
    return default if default in ALLOWED_AF_TIME_ORIGIN_TYPES else DEFAULT_AF_TIME_ORIGIN_TYPE


def get_default_time_origin_type() -> str:
    """
    Retourne le timeOriginType par défaut (AF_TIME_ORIGIN_TYPE), sinon P.
    """
    return _normalize_time_origin_type(
        _get_config_value("AF_TIME_ORIGIN_TYPE"),
        default=DEFAULT_AF_TIME_ORIGIN_TYPE,
        strict=False,
    )


def _parse_iso(dt_str: str) -> tuple[str, str]:
    """
    Convertit un datetime ISO en (date JJ/MM/AA, heure HHhMM).
    """
    dt_val = parse_iso_datetime(dt_str)
    if dt_val is None:
        return "", ""
    return (
        format_date_value(dt_val, fmt="%d/%m/%y", default=""),
        format_time_value(dt_val, fmt="%Hh%M", default=""),
    )


@dataclass
class FlightRoute:
    origine: str
    destination: str
    route: str
    numero_vol: str
    horaire_iso: str
    date_depart: str
    heure_depart: str

    def as_dict(self) -> Dict[str, str]:
        return {
            "Origine": self.origine,
            "Destination": self.destination,
            "Routing": self.route,
            "Numero_Vol": self.numero_vol,
            "Horaire_ISO": self.horaire_iso,
            "Date_depart": self.date_depart,
            "Heure_depart": self.heure_depart,
        }


# ---------------------------------------------------------------------------
# Appel API
# ---------------------------------------------------------------------------

def fetch_flights(
    dest: str,
    start_date: str,
    end_date: str,
    origin: str = "CDG",
    airline: str = "AF",
    time_origin_type: str | None = None,
) -> Dict[str, Any]:
    """
    Appelle l'endpoint flightstatus pour une destination et une fenêtre de dates.
    """
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("AF_API_KEY manquant (secret Streamlit ou variable d'environnement).")

    dest = (dest or "").strip().upper()
    origin = (origin or "").strip().upper()
    airline = (airline or "").strip().upper()
    time_origin_type = _normalize_time_origin_type(
        time_origin_type,
        default=get_default_time_origin_type(),
        strict=True,
    )
    if len(dest) != 3:
        raise RuntimeError(f"Destination IATA invalide : '{dest}'")

    url = (
        "https://api.airfranceklm.com/opendata/flightstatus"
        f"?startRange={start_date}T00:00:01Z"
        f"&endRange={end_date}T23:59:59Z"
        f"&origin={origin}"
        f"&destination={dest}"
        f"&operatingAirlineCode={airline}"
        f"&timeOriginType={time_origin_type}"
    )

    resp = requests.get(
        url,
        headers={
            "API-Key": api_key,
            "Accept": "application/hal+json",
            "User-Agent": "ASF-Scheduler/airfrance_api_client",
        },
        timeout=20,
    )

    if resp.status_code == 404:
        # Destination non desservie / aucune donnée -> on retourne vide pour ne pas bloquer la boucle
        return {"operationalFlights": []}

    if resp.status_code != 200:
        raise RuntimeError(
            f"HTTP {resp.status_code} sur {url}\n"
            f"Headers: {resp.headers}\n"
            f"Body: {resp.text[:800]}"
        )
    return resp.json()


def extract_routes(data: Dict[str, Any]) -> List[FlightRoute]:
    """
    Transforme le payload API en objets FlightRoute.
    - Supprime un éventuel retour final vers CDG.
    - Sélectionne l'heure de départ depuis l'origine (CDG de préférence),
      en privilégiant `latestPublished` (puis fallback).
    """
    def _pick_departure_time(leg: Dict[str, Any]) -> str:
        dep_info = leg.get("departureInformation", {}) if isinstance(leg, dict) else {}
        times = dep_info.get("times", {}) if isinstance(dep_info, dict) else {}
        if not isinstance(times, dict):
            return ""
        estimated = times.get("estimated", {})
        estimated_value = estimated.get("value") if isinstance(estimated, dict) else ""
        return (
            str(times.get("latestPublished") or "")
            or str(times.get("actual") or "")
            or str(estimated_value or "")
            or str(times.get("scheduled") or "")
        )

    flights: List[FlightRoute] = []
    for flight in data.get("operationalFlights", []):
        route_list = flight.get("route") or []
        if not route_list:
            continue
        cleaned_route = list(route_list)
        if cleaned_route and cleaned_route[-1] == "CDG":
            cleaned_route = cleaned_route[:-1]  # retire un retour éventuel
        route_str = "-".join(cleaned_route)
        origine = cleaned_route[0]
        destination = cleaned_route[-1]
        num_vol = f'{flight.get("airline", {}).get("code", "").upper()} {flight.get("flightNumber", "")}'
        legs = flight.get("flightLegs") or []
        leg_from_origin = next(
            (lg for lg in legs if lg.get("departureInformation", {}).get("departureStation") == origine),
            None,
        )
        dep_time = None
        if leg_from_origin:
            dep_time = _pick_departure_time(leg_from_origin)
        # Fallback : horaire le plus tôt parmi les legs disponibles
        if not dep_time:
            candidates = []
            for lg in legs:
                t = _pick_departure_time(lg)
                if t:
                    candidates.append(t)
            if candidates:
                dep_time = min(candidates)
        d_str, h_str = _parse_iso(dep_time)
        flights.append(
            FlightRoute(
                origine=origine,
                destination=destination,
                route=route_str,
                numero_vol=num_vol,
                horaire_iso=dep_time,
                date_depart=d_str,
                heure_depart=h_str,
            )
        )
    return flights


def fetch_multiple(
    dest_codes: List[str],
    start_date: str,
    end_date: str,
    origin: str = "CDG",
    airline: str = "AF",
    time_origin_type: str | None = None,
    throttle_sec: float | None = None,
    max_calls_per_day: int | None = None,
) -> List[FlightRoute]:
    """
    Appelle l'API pour chaque destination avec contrôle de quota et de tempo.
    Retourne la liste cumulée des routes.
    """
    cfg_max_calls, cfg_min_delay = get_api_limits()
    effective_max_calls = cfg_max_calls
    if max_calls_per_day is not None:
        effective_max_calls = min(_as_positive_int(str(max_calls_per_day), cfg_max_calls), cfg_max_calls)
    if len(dest_codes) > effective_max_calls:
        raise RuntimeError(
            f"Trop de destinations ({len(dest_codes)}) pour la limite AF_MAX_CALLS_PER_DAY={effective_max_calls}."
        )
    effective_time_origin_type = _normalize_time_origin_type(
        time_origin_type,
        default=get_default_time_origin_type(),
        strict=True,
    )

    if throttle_sec is None:
        effective_delay = cfg_min_delay
    else:
        effective_delay = max(_as_positive_float(str(throttle_sec), cfg_min_delay), cfg_min_delay)

    out: List[FlightRoute] = []
    for i, code in enumerate(dest_codes):
        data = fetch_flights(
            code,
            start_date,
            end_date,
            origin=origin,
            airline=airline,
            time_origin_type=effective_time_origin_type,
        )
        out.extend(extract_routes(data))
        if i < len(dest_codes) - 1:
            time.sleep(effective_delay)
    return out
