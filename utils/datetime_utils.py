import datetime as dt
import warnings
import pandas as pd

JOURS_FR_LONG = [
    "Lundi",
    "Mardi",
    "Mercredi",
    "Jeudi",
    "Vendredi",
    "Samedi",
    "Dimanche",
]

MOIS_FR_LONG = [
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
]


_PANDAS_DAYFIRST_ISO_WARNING = (
    r"Parsing dates in %Y-%m-%d format when dayfirst=True was specified\."
)


def _to_datetime_safely(
    value: object,
    *,
    errors: str,
    dayfirst: bool = False,
    fmt: str | None = None,
):
    """
    Wrapper pd.to_datetime avec filtrage ciblé d'un warning pandas connu
    (ISO + dayfirst=True), sans modifier le résultat de parsing.
    """
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=_PANDAS_DAYFIRST_ISO_WARNING,
            category=UserWarning,
        )
        return pd.to_datetime(value, errors=errors, dayfirst=dayfirst, format=fmt)


def parse_date_series(
    series: pd.Series,
    fmt: str = "%d/%m/%y",
    *,
    allow_dayfirst_false: bool = True,
) -> pd.Series:
    """
    Parse une série de dates en privilégiant le format fourni, avec fallback dayfirst.
    Retourne une Series datetime64[ns] (NaT si invalide).
    """
    ser = _to_datetime_safely(series, fmt=fmt, errors="coerce")
    mask = ser.isna()
    if mask.any():
        ser.loc[mask] = _to_datetime_safely(
            series.loc[mask],
            errors="coerce",
            dayfirst=True,
        )
        mask = ser.isna()
        if allow_dayfirst_false and mask.any():
            ser.loc[mask] = _to_datetime_safely(
                series.loc[mask],
                errors="coerce",
                dayfirst=False,
            )
    return ser


def parse_time_series(
    series: pd.Series,
    *,
    allow_hour_only: bool = False,
    allow_general_fallback: bool = False,
    strip_spaces: bool = False,
    lowercase: bool = False,
) -> pd.Series:
    """
    Parse une série d'heures (peut contenir '10h00' ou '10:00').
    Retourne une Series datetime64[ns] (NaT si invalide).
    """
    s_clean = series.astype(str).str.strip()
    if lowercase:
        s_clean = s_clean.str.lower()
    s_clean = s_clean.str.replace("h", ":", regex=False)
    if strip_spaces:
        s_clean = s_clean.str.replace(" ", "", regex=False)
    if allow_hour_only:
        hour_only = s_clean.str.fullmatch(r"\d{2}")
        if hour_only.any():
            s_clean.loc[hour_only] = s_clean.loc[hour_only] + ":00"
    ser = pd.to_datetime(s_clean, format="%H:%M", errors="coerce")
    mask = ser.isna()
    if mask.any():
        ser.loc[mask] = pd.to_datetime(s_clean.loc[mask], format="%H:%M:%S", errors="coerce")
        if allow_general_fallback:
            mask = ser.isna()
            if mask.any():
                ser.loc[mask] = pd.to_datetime(s_clean.loc[mask], errors="coerce")
    # Support des heures Excel en format numérique (fraction de journée)
    num = pd.to_numeric(series, errors="coerce")
    num_mask = ser.isna() & num.notna()
    if num_mask.any():
        seconds = (num[num_mask] * 86400).round().astype("Int64")
        ser.loc[num_mask] = pd.to_datetime(seconds, unit="s", errors="coerce")
    return ser


def parse_date_value(
    value: object,
    fmt: str = "%d/%m/%y",
    *,
    allow_dayfirst_false: bool = True,
) -> pd.Timestamp:
    """Parse une valeur unique en date via parse_date_series."""
    return parse_date_series(
        pd.Series([value]),
        fmt=fmt,
        allow_dayfirst_false=allow_dayfirst_false,
    ).iloc[0]


