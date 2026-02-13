# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Iterable, Mapping, MutableMapping
from typing import Any

import pandas as pd

from scheduler.format_rules import format_be_number, format_vol_display
from utils.identifiers import normalize_be_number


def _norm_be(val: object) -> str:
    return normalize_be_number(val) or str(val).strip()


def _keys_from_be(val: object) -> list[str]:
    normalized = _norm_be(val)
    keys = {normalized}
    for n in [6, 5, 4, 3]:
        if len(normalized) >= n:
            keys.add(normalized[-n:])
    return [k for k in keys if k]


def _collect_dest_map(df_source: pd.DataFrame | None) -> dict[str, object]:
    mapping: dict[str, object] = {}
    if df_source is None or df_source.empty:
        return mapping
    for _, row in df_source.iterrows():
        dest_val = row.get("BE_Destinataire", "")
        if pd.isna(dest_val) or str(dest_val).strip() == "":
            continue
        for key in _keys_from_be(row.get("BE_Numero", "")):
            if key not in mapping:
                mapping[key] = dest_val
    return mapping


def build_destinataire_mapping(
    *,
    df_be: pd.DataFrame | None,
    df_planning: pd.DataFrame | None,
) -> dict[str, object]:
    mapping: dict[str, object] = {}
    mapping.update(_collect_dest_map(df_be))
    if df_planning is not None and "BE_Destinataire" in df_planning.columns:
        mapping.update(_collect_dest_map(df_planning))
    return mapping


def _key_from_comm_row(row: pd.Series) -> str:
    for col in ["NUMERO BE", "BE_Numero", "Numero_BE_Aff", "Numero_BE"]:
        if col in row and str(row[col]).strip():
            return _norm_be(row[col])
    return ""


def fill_missing_destinataire(
    df_comm: pd.DataFrame,
    mapping: dict[str, object],
) -> pd.DataFrame:
    df_out = df_comm.copy()
    if not mapping:
        return df_out

    if "Destinataire" not in df_out.columns:
        df_out["Destinataire"] = ""
    df_out["Destinataire"] = df_out["Destinataire"].replace("", pd.NA)

    def _lookup_dest(row: pd.Series) -> object:
        keys = _keys_from_be(_key_from_comm_row(row))
        for key in keys:
            if key in mapping:
                return mapping[key]
        return ""

    mask_dest_empty = (
        df_out["Destinataire"].isna()
        | df_out["Destinataire"].astype(str).str.strip().eq("")
    )
    df_out.loc[mask_dest_empty, "Destinataire"] = df_out.loc[mask_dest_empty].apply(
        _lookup_dest,
        axis=1,
    )
    return df_out


def fill_column_from_candidate_keywords(
    df: pd.DataFrame,
    *,
    target: str,
    keywords: Iterable[str],
) -> pd.DataFrame:
    df_out = df.copy()
    if target not in df_out.columns:
        df_out[target] = ""
    df_out[target] = df_out[target].replace("", pd.NA)
    for col in df_out.columns:
        if any(k.lower() in col.lower() for k in keywords):
            df_out[target] = df_out[target].fillna(df_out[col]).replace("", pd.NA)
    df_out[target] = df_out[target].fillna("").astype(str)
    return df_out


def _first_existing_series(
    df: pd.DataFrame,
    candidates: list[str],
) -> pd.Series:
    for col in candidates:
        if col in df.columns:
            return df[col]
    return pd.Series([""] * len(df), index=df.index)


def build_communication_display_dataframe(df_comm: pd.DataFrame) -> pd.DataFrame:
    df_display = df_comm.copy()
    df_display["Numero_BE_Aff"] = _first_existing_series(
        df_display,
        ["Numero_BE_Aff", "NUMERO BE", "BE_Numero"],
    ).apply(format_be_number)
    df_display["Numero_Vol_Aff"] = _first_existing_series(
        df_display,
        ["Numero_Vol_Aff", "NUMERO VOL"],
    ).apply(format_vol_display)
    df_display["Heure_Vol_Aff"] = (
        _first_existing_series(df_display, ["Heure_Vol_Aff", "HEURE VOL"])
        .astype(str)
        .str.slice(0, 5)
        .str.replace(":", "h", 1)
    )
    df_display = fill_column_from_candidate_keywords(
        df_display,
        target="Destinataire",
        keywords=["destinataire"],
    )
    df_display = fill_column_from_candidate_keywords(
        df_display,
        target="Expediteur",
        keywords=["expediteur", "expéditeur"],
    )
    return df_display


def is_empty_dataframe(df: object) -> bool:
    return df is None or getattr(df, "empty", True)


def build_session_source_options(
    *,
    df_plan_main: pd.DataFrame | None,
    sim_res_modes: Mapping[str, dict[str, Any]] | None,
) -> list[str]:
    options: list[str] = []
    if not is_empty_dataframe(df_plan_main):
        options.append("planning")
    if sim_res_modes:
        options.append("simulation")
    return options


def resolve_default_session_source(options: list[str]) -> str:
    return "planning" if "planning" in options else options[0]


def build_sim_mode_selector_data(
    sim_res_modes: Mapping[str, dict[str, Any]] | None,
) -> tuple[list[str], dict[str, str]]:
    mode_values: list[str] = []
    mode_labels: dict[str, str] = {}
    for key, res in (sim_res_modes or {}).items():
        stats_mode = res.get("statistiques", {})
        label = "Priorité Colis" if key == "colis" else "Priorité Bénévoles"
        extra = (
            f" ({stats_mode.get('nb_colis_expedies', 0)} colis / "
            f"{stats_mode.get('nb_benevoles_mobilises', 0)} bénév)"
        )
        mode_values.append(key)
        mode_labels[key] = f"{label}{extra}"
    return mode_values, mode_labels


def reset_onedrive_loaded_state_for_year(
    session_state: MutableMapping[str, Any],
    *,
    year: int,
) -> None:
    loaded_year = session_state.get("comm_onedrive_loaded_year")
    if loaded_year is None or loaded_year == year:
        return
    session_state.pop("comm_onedrive_df", None)
    session_state.pop("comm_onedrive_file_label", None)
    session_state.pop("comm_onedrive_file_path", None)
    session_state["comm_onedrive_loaded_year"] = None
