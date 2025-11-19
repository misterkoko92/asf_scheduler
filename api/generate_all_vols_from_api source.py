#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generate_all_vols_from_api.py
Version hybride — essaie d’abord l’API publique Air France (flightstatus/v4/flights),
puis bascule sur l’API interne /flights/all si la première échoue.
"""

import os
import time
import yaml
import json
import requests
import pandas as pd
from datetime import datetime, timedelta

# === CONFIG ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
BE_CSV = os.path.join(DATA_DIR, "BE.csv")
OUTPUT_CSV = os.path.join(DATA_DIR, "Vols_API.csv")
CONFIG_YAML = os.path.join(BASE_DIR, "config.yaml")

API_KEY = "7krxvvkty8jn3dcgzuar7wck"
PUBLIC_URL = "https://api.airfranceklm.com/opendata/flightstatus/v4/flights"
INTERNAL_URL = "https://api.airfranceklm.com/flights/all"  # Fallback si l’API publique échoue


# === Lecture des destinations utiles ===
def read_destinations_from_BE(be_csv):
    df = pd.read_csv(be_csv, dtype=str, sep=";")
    df.columns = df.columns.str.strip().str.upper()
    if "BE_STATUT" not in df.columns or "BE_FK_DESTINATION" not in df.columns:
        raise ValueError(f"❌ Colonnes manquantes dans BE.csv : {list(df.columns)}")

    df = df[df["BE_STATUT"].str.upper() == "D"]
    dests = sorted(df["BE_FK_DESTINATION"].dropna().unique())
    print(f"\n🎯 Destinations suivies : {', '.join(dests) if dests else 'Aucune'}")
    return dests


# === Lecture des dates depuis config.yaml ===
def read_config_dates(config_yaml):
    with open(config_yaml, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    try:
        weekstart = datetime.strptime(config["weekstart"], "%Y-%m-%d").date()
        weekfin = datetime.strptime(config["weekfin"], "%Y-%m-%d").date()
    except Exception:
        print("⚠️ Format de date inattendu dans config.yaml, tentative d'autodétection...")
        weekstart = datetime.strptime(config["weekstart"], "%d/%m/%Y").date()
        weekfin = datetime.strptime(config["weekfin"], "%d/%m/%Y").date()
    return weekstart, weekfin


# === Appel API publique ===
def fetch_day_public(date_str, dests_utiles):
    """Appel API publique Air France"""
    headers = {
        "API-Key": API_KEY,
        "Accept": "application/json"
    }
    params = {
        "origin": "CDG",
        "movementType": "D",
        "operatingAirlineCode": "AF",
        "timeOriginType": "S",
        "timeType": "L",
        "startDate": date_str,
        "endDate": date_str
    }

    print(f"\n📆 Jour : {date_str}")
    try:
        r = requests.get(PUBLIC_URL, headers=headers, params=params, timeout=20)
        if r.status_code in (403, 404):
            print(f"    ⚠️ API publique inaccessible ({r.status_code}), bascule vers API interne…")
            return None  # signaler fallback
        if r.status_code != 200:
            print(f"    ⚠️ Erreur API publique : {r.status_code} {r.text[:180]}")
            return []

        data = r.json()
        flights = data.get("operationalFlights", [])
        print(f"    → API publique a renvoyé {len(flights)} vols bruts")

        selected = []
        for f in flights:
            airline = f.get("airline", {}).get("code", "")
            if airline != "AF":
                continue
            route = f.get("route", [])
            if not route or route[0] != "CDG":
                continue
            matching_dests = [r for r in route if r in dests_utiles]
            if not matching_dests:
                continue

            flight_number = f.get("flightNumber")
            sched_date = f.get("flightScheduleDate")
            legs = f.get("flightLegs", [])
            dep_time = None
            if legs:
                dep_time = (
                    legs[0]
                    .get("departureInformation", {})
                    .get("times", {})
                    .get("scheduled")
                )

            for dest_in_route in matching_dests:
                selected.append({
                    "Date": sched_date,
                    "Numéro de vol": f"AF{flight_number}",
                    "Origine": route[0],
                    "Destination": dest_in_route,
                    "Heure départ": dep_time,
                    "Route": " - ".join(route)
                })

        print(f"    → {len(selected)} vols CDG→Dest enregistrés ce jour (API publique).")
        return selected

    except Exception as e:
        print(f"    ⚠️ Erreur de connexion (API publique) : {e}")
        return []


# === Appel API interne ===
def fetch_day_internal(date_str, dests_utiles):
    """Appel API interne /flights/all"""
    headers = {
        "API-Key": API_KEY,
        "Accept": "application/json"
    }
    try:
        r = requests.get(INTERNAL_URL, headers=headers, timeout=20)
        if r.status_code != 200:
            print(f"    ⚠️ Erreur API interne : {r.status_code} {r.text[:180]}")
            return []

        data = r.json()
        flights = data.get("data", [])
        print(f"    → API interne a renvoyé {len(flights)} vols bruts")

        selected = []
        for f in flights:
            route = f.get("route", [])
            if not route or route[0] != "CDG":
                continue
            dests_in_route = [r for r in route if r in dests_utiles]
            if not dests_in_route:
                continue

            selected.append({
                "Date": f.get("datevol"),
                "Numéro de vol": f.get("code"),
                "Origine": route[0],
                "Destination": dests_in_route[0],
                "Route": " - ".join(route)
            })

        print(f"    → {len(selected)} vols CDG→Dest enregistrés ce jour (API interne).")
        return selected

    except Exception as e:
        print(f"    ⚠️ Erreur de connexion (API interne) : {e}")
        return []


# === MAIN ===
def main():
    print("🕐 Pause initiale 2s pour respecter le quota d’appel (1/s)...")
    time.sleep(2)

    dests_utiles = read_destinations_from_BE(BE_CSV)
    weekstart, weekfin = read_config_dates(CONFIG_YAML)

    all_flights = []
    current = weekstart

    while current <= weekfin:
        date_str = current.strftime("%Y-%m-%d")
        flights = fetch_day_public(date_str, dests_utiles)
        if flights is None:
            flights = fetch_day_internal(date_str, dests_utiles)
        all_flights.extend(flights)
        time.sleep(1.2)
        current += timedelta(days=1)

    # Export CSV
    if not all_flights:
        print("⚠️ Aucun vol récupéré.")
        return

    df = pd.DataFrame(all_flights)
    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"\n✅ Vols exportés → {OUTPUT_CSV}")
    print(f"📊 Total : {len(df)} vols enregistrés (CDG uniquement)")


if __name__ == "__main__":
    main()