def parse_time_value(
    value: object,
    *,
    allow_hour_only: bool = False,
    allow_general_fallback: bool = False,
    strip_spaces: bool = False,
    lowercase: bool = False,
) -> pd.Timestamp:
    """Parse une valeur unique en heure via parse_time_series."""
    return parse_time_series(
        pd.Series([value]),
        allow_hour_only=allow_hour_only,
        allow_general_fallback=allow_general_fallback,
        strip_spaces=strip_spaces,
        lowercase=lowercase,
    ).iloc[0]


def coerce_datetime(
    value: object,
    *,
    errors: str = "coerce",
    dayfirst: bool = False,
    fmt: str | None = None,
    format: str | None = None,
) -> pd.Timestamp | pd.Series | pd.DatetimeIndex:
    """Wrapper centralisé de pd.to_datetime (séries ou valeurs uniques)."""
    if fmt is None and format is not None:
        fmt = format
    return _to_datetime_safely(value, errors=errors, dayfirst=dayfirst, fmt=fmt)


def parse_iso_datetime(value: object) -> dt.datetime | None:
    """
    Parse une valeur ISO (ou proche) en datetime.
    Retourne None si invalide.
    """
    if value in (None, ""):
        return None
    if isinstance(value, dt.datetime):
        return value
    if isinstance(value, dt.date):
        return dt.datetime.combine(value, dt.time())
    try:
        sval = str(value).strip()
    except Exception:
        return None
    if not sval:
        return None
    if sval.endswith("Z"):
        sval = f"{sval[:-1]}+00:00"
    try:
        return dt.datetime.fromisoformat(sval)
    except Exception:
        return None


def parse_iso_date_value(value: object) -> dt.date | None:
    """
    Parse une valeur ISO (date ou datetime) en date.
    Retourne None si invalide.
    """
    dt_val = parse_iso_datetime(value)
    if dt_val is None:
        return None
    return dt_val.date()


def format_date_series(
    series: pd.Series,
    fmt: str = "%d/%m/%y",
    *,
    dayfirst: bool = True,
    allow_dayfirst_false: bool = True,
) -> pd.Series:
    parsed = parse_date_series(series, fmt=fmt, allow_dayfirst_false=allow_dayfirst_false)
    return parsed.dt.strftime(fmt)


def format_time_series(
    series: pd.Series,
    fmt: str = "%Hh%M",
    *,
    allow_hour_only: bool = False,
    allow_general_fallback: bool = False,
    strip_spaces: bool = False,
    lowercase: bool = False,
) -> pd.Series:
    parsed = parse_time_series(
        series,
        allow_hour_only=allow_hour_only,
        allow_general_fallback=allow_general_fallback,
        strip_spaces=strip_spaces,
        lowercase=lowercase,
    )
    return parsed.dt.strftime(fmt)


def format_date_value(
    value: object,
    fmt: str = "%d/%m/%y",
    *,
    dayfirst: bool = True,
    allow_dayfirst_false: bool = True,
    default: str | None = "",
) -> str:
    if isinstance(value, (dt.date, dt.datetime, pd.Timestamp)):
        try:
            return value.strftime(fmt)
        except Exception:
            return default if default is not None else str(value)
    dt_val = parse_date_value(value, fmt=fmt, allow_dayfirst_false=allow_dayfirst_false)
    if pd.isna(dt_val):
        return default if default is not None else str(value)
    try:
        return dt_val.strftime(fmt)
    except Exception:
        return default if default is not None else str(value)


