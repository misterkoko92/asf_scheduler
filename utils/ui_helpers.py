from utils.identifiers import format_vol_display, normalize_be_number


def build_iata_city_maps(df_paramdest):
    """
    Construit deux dictionnaires :
    - iata -> ville
    - ville uppercase -> iata
    Retourne (dest_city_map, city_to_iata_map).
    """
    dest_city_map = {}
    if df_paramdest is not None and not getattr(df_paramdest, "empty", True):
        for _, r in df_paramdest.iterrows():
            iata = str(r.get("Dest_IATA", "")).strip().upper()
            ville = str(r.get("Dest_Ville", "") or r.get("Destination", "")).strip()
            if iata:
                dest_city_map[iata] = ville or iata
    city_to_iata_map = {v.upper(): k for k, v in dest_city_map.items()}
    return dest_city_map, city_to_iata_map


def format_be_label(dest: str, be_num: str, nb_colis: str | int, be_type: str, status: str, date_str: str | None = "") -> str:
    """
    Formattage standard d'un BE pour les listes déroulantes.
    """
    dest_up = (dest or "").upper()
    be_key = normalize_be_number(be_num)
    be_display = be_key or str(be_num)
    nb_txt = f"{nb_colis} colis" if nb_colis not in ("", None) else "Nb ?"
    type_txt = (be_type or "").upper()
    date_txt = date_str or "A planifier"
    return f"{dest_up} - BE {be_display} - {nb_txt} - {type_txt} - {date_txt} ({status})"


def format_vol_label(date_dt, iata: str, vol_num: str, heure_str: str, routing: str, status: str) -> str:
    """
    Formattage standard d'un vol pour les listes déroulantes.
    """
    jour = ""
    try:
        if hasattr(date_dt, "strftime"):
            jours_fr = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
            jour = jours_fr[date_dt.weekday()]
    except Exception:
        pass
    date_txt = f"{jour} {date_dt.strftime('%d/%m/%y')}" if getattr(date_dt, "strftime", None) else str(date_dt)
    routing_txt = routing or ""
    vol_display = format_vol_display(vol_num) or str(vol_num)
    return f"{date_txt} — {iata or ''} — {vol_display} — {heure_str} — {routing_txt} — {status}"


def sort_planning_df(df, date_col="Date_Vol", time_col="Heure_Vol", be_col="BE_Numero"):
    """
    Tri cohérent : date puis heure puis numéro BE.
    """
    from utils.datetime_utils import parse_date_series, parse_time_series
    if df is None or getattr(df, "empty", True):
        return df
    df = df.copy()
    df["_date_sort"] = parse_date_series(df.get(date_col, ""))
    df["_time_sort"] = parse_time_series(df.get(time_col, ""))
    df = df.sort_values(["_date_sort", "_time_sort", be_col], kind="stable")
    return df.drop(columns=["_date_sort", "_time_sort"], errors="ignore")
