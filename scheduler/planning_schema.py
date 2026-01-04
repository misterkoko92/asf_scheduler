# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List
from uuid import uuid4

import pandas as pd

from utils.datetime_utils import parse_date_series, parse_time_series


@dataclass(frozen=True)
class PlanningSchema:
    required: List[str]
    optional: List[str]

    @property
    def columns(self) -> List[str]:
        return [*self.required, *self.optional]


SCHEMA = PlanningSchema(
    required=[
        "Date_Vol",
        "Heure_Vol",
        "Numero_Vol",
        "Destination",
        "BE_Numero",
        "BE_Nb_Colis",
        "BE_Nb_Equiv",
        "Benevole",
        "ID",
    ],
    optional=[
        "BE_Type",
        "BE_Expediteur",
        "BE_Destinataire",
        "Telephone",
        "Routing",
        "_MANUEL",
        "_STATUS",
        "UID",
    ],
)


ALIASES = {
    "Numero_Vol": ["Numero_Vol", "Vol", "NUMERO VOL", "Numero Vol"],
    "Destination": ["Destination", "Dest_IATA", "IATA", "Dest_IATA_UP"],
    "BE_Numero": ["BE_Numero", "NUMERO BE", "BE NUMERO", "BE_Num", "BE_numero"],
    "BE_Nb_Colis": ["BE_Nb_Colis", "NB_COLIS", "NOMBRE COLIS"],
    "BE_Nb_Equiv": ["BE_Nb_Equiv", "BE_Poids_Equiv", "BE_Equiv", "Equiv_Colis"],
    "Benevole": ["Benevole", "BENEVOLE"],
    "ID": ["ID", "BENEVOLE_ID", "ID_BENEVOLE"],
    "BE_Type": ["BE_Type", "TYPE", "TYPE_COLIS"],
    "BE_Expediteur": ["BE_Expediteur", "EXPEDITEUR", "EXP"],
    "BE_Destinataire": ["BE_Destinataire", "DESTINATAIRE"],
    "Telephone": ["Telephone", "TELEPHONE", "Telephone_Benevole"],
    "Routing": ["Routing", "ROUTING", "Routing_Str"],
    "_MANUEL": ["_MANUEL"],
    "_STATUS": ["_STATUS"],
    "UID": ["UID"],
    "Date_Vol": ["Date_Vol", "DATE"],
    "Heure_Vol": ["Heure_Vol", "HEURE VOL", "Heure VOL"],
}


def _first_existing(df: pd.DataFrame, candidates: Iterable[str]) -> str | None:
    for name in candidates:
        if name in df.columns:
            return name
    return None


def _strip_af_prefix(value: str) -> str:
    s = str(value or "").strip()
    s = s.replace("AF ", "").replace("AF", "").strip() if s.upper().startswith("AF") else s
    return s.replace(".0", "").strip()


def _normalize_be_num(value: object) -> str:
    s = str(value or "").strip()
    if s.endswith(".0"):
        s = s[:-2]
    digits = "".join(ch for ch in s if ch.isdigit())
    if not digits:
        return s
    if len(digits) >= 6:
        return digits[-6:]
    return digits.zfill(6)


def normalize_planning_df(df: pd.DataFrame | None) -> pd.DataFrame:
    """
    Normalise un planning pour respecter le schéma canonique unique.
    Toute sortie est filtrée sur les colonnes du schéma.
    """
    if df is None or getattr(df, "empty", True):
        return pd.DataFrame(columns=SCHEMA.columns)

    df_norm = df.copy()

    # Recréer les colonnes canoniques à partir des aliases
    for target, variants in ALIASES.items():
        if target in df_norm.columns:
            continue
        src = _first_existing(df_norm, variants)
        if src is not None:
            df_norm[target] = df_norm[src]
        else:
            df_norm[target] = ""

    # Normalisations
    df_norm["Date_Vol"] = parse_date_series(df_norm["Date_Vol"]).dt.date
    df_norm["Heure_Vol"] = (
        parse_time_series(df_norm["Heure_Vol"])
        .dt.strftime("%H:%M")
        .fillna("")
    )

    df_norm["Numero_Vol"] = df_norm["Numero_Vol"].apply(_strip_af_prefix)
    df_norm["Destination"] = (
        df_norm["Destination"].astype(str).str.strip().str.upper().replace("NAN", "")
    )
    df_norm["BE_Numero"] = df_norm["BE_Numero"].apply(_normalize_be_num)

    df_norm["BE_Nb_Colis"] = (
        pd.to_numeric(df_norm["BE_Nb_Colis"], errors="coerce")
        .fillna(0)
        .astype(int)
    )
    df_norm["BE_Nb_Equiv"] = (
        pd.to_numeric(df_norm["BE_Nb_Equiv"], errors="coerce")
        .fillna(df_norm["BE_Nb_Colis"])
        .astype(int)
    )

    df_norm["Benevole"] = df_norm["Benevole"].astype(str).fillna("")
    df_norm["ID"] = (
        df_norm["ID"].astype(str).str.replace(r"\.0$", "", regex=True).fillna("")
    )

    for col in ["BE_Type", "BE_Expediteur", "BE_Destinataire", "Telephone"]:
        df_norm[col] = df_norm[col].astype(str).fillna("")

    df_norm["_MANUEL"] = (
        df_norm["_MANUEL"]
        .fillna(False)
        .astype(str)
        .str.strip()
        .str.lower()
        .isin({"true", "1", "yes", "vrai"})
    )
    df_norm["_STATUS"] = (
        df_norm["_STATUS"]
        .fillna("normal")
        .astype(str)
        .str.strip()
        .replace({"": "normal", "nan": "normal"})
    )

    if "UID" not in df_norm.columns or df_norm["UID"].isna().any():
        df_norm["UID"] = df_norm.get("UID", "")
        df_norm["UID"] = df_norm["UID"].replace("", pd.NA)
        df_norm.loc[df_norm["UID"].isna(), "UID"] = [
            str(uuid4()) for _ in range(df_norm["UID"].isna().sum())
        ]

    return df_norm[SCHEMA.columns].copy()


def validate_planning_df(df: pd.DataFrame | None) -> List[str]:
    """
    Retourne la liste des erreurs de schéma détectées.
    """
    if df is None:
        return ["planning_df is None"]
    missing = [c for c in SCHEMA.required if c not in df.columns]
    errors = []
    if missing:
        errors.append(f"Missing columns: {', '.join(missing)}")
    return errors


def assert_planning_schema(df: pd.DataFrame | None) -> None:
    """
    Lève une ValueError si le planning ne respecte pas le schéma canonique.
    """
    errors = validate_planning_df(df)
    if errors:
        raise ValueError("Planning schema invalid: " + "; ".join(errors))