def format_time_value(
    value: object,
    fmt: str = "%Hh%M",
    *,
    allow_hour_only: bool = False,
    allow_general_fallback: bool = False,
    strip_spaces: bool = False,
    lowercase: bool = False,
    default: str | None = "",
) -> str:
    if isinstance(value, (dt.time, dt.datetime, pd.Timestamp)):
        try:
            return value.strftime(fmt)
        except Exception:
            return default if default is not None else str(value)
    t_val = parse_time_value(
        value,
        allow_hour_only=allow_hour_only,
        allow_general_fallback=allow_general_fallback,
        strip_spaces=strip_spaces,
        lowercase=lowercase,
    )
    if pd.isna(t_val):
        return default if default is not None else str(value)
    try:
        return t_val.strftime(fmt)
    except Exception:
        return default if default is not None else str(value)


def format_date_long_fr(
    value: object,
    *,
    fmt: str = "%d/%m/%y",
    allow_dayfirst_false: bool = True,
    default: str | None = "",
) -> str:
    dt_val = parse_date_value(value, fmt=fmt, allow_dayfirst_false=allow_dayfirst_false)
    if pd.isna(dt_val):
        return default if default is not None else str(value)
    try:
        day = JOURS_FR_LONG[int(dt_val.dayofweek)]
    except Exception:
        day = ""
    try:
        date_str = dt_val.strftime(fmt)
    except Exception:
        date_str = ""
    return f"{day} {date_str}".strip()


def format_date_fr_long_slash(value: object) -> str:
    """
    Format "Lundi 13/11/2025".
    """
    dt_val = coerce_datetime(value, errors="coerce", dayfirst=True)
    if pd.isna(dt_val):
        return ""
    jour = JOURS_FR_LONG[int(dt_val.dayofweek)]
    return f"{jour} {dt_val.day:02d}/{dt_val.month:02d}/{dt_val.year}"


def format_date_fr_words(value: object) -> str:
    """
    Format "Lundi 13 novembre".
    """
    dt_val = coerce_datetime(value, errors="coerce", dayfirst=True)
    if pd.isna(dt_val):
        return ""
    jour = JOURS_FR_LONG[int(dt_val.dayofweek)]
    mois = MOIS_FR_LONG[int(dt_val.month) - 1]
    return f"{jour} {dt_val.day} {mois}"


def format_heure_hh_mm(value: object) -> str:
    """
    Format "10h40" (sans zéro initial sur l'heure).
    """
    if value is None:
        return ""
    if isinstance(value, str) and "h" in value:
        return value
    if isinstance(value, dt.time):
        return f"{value.hour}h{value.minute:02d}"
    if isinstance(value, dt.datetime):
        return f"{value.hour}h{value.minute:02d}"
    try:
        dt_val = coerce_datetime(value, errors="coerce")
        if pd.notna(dt_val):
            return f"{dt_val.hour}h{dt_val.minute:02d}"
    except Exception:
        pass
    return str(value).replace(":", "h")


def parse_date_value_as_date(
    value: object,
    *,
    fmt: str = "%d/%m/%y",
    allow_dayfirst_false: bool = True,
) -> dt.date | None:
    """
    Parse une valeur en date (datetime.date) ou None si invalide.
    """
    if value in (None, ""):
        return None
    if isinstance(value, dt.date) and not isinstance(value, dt.datetime):
        return value
    if isinstance(value, dt.datetime):
        return value.date()
    dt_val = parse_date_value(value, fmt=fmt, allow_dayfirst_false=allow_dayfirst_false)
    if pd.isna(dt_val):
        return None
    try:
        return dt_val.date()
    except Exception:
        return None


def parse_time_value_as_time(value: object) -> dt.time | None:
    """
    Parse une valeur en datetime.time en mode "heures décimales".
    Exemple: 14.5 -> 14:30 (et non fraction de journée).
    """
    if value in ("", None):
        return None
    if isinstance(value, dt.time):
        return value
    if isinstance(value, dt.datetime):
        return value.time()
    try:
        sval = str(value).strip().replace("h", ":")
    except Exception:
        return None
    if not sval:
        return None
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return dt.datetime.strptime(sval, fmt).time()
        except Exception:
            continue
    try:
        num = float(sval)
        hours = int(num)
        minutes = int(round((num - hours) * 60))
        return dt.time(hour=hours, minute=minutes)
    except Exception:
        return None


