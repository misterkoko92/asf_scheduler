import pandas as pd


def parse_date_series(series: pd.Series, fmt: str = "%d/%m/%y") -> pd.Series:
    """
    Parse une série de dates en privilégiant le format fourni, avec fallback dayfirst.
    Retourne une Series datetime64[ns] (NaT si invalide).
    """
    ser = pd.to_datetime(series, format=fmt, errors="coerce")
    mask = ser.isna()
    if mask.any():
        ser.loc[mask] = pd.to_datetime(series.loc[mask], errors="coerce", dayfirst=True)
        mask = ser.isna()
        if mask.any():
            ser.loc[mask] = pd.to_datetime(series.loc[mask], errors="coerce", dayfirst=False)
    return ser


def parse_time_series(series: pd.Series) -> pd.Series:
    """
    Parse une série d'heures (peut contenir '10h00' ou '10:00').
    Retourne une Series datetime64[ns] (NaT si invalide).
    """
    s_clean = series.astype(str).str.strip().str.replace("h", ":", regex=False)
    ser = pd.to_datetime(s_clean, format="%H:%M", errors="coerce")
    mask = ser.isna()
    if mask.any():
        ser.loc[mask] = pd.to_datetime(s_clean.loc[mask], format="%H:%M:%S", errors="coerce")
    # Support des heures Excel en format numérique (fraction de journée)
    num = pd.to_numeric(series, errors="coerce")
    num_mask = ser.isna() & num.notna()
    if num_mask.any():
        seconds = (num[num_mask] * 86400).round().astype("Int64")
        ser.loc[num_mask] = pd.to_datetime(seconds, unit="s", errors="coerce")
    return ser


def normalize_hour_str(series: pd.Series) -> pd.Series:
    """
    Retourne une Series de chaînes 'HHhMM' à partir d'une série parsable en heure.
    """
    parsed = parse_time_series(series)
    return parsed.dt.strftime("%Hh%M")


def hour_min_from_series(series: pd.Series) -> pd.Series:
    """
    Calcule le nombre de minutes depuis minuit pour chaque valeur horaire.
    """
    parsed = parse_time_series(series)
    return (parsed.dt.hour * 60 + parsed.dt.minute).astype("Int64")
