"""
Petit script de test isolé pour l'API Air France/KLM (mode API-Key direct).
Il n'est pas relié au reste du projet.

Utilisation :
    # Un seul code IATA
    python test_api/airfrance_api_test.py --dest ABJ --start 2025-12-08 --end 2025-12-14

    # Tous les codes ParamDest du Tableau de Bord (1 appel/s)
    python test_api/airfrance_api_test.py --from-paramdest --start 2025-12-08 --end 2025-12-14
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime

import requests
import time
import pandas as pd

# Ajout du répertoire racine du projet au PYTHONPATH pour les imports loaders/scheduler
BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from loaders.universal_loader import load_and_normalize
from scheduler.config_paths import TABLEAU_DE_BORD, SHEET_PARAM_DEST
from scheduler.column_map import column_map_param_dest

API_KEY = "7krxvvkty8jn3dcgzuar7wck"


def fetch_flights(dest: str, start_date: str, end_date: str) -> Dict[str, Any]:
    """Appelle l'endpoint flightstatus pour une destination et une fenêtre de dates."""
    url = (
        "https://api.airfranceklm.com/opendata/flightstatus"
        f"?startRange={start_date}T00:00:01Z&endRange={end_date}T23:59:59Z"
        f"&origin=CDG&destination={dest}&operatingAirlineCode=AF"
    )
    # Respecter la limite 1 req/s si vous enchaînez les appels (à gérer à l'appelant)
    resp = requests.get(
        url,
        headers={
            "API-Key": API_KEY,
            "Accept": "application/hal+json",
            "User-Agent": "curl/8.7.1",
        },
        timeout=20,
    )
    if resp.status_code != 200:
        raise SystemExit(
            f"HTTP {resp.status_code} sur {url}\n"
            f"Headers: {resp.headers}\n"
            f"Body: {resp.text[:800]}"
        )
    return resp.json()


def _parse_dt(dt_str: str) -> tuple[str, str]:
    """Retourne (date_jj_mm_aa, heure_HHhMM) à partir d'un datetime ISO."""
    if not dt_str:
        return "", ""
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%y"), dt.strftime("%Hh%M")
    except Exception:
        return "", ""


def extract_routes(data: Dict[str, Any]) -> List[Dict[str, str]]:
    """Extrait route complète, numéro de vol et horaire programmé."""
    flights: List[Dict[str, str]] = []
    for flight in data.get("operationalFlights", []):
        route_list = flight.get("route") or []
        if not route_list:
            continue
        # Si plus de 3 codes, on ignore le dernier (retour) pour fixer la destination.
        cleaned_route = route_list[:-1] if len(route_list) > 3 else route_list
        route = "-".join(cleaned_route)
        origin = cleaned_route[0]
        destination = cleaned_route[-1]
        num_vol = f'{flight["airline"]["code"]} {flight["flightNumber"]}'
        leg = (flight.get("flightLegs") or [{}])[0]
        sched = leg.get("departureInformation", {}).get("times", {}).get("scheduled", "")
        d_str, h_str = _parse_dt(sched)
        flights.append(
            {
                "Origine": origin,
                "Destination": destination,
                "route": route,
                "num_vol": num_vol,
                "horaire": sched,
                "Date_depart": d_str,
                "Heure_depart": h_str,
            }
        )
    return flights


def main():
    parser = argparse.ArgumentParser(description="Test API Air France/KLM flightstatus (API-Key)")
    parser.add_argument("--dest", help="Destination (IATA ou nom)")
    parser.add_argument("--from-paramdest", action="store_true", help="Tester tous les codes IATA issus de ParamDest du Tableau de Bord")
    parser.add_argument("--start", default="2025-12-08", help="Date début (YYYY-MM-DD)")
    parser.add_argument("--end", default="2025-12-14", help="Date fin (YYYY-MM-DD)")
    parser.add_argument("--out", default="test_api/export_vols.xlsx", help="Chemin du fichier Excel d'export")
    args = parser.parse_args()

    all_rows: List[Dict[str, str]] = []

    if args.from_paramdest:
        df_paramdest = load_and_normalize(TABLEAU_DE_BORD, SHEET_PARAM_DEST, column_map_param_dest, header=0)
        codes = sorted(set(df_paramdest["Dest_IATA"].dropna().astype(str).str.upper()))
        print(f"Codes ParamDest détectés ({len(codes)}): {codes}")
        for code in codes:
            print(f"\n=== {code} ===")
            try:
                data = fetch_flights(code, args.start, args.end)
                routes = extract_routes(data)
                all_rows.extend(routes)
                print(f"Vols trouvés : {len(routes)}")
                for r in routes[:10]:
                    print(r)
            except SystemExit as e:
                print(f"Erreur pour {code}: {e}")
            time.sleep(1.1)  # respecter la limite 1 requête/s
    else:
        if not args.dest:
            raise SystemExit("Spécifie --dest ou --from-paramdest")
        data = fetch_flights(args.dest, args.start, args.end)
        routes = extract_routes(data)
        all_rows.extend(routes)

        print(f"Destination: {args.dest}")
        print(f"Vols trouvés : {len(routes)}")
        for r in routes[:20]:  # aperçu
            print(r)

    if all_rows:
        df = pd.DataFrame(all_rows)
        cols = [
            "Origine",
            "Destination",
            "route",
            "num_vol",
            "Date_depart",
            "Heure_depart",
        ]
        df = df[cols]
        out_path = args.out
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        df.to_excel(out_path, index=False)
        print(f"\nExport Excel enregistré : {out_path}")


if __name__ == "__main__":
    main()
