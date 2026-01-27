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

def _get_api_key() -> str | None:
    """
    Récupère la clé API depuis les secrets Streamlit ou les variables d'env.
    """
    # Charge automatiquement .env si présent (pour usage local)
    try:
        load_dotenv()
    except Exception:
        pass

    if st and hasattr(st, "secrets"):
        try:
            val = st.secrets.get("AF_API_KEY")
            if val:
                return str(val)
        except Exception:
            pass
    return os.getenv("AF_API_KEY")


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

def fetch_flights(dest: str, start_date: str, end_date: str, origin: str = "CDG", airline: str = "AF") -> Dict[str, Any]:
    """
    Appelle l'endpoint flightstatus pour une destination et une fenêtre de dates.
    """
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("AF_API_KEY manquant (secret Streamlit ou variable d'environnement).")

    dest = (dest or "").strip().upper()
    origin = (origin or "").strip().upper()
    airline = (airline or "").strip().upper()
    if len(dest) != 3:
        raise RuntimeError(f"Destination IATA invalide : '{dest}'")

    url = (
        "https://api.airfranceklm.com/opendata/flightstatus"
        f"?startRange={start_date}T00:00:01Z"
        f"&endRange={end_date}T23:59:59Z"
        f"&origin={origin}"
        f"&destination={dest}"
        f"&operatingAirlineCode={airline}"
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
    - Sélectionne l'heure de départ depuis l'origine (CDG de préférence).
    """
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
        sched = None
        if leg_from_origin:
            sched = leg_from_origin.get("departureInformation", {}).get("times", {}).get("scheduled", "")
        # Fallback : horaire le plus tôt parmi les legs disponibles
        if not sched:
            candidates = []
            for lg in legs:
                t = lg.get("departureInformation", {}).get("times", {}).get("scheduled", "")
                if t:
                    candidates.append(t)
            if candidates:
                sched = min(candidates)
        d_str, h_str = _parse_iso(sched)
        flights.append(
            FlightRoute(
                origine=origine,
                destination=destination,
                route=route_str,
                numero_vol=num_vol,
                horaire_iso=sched,
                date_depart=d_str,
                heure_depart=h_str,
            )
        )
    return flights


def fetch_multiple(dest_codes: List[str], start_date: str, end_date: str, origin: str = "CDG", airline: str = "AF", throttle_sec: float = 1.05) -> List[FlightRoute]:
    """
    Appelle l'API pour chaque destination (1 appel/s minimum).
    Retourne la liste cumulée des routes.
    """
    out: List[FlightRoute] = []
    for i, code in enumerate(dest_codes):
        data = fetch_flights(code, start_date, end_date, origin=origin, airline=airline)
        out.extend(extract_routes(data))
        if i < len(dest_codes) - 1:
            time.sleep(throttle_sec)
    return out
