# -*- coding: utf-8 -*-

from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from utils.datetime_utils import (
    coerce_datetime,
    format_date_value,
    hour_min_value,
    parse_date_series,
)
from utils.identifiers import format_vol_display


def _time_to_minutes(val: object) -> int | None:
    return hour_min_value(
        val,
        allow_general_fallback=True,
        strip_spaces=True,
        lowercase=True,
    )


def _minutes_to_hhmm(m: int | None) -> str:
    if m is None:
        return ""
    h = int(m // 60)
    mi = int(m % 60)
    return f"{h:02d}h{mi:02d}"


def _compute_week_dates(
    *,
    api_start_date: object | None,
    week: int | None,
    df_benev: pd.DataFrame | None,
    df_flights: pd.DataFrame | None,
    today: pd.Timestamp | None = None,
) -> list[datetime]:
    if today is None:
        today = pd.Timestamp.today()

    if api_start_date:
        ref = coerce_datetime(api_start_date, errors="coerce")
    else:
        ref = None
        for df in (df_benev, df_flights):
            if df is None or df.empty:
                continue
            if "Date" not in df.columns:
                continue
            ser = parse_date_series(df["Date"])
            if not ser.dropna().empty:
                ref = ser.dropna().iloc[0]
                break

    if ref is None or pd.isna(ref):
        if week:
            try:
                today_iso = today.isocalendar()
                monday = datetime.fromisocalendar(int(today_iso.year), int(week), 1)
                return [monday + pd.Timedelta(days=i) for i in range(7)]
            except (TypeError, ValueError, OverflowError):
                pass
        ref = today

    iso = ref.isocalendar()
    monday = datetime.fromisocalendar(int(iso.year), int(iso.week), 1)
    return [monday + pd.Timedelta(days=i) for i in range(7)]


def _build_day_labels(week_dates: list[datetime]) -> list[str]:
    day_names = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    return [
        f"{day_names[i]} {format_date_value(d, fmt='%d/%m', default='')}"
        for i, d in enumerate(week_dates)
    ]


def _build_benev_week_table(
    df_benev: pd.DataFrame | None,
    *,
    week_dates: list[datetime],
    day_labels: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if df_benev is None or df_benev.empty:
        return pd.DataFrame(), pd.DataFrame()

    df_b = df_benev.copy()
    df_b["Date_dt"] = parse_date_series(df_b["Date"]).dt.date

    avail: dict[tuple[str, date], tuple[int, int]] = {}
    for _, row in df_b.iterrows():
        name = str(row.get("Nom", "")).strip()
        d = row.get("Date_dt")
        if not name or pd.isna(d):
            continue
        arr = _time_to_minutes(row.get("Arrivée", ""))
        dep = _time_to_minutes(row.get("Départ", ""))
        if arr is None or dep is None:
            continue
        key = (name, d)
        if key in avail:
            prev_arr, prev_dep = avail[key]
            arr = min(arr, prev_arr)
            dep = max(dep, prev_dep)
        avail[key] = (arr, dep)

    names = sorted(
        {
            str(n).strip()
            for n in df_b.get("Nom", pd.Series(dtype=object)).tolist()
            if str(n).strip()
        }
    )
    if not names:
        return pd.DataFrame(), pd.DataFrame()

    name_days: dict[str, set[date]] = {}
    for n, d in avail.keys():
        if not n:
            continue
        name_days.setdefault(n, set()).add(d)
    name_counts = {n: len(days) for n, days in name_days.items()}
    name_display = {n: f"{n} ({name_counts.get(n, 0)})" for n in names}

    cols = pd.MultiIndex.from_product([day_labels, ["Début", "Fin"]])
    table = pd.DataFrame("", index=[name_display[n] for n in names], columns=cols)
    table.index.name = "Bénévole"
    mask = pd.DataFrame(False, index=[name_display[n] for n in names], columns=cols)

    for name in names:
        for d, label in zip(week_dates, day_labels):
            key = (name, d.date())
            if key not in avail:
                continue
            arr, dep = avail[key]
            row_name = name_display.get(name, name)
            table.loc[row_name, (label, "Début")] = _minutes_to_hhmm(arr)
            table.loc[row_name, (label, "Fin")] = _minutes_to_hhmm(dep)
            mask.loc[row_name, (label, "Début")] = True
            mask.loc[row_name, (label, "Fin")] = True
    return table, mask


def _build_benev_ranges_by_date(df_benev: pd.DataFrame | None) -> dict[date, list[tuple[int, int]]]:
    benev_by_date: dict[date, list[tuple[int, int]]] = {}
    if df_benev is None or df_benev.empty:
        return benev_by_date

    tmp_b = df_benev.copy()
    tmp_b["Date_dt"] = parse_date_series(tmp_b["Date"]).dt.date
    for _, row in tmp_b.iterrows():
        d = row.get("Date_dt")
        if pd.isna(d):
            continue
        arr = _time_to_minutes(row.get("Arrivée", ""))
        dep = _time_to_minutes(row.get("Départ", ""))
        if arr is None or dep is None:
            continue
        benev_by_date.setdefault(d, []).append((arr, dep))
    return benev_by_date


def _build_flights_week_table(
    df_flights: pd.DataFrame | None,
    *,
    df_be: pd.DataFrame | None,
    week_dates: list[datetime],
    day_labels: list[str],
    benev_by_date: dict[date, list[tuple[int, int]]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if df_flights is None or df_flights.empty:
        return pd.DataFrame(), pd.DataFrame()

    def _is_compatible(d: date, minute_val: int | None) -> bool:
        if minute_val is None:
            return False
        for start, end in benev_by_date.get(d, []):
            if start <= minute_val <= end:
                return True
        return False

    def _vol_display(num: object) -> str:
        return format_vol_display(num) or str(num or "").strip()

    df_v = df_flights.copy()
    df_v["Date_dt"] = parse_date_series(df_v["Date"]).dt.date

    flights: dict[tuple[str, date], dict[str, bool]] = {}
    for _, row in df_v.iterrows():
        dest = str(row.get("Destination", "")).strip()
        d = row.get("Date_dt")
        if not dest or pd.isna(d):
            continue

        heure = str(row.get("Heure", "")).strip()
        hmin = _time_to_minutes(heure)
        routing_raw = str(row.get("Routing", "")).strip().upper()
        routing_parts = [p for p in routing_raw.replace(" ", "").split("-") if p and p != "CDG"]
        routing = "-".join(routing_parts)
        vol = _vol_display(row.get("Numero_Vol", ""))
        label_parts = [p for p in [heure, vol, routing] if p]
        label = " - ".join(label_parts)
        key = (dest, d)
        compatible = _is_compatible(d, hmin)
        labels_map = flights.setdefault(key, {})
        labels_map[label] = labels_map.get(label, False) or compatible

    dests = sorted(
        {
            str(d).strip()
            for d in df_v.get("Destination", pd.Series(dtype=object)).tolist()
            if str(d).strip()
        }
    )
    if not dests:
        return pd.DataFrame(), pd.DataFrame()

    colis_counts: dict[str, int] = {}
    if df_be is not None and not df_be.empty and "Destination" in df_be.columns:
        tmp_be = df_be.copy()
        tmp_be["Destination"] = tmp_be["Destination"].astype(str).str.strip()
        tmp_be["Nb_Colis"] = (
            pd.to_numeric(tmp_be.get("Nb_Colis", 0), errors="coerce").fillna(0).astype(int)
        )
        colis_counts = tmp_be.groupby("Destination")["Nb_Colis"].sum().astype(int).to_dict()

    dest_display = {d: f"{d} ({colis_counts.get(d, 0)})" for d in dests}
    table = pd.DataFrame("", index=[dest_display[d] for d in dests], columns=day_labels)
    table.index.name = "Escale"
    status = pd.DataFrame("none", index=[dest_display[d] for d in dests], columns=day_labels)

    for dest in dests:
        for d, label in zip(week_dates, day_labels):
            key = (dest, d.date())
            if key not in flights:
                continue
            row_dest = dest_display.get(dest, dest)
            items = list(flights[key].items())
            table.loc[row_dest, label] = "\n".join([lab for lab, _ in items])
            if any(ok for _, ok in items):
                status.loc[row_dest, label] = "compatible"
            else:
                status.loc[row_dest, label] = "incompatible"

    return table, status
