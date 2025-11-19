import csv
from datetime import date, timedelta
import yaml
from af_client import AFClient, offers_to_vols_rows

def daterange(d0, d1):
    cur = d0
    while cur <= d1:
        yield cur
        cur += timedelta(days=1)

def main(config_yaml, paramdest_csv, out_csv):
    cfg = yaml.safe_load(open(config_yaml, "r"))
    weekstart = cfg.get("weekstart")  # "10/11/2025"
    weekfin   = cfg.get("weekfin")    # "16/11/2025"
    d0 = date.fromisoformat("-".join(reversed(weekstart.split("/"))))
    d1 = date.fromisoformat("-".join(reversed(weekfin.split("/"))))

    # Destinations à tester (lis ParamDest.csv si tu veux filtrer par jour OK)
    dests = []
    with open(paramdest_csv, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for r in reader:
            dests.append(r["Destination"].strip().upper())

    client = AFClient()
    rows_all = []

    for d in daterange(d0, d1):
        # Exemple: on ne prend que CDG -> DEST (à adapter si tu veux ORY, AMS, etc.)
        for dest in dests:
            offers = client.search_offers("CDG", dest, d.isoformat())
            rows = offers_to_vols_rows(offers)
            rows_all.extend(rows)

    # écriture Vols.csv
    fieldnames = ["PVOL_DATE", "PVOL_HEURE", "PVOL_NUMERO", "PVOL_ROUTE_API"]
    with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        w.writeheader()
        for r in rows_all:
            w.writerow(r)

if __name__ == "__main__":
    BASE = "/Users/EdouardGonnu/asf_scheduler"
    main(
        config_yaml=f"{BASE}/config.yaml",
        paramdest_csv=f"{BASE}/data/ParamDest.csv",
        out_csv=f"{BASE}/data/Vols.csv"
    )
