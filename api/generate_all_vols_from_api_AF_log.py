#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Récupération automatique des vols Air France via API officielle.
- Lecture des destinations (BE.csv) et période (config.yaml)
- ✅ Un seul appel API par jour (tous les vols CDG / Air France)
- ✅ Filtrage local sur les destinations utiles (BE.csv)
- ✅ Respect des quotas : 1 appel/s, 100 appels/jour
- 💾 Sauvegarde des réponses brutes JSON dans /logs_api/
- 📊 Export des vols Air France CDG→Destinations dans Vols_API.csv
"""

import os
import ssl
import http.client
import urllib.parse
import yaml
import pandas as pd
import json
import time
from datetime import datetime, timedelta

# === CONFIG ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOGS_DIR = os.path.join(BASE_DIR, "logs_api")
BE_CSV = os.path.join(DATA_DIR, "BE.csv")
OUTPUT_CSV = os.path.join(DATA_DIR, "Vols_API.csv")
CONFIG_YAML = os.path.join(BASE_DIR, "config.yaml")

HOST = "api.airfranceklm.com"
ENDPOINT = "/opendata/flightstatus"
API_KEY = os.getenv("AIRFRANCE_API_KEY", "YOUR_API_KEY")

# Limites API
MAX_CALLS_PER_DAY = 100
MIN_DELAY_BETWEEN_CALLS = 1.2  # secondes

# Crée le dossier logs_api si absent
os.makedirs(LOGS_DIR, exist_ok=True)


# === UTILS ===
def read_destinations_from_BE(be_csv):
    """Lit les destinations actives depuis BE.csv"""
    df = pd.read_csv(be_csv, dtype=str, sep=";")
    df.columns = df.columns.str.strip().str.upper()

    if "BE_STATUT" not in df.columns or "BE_FK_DESTINATION" not in df.columns:
        raise ValueError("❌ Colonnes manquantes dans BE.csv")

    df = df[df["BE_STATUT"].str.upper() == "D"]
    dests = sorted(df["BE_FK_DESTINATION"].dropna().unique())
    print(f"\n🎯 Destinations suivies : {', '.join(dests) if dests else 'Aucune'}")
    return dests


def read_config_dates(config_yaml):
    """Lit weekstart/weekfin depuis config.yaml"""
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


# === API CALL (1/jour) ===
def fetch_all_flights_for_day(date_iso, call_count):
    """Un seul appel API pour tous les vols AF au départ de CDG pour un jour donné."""
    if call_count >= MAX_CALLS_PER_DAY:
        print("🚫 Limite quotidienne atteinte — arrêt.")
        return [], call_count

    all_flights = []
    page_number = 0
    page_size = 100
    context = ssl._create_unverified_context()

    start = f"{date_iso}T00:00:00Z"
    end = f"{date_iso}T23:59:59Z"

    while True:
        params = {
            "startRange": start,
            "endRange": end,
            "departure": "CDG",
            "carrierCode": "AF",
            "movementType": "D",
            "pageNumber": page_number,
            "pageSize": page_size
        }

        query = urllib.parse.urlencode(params)
        url = f"{ENDPOINT}?{query}"

        print(f"→ Appel API ({call_count+1}/{MAX_CALLS_PER_DAY}) : https://{HOST}{url}")
        conn = http.client.HTTPSConnection(HOST, context=context)
        headers = {"API-Key": API_KEY, "Accept": "application/hal+json"}
        conn.request("GET", url, headers=headers)
        res = conn.getresponse()
        data = res.read().decode("utf-8")

        call_count += 1

        if res.status != 200:
            print(f"⚠️ Erreur API ({res.status}) : {data[:200]}")
            break

        response = json.loads(data)
        flights = response.get("operationalFlights", [])
        all_flights.extend(flights)
        print(f"   → {len(flights)} vols récupérés (page {page_number})")

        # Sauvegarde du JSON brut
        log_path = os.path.join(LOGS_DIR, f"{date_iso}_p{page_number}.json")
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(response, f, indent=2, ensure_ascii=False)
        print(f"💾 Log sauvegardé → {log_path}")

        if len(flights) < page_size:
            break

        page_number += 1
        if call_count >= MAX_CALLS_PER_DAY:
            print("🚫 Limite de 100 appels atteinte — arrêt pagination.")
            break

        print("⏸️ Pause 1s pour quota...")
        time.sleep(MIN_DELAY_BETWEEN_CALLS)

    return all_flights, call_count


# === MAIN ===
def main():
    print("🕐 Pause initiale 2s pour respecter le quota (1/s)...")
    time.sleep(2)

    dests_utiles = read_destinations_from_BE(BE_CSV)
    weekstart, weekfin = read_config_dates(CONFIG_YAML)

    all_records = []
    call_count = 0

    for single_date in (weekstart + timedelta(n) for n in range((weekfin - weekstart).days + 1)):
        date_iso = single_date.strftime("%Y-%m-%d")
        print(f"\n📆 Jour : {date_iso}")
        print(f"📡 Récupération de tous les vols Air France au départ de CDG ({date_iso})")

        flights, call_count = fetch_all_flights_for_day(date_iso, call_count)
        print(f"   → {len(flights)} vols bruts récupérés")

        count_dest = 0
        for f in flights:
            airline = f.get("airline", {}).get("name", "")
            num = f.get("flightNumber", "")
            sched_date = f.get("flightScheduleDate", "")
            route = f.get("route", [])
            legs = f.get("flightLegs", [])

            if not route or route[0] != "CDG" or route[-1] not in dests_utiles:
                continue

            dep_time = legs[0].get("departureInformation", {}).get("times", {}).get("scheduled", "") if legs else ""
            arr_time = legs[-1].get("arrivalInformation", {}).get("times", {}).get("scheduled", "") if legs else ""

            all_records.append({
                "Date": sched_date,
                "Compagnie": airline,
                "Vol": num,
                "Origine": route[0],
                "Destination": route[-1],
                "Route": " - ".join(route),
                "Départ prévu": dep_time,
                "Arrivée prévue": arr_time
            })
            count_dest += 1

        print(f"✅ {count_dest} vols CDG→Dest (ABJ/BZV/TNR) conservés.")
        print("⏸️ Pause 2s avant le jour suivant...\n")
        time.sleep(2)

        if call_count >= MAX_CALLS_PER_DAY:
            print("🚫 Limite journalière de 100 appels atteinte — arrêt anticipé.")
            break

    # === EXPORT CSV ===
    if not all_records:
        print("⚠️ Aucun vol filtré trouvé.")
        return

    df = pd.DataFrame(all_records)
    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"\n✅ Vols exportés → {OUTPUT_CSV}")
    print(f"📊 Total : {len(df)} vols enregistrés")
    print(f"📈 Appels API utilisés : {call_count}/{MAX_CALLS_PER_DAY}")


if __name__ == "__main__":
    main()