def format_time_hm_loose(value: object) -> str:
    """
    Format "HH:MM" (troncature tolérante), sans forcer le padding si déjà texte.
    """
    if value in (None, ""):
        return ""
    if isinstance(value, dt.datetime):
        return value.time().strftime("%H:%M")
    if isinstance(value, dt.time):
        return value.strftime("%H:%M")
    sval = str(value).strip().replace("h", ":")
    if not sval:
        return ""
    if len(sval) >= 5:
        return sval[:5]
    return sval


def parse_date_long_fr(value: object, *, default_year: int | None = None) -> pd.Timestamp:
    """
    Parse "Lundi 01/12[/YYYY]" en Timestamp (NaT si invalide).
    """
    if pd.isna(value):
        return pd.NaT
    s = str(value).strip()
    if not s:
        return pd.NaT
    dt_val = coerce_datetime(s, errors="coerce", dayfirst=True)
    if pd.notna(dt_val):
        return dt_val
    parts = s.split()
    if len(parts) >= 2:
        date_part = parts[-1]
        year = default_year or dt.datetime.now().year
        try:
            return coerce_datetime(
                f"{date_part}/{year}",
                errors="coerce",
                dayfirst=True,
                fmt="%d/%m/%Y",
            )
        except Exception:
            return pd.NaT
    return pd.NaT


def normalize_hour_value(
    value: object,
    *,
    allow_hour_only: bool = False,
    allow_general_fallback: bool = False,
    strip_spaces: bool = False,
    lowercase: bool = False,
) -> str:
    """Normalise une valeur horaire en chaîne 'HHhMM'."""
    out = normalize_hour_str(
        pd.Series([value]),
        allow_hour_only=allow_hour_only,
        allow_general_fallback=allow_general_fallback,
        strip_spaces=strip_spaces,
        lowercase=lowercase,
    ).iloc[0]
    if pd.isna(out):
        return ""
    return str(out)


def hour_min_value(
    value: object,
    *,
    allow_hour_only: bool = False,
    allow_general_fallback: bool = False,
    strip_spaces: bool = False,
    lowercase: bool = False,
) -> int | None:
    """Retourne le nombre de minutes depuis minuit pour une valeur horaire."""
    mins = hour_min_from_series(
        pd.Series([value]),
        allow_hour_only=allow_hour_only,
        allow_general_fallback=allow_general_fallback,
        strip_spaces=strip_spaces,
        lowercase=lowercase,
    ).iloc[0]
    if pd.isna(mins):
        return None
    return int(mins)


def normalize_hour_str(
    series: pd.Series,
    *,
    allow_hour_only: bool = False,
    allow_general_fallback: bool = False,
    strip_spaces: bool = False,
    lowercase: bool = False,
) -> pd.Series:
    """
    Retourne une Series de chaînes 'HHhMM' à partir d'une série parsable en heure.
    """
    parsed = parse_time_series(
        series,
        allow_hour_only=allow_hour_only,
        allow_general_fallback=allow_general_fallback,
        strip_spaces=strip_spaces,
        lowercase=lowercase,
    )
    return parsed.dt.strftime("%Hh%M")


def hour_min_from_series(
    series: pd.Series,
    *,
    allow_hour_only: bool = False,
    allow_general_fallback: bool = False,
    strip_spaces: bool = False,
    lowercase: bool = False,
) -> pd.Series:
    """
    Calcule le nombre de minutes depuis minuit pour chaque valeur horaire.
    """
    parsed = parse_time_series(
        series,
        allow_hour_only=allow_hour_only,
        allow_general_fallback=allow_general_fallback,
        strip_spaces=strip_spaces,
        lowercase=lowercase,
    )
    return (parsed.dt.hour * 60 + parsed.dt.minute).astype("Int64")
