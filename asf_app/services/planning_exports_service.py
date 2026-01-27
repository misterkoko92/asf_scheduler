# -*- coding: utf-8 -*-
from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Optional, List

import pandas as pd

import scheduler.config_paths as cp
from asf_app.config.runtime import (
    get_onedrive_root,
    get_tmp_dir,
    is_graph_onedrive,
    get_output_remote_dir,
)
from utils.logging_utils import get_logger
from utils.datetime_utils import parse_date_long_fr

logger = get_logger("planning_exports_service", console=False)


def load_planning_preview(week: int, year: int) -> tuple[pd.DataFrame | None, str, Path | None]:
    """
    Charge un aperçu du planning validé (fichier exporté) pour la semaine choisie.
    Retourne (df, message, path).
    """
    return load_planning_preview_with_path(week, year, None)


def load_planning_preview_with_path(
    week: int, year: int, path_override: Optional[Path | str]
) -> tuple[pd.DataFrame | None, str, Path | None]:
    """
    Variante : accepte un chemin explicite si déjà sélectionné.
    """
    msg_missing = None
    if is_graph_onedrive():
        if path_override:
            remote_path = str(path_override)
        else:
            candidates = find_planning_files_for_week(week, year)
            if not candidates:
                return None, f"Fichier introuvable : S{week:02d}-{year}", None
            remote_path = str(candidates[0])
        local_path = get_tmp_dir() / "onedrive_cache" / "planning_exports" / remote_path
        if not local_path.exists():
            cp.download_onedrive_file(remote_path, local_path, interactive=False)
        if not local_path.exists():
            return None, f"Fichier introuvable : {remote_path}", None
        path = local_path
    else:
        base_dir = get_onedrive_root() / "Planning MAB" / f"ASFmm PLANNING {year}"
        if path_override:
            path = Path(path_override)
        else:
            filename = f"ASFmm - PLANNING SEMAINE {year}-{week:02d}-01.xlsx"
            path = base_dir / filename
            if not path.exists():
                # tolérance sur nom : espaces, tirets, xlsm/xlsx
                patterns = [
                    f"ASFmm*{week:02d}*{year}.xls*",
                    f"*PLANNING*{week:02d}*{year}.xls*",
                ]
                candidates = []
                for pat in patterns:
                    candidates.extend(base_dir.glob(pat))
                if candidates:
                    # garder ceux qui contiennent la semaine précise
                    def _score(p):
                        name_up = p.name.upper()
                        return int(f"{name_up.count(str(week).zfill(2))}{name_up.count(str(year))}")
                    path = sorted(candidates, key=_score, reverse=True)[0]
                    msg_missing = f"Fichier exact introuvable, utilisation de : {path.name}"
                else:
                    return None, f"Fichier introuvable : {path}", None
            else:
                msg_missing = None

    sheet_candidates = [f"Planning S{week:02d}", "Export planning"]
    for sh in sheet_candidates:
        try:
            df_prev = pd.read_excel(path, sheet_name=sh)
            if df_prev is not None and not df_prev.empty:
                if msg_missing:
                    return df_prev, f"{msg_missing} — Aperçu basé sur la feuille « {sh} »", path
                return df_prev, f"Aperçu basé sur la feuille « {sh} »", path
        except Exception as exc:
            logger.debug("Erreur lecture preview %s/%s: %s", path, sh, exc)
            continue
    if msg_missing:
        return None, f"{msg_missing} — Impossible de lire les feuilles {sheet_candidates} dans {path.name}", path
    return None, f"Impossible de lire les feuilles {sheet_candidates} dans {path.name}", path


def available_weeks_from_exports() -> set[tuple[int, int]]:
    """
    Retourne les semaines dispo en inspectant les fichiers d'export Excel
    dans OneDrive (ASFmm PLANNING YYYY).
    """
    weeks: set[tuple[int, int]] = set()
    if is_graph_onedrive():
        items = cp.list_onedrive_files("Planning MAB", recursive=True, suffixes=[".xls", ".xlsx", ".xlsm"])
        for item in items:
            name = item.get("name", "")
            m_new = re.search(r"SEMAINE\s*(20\d{2})\D+(\d{1,2})", name, re.IGNORECASE)
            m_week = re.search(r"N°\s*(\d+)", name)
            m_year = re.search(r"(20\d{2})", name)
            try:
                if m_new:
                    yr = int(m_new.group(1))
                    wk = int(m_new.group(2))
                    weeks.add((wk, yr))
                elif m_week and m_year:
                    wk = int(m_week.group(1))
                    yr = int(m_year.group(1))
                    weeks.add((wk, yr))
            except Exception:
                continue
        return weeks

    base_dir = get_onedrive_root() / "Planning MAB"
    if not base_dir.exists():
        return weeks

    for sub in base_dir.iterdir():
        if not sub.is_dir():
            continue
        name_up = sub.name.upper()
        if not name_up.startswith("ASFMM PLANNING "):
            continue
        try:
            year = int(re.sub(r"\D", "", sub.name)[-4:])
        except Exception:
            continue
        for f in sub.glob("ASFmm - PLANNING SEMAINE *.xls*"):
            m_new = re.search(r"SEMAINE\s*(20\d{2})\D+(\d{1,2})", f.name, re.IGNORECASE)
            m_old = re.search(r"N°\s*(\d+)", f.name)
            try:
                if m_new:
                    wk = int(m_new.group(2))
                    weeks.add((wk, year))
                elif m_old:
                    wk = int(m_old.group(1))
                    weeks.add((wk, year))
            except Exception:
                continue
    return weeks


def parse_version_from_name(path: Path) -> tuple[int, int]:
    """
    Extrait vXX[-YY] du nom de fichier. Par défaut retourne (1,0).
    """
    stem = path.stem.upper()
    m = re.search(r"SEMAINE\s*20\d{2}\D+\d{1,2}\D+(\d+)", stem, re.IGNORECASE)
    if m:
        try:
            major = int(m.group(1))
            return major, 0
        except Exception:
            pass
    m = re.search(r"V(\d+)(?:-(\d+))?", stem)
    if m:
        try:
            major = int(m.group(1))
            minor = int(m.group(2) or 0)
            return major, minor
        except Exception:
            pass
    return 1, 0


def find_planning_files_for_week(week: int, year: int) -> List[Path | str]:
    """
    Liste les fichiers de planning correspondant à la semaine/année,
    triés par version décroissante (vXX[-YY]) puis date de modif.
    """
    if is_graph_onedrive():
        remote_dir = get_output_remote_dir(year)
        pattern_old = f"ASFmm - PLANNING SEMAINE N° {week:02d} - {year}*.xls*"
        pattern_new = f"ASFmm - PLANNING SEMAINE {year}-{week:02d}-*.xls*"
        items = cp.list_onedrive_files(remote_dir, recursive=False, suffixes=[".xls", ".xlsx", ".xlsm"])
        files = [
            i.get("path", "")
            for i in items
            if fnmatch.fnmatch(i.get("name", ""), pattern_old)
            or fnmatch.fnmatch(i.get("name", ""), pattern_new)
        ]

        def _sort_key(p: str):
            major, minor = parse_version_from_name(Path(p))
            return (major, minor, 0)

        files.sort(key=_sort_key, reverse=True)
        return files

    base_dir = get_onedrive_root() / "Planning MAB" / f"ASFmm PLANNING {year}"
    if not base_dir.exists():
        return []
    pattern_old = f"ASFmm - PLANNING SEMAINE N° {week:02d} - {year}*.xls*"
    pattern_new = f"ASFmm - PLANNING SEMAINE {year}-{week:02d}-*.xls*"
    files = list(base_dir.glob(pattern_old)) + list(base_dir.glob(pattern_new))
    files = [p for p in files if p.is_file()]

    def _sort_key(p: Path):
        major, minor = parse_version_from_name(p)
        try:
            mtime = p.stat().st_mtime
        except Exception:
            mtime = 0
        return (major, minor, mtime)

    files.sort(key=_sort_key, reverse=True)
    return files


def load_planning_xlsx(path: Path, default_year: int | None = None) -> pd.DataFrame:
    """
    Loader robuste pour les plannings ASFmm 2025 (formats Excel / macro).

    Hypothèses sur la maquette :
    - On ne regarde que le PREMIER onglet.
    - Colonnes A→Q (0→16) contiennent :
        A : bloc jour / vide / TOTAL
        B : ITEM (masqué, inutilisé)
        C : DATE LONGUE (vraie date Excel)
        D : NOM bénévoles (format Prénom / Prénom court + NOM)
        ...
        F : DESTINATION (nom complet, ex : BRAZZAVILLE)
        G : IATA (ex : BZV)
        H : ROUTING
        I : N° de vol
        J : Heure de vol
        K : N° BE (YYNNNN)
        L : Nb colis
        M : Type de colis
        N : Observations (ignoré)
        O : Date transfert
        P : Expéditeur
        Q : Destinataire

    Sortie :
        DataFrame avec colonnes :
        ['date', 'nom', 'destination_nom', 'destination_iata', 'routing',
         'vol_info', 'heure', 'be', 'nb_colis', 'type', 'expediteur',
         'destinataire']
    """
    path = Path(path)
    if not path.exists():
        return pd.DataFrame()

    try:
        df_raw = pd.read_excel(path, sheet_name=0, header=None, dtype=object)
    except Exception as exc:
        logger.warning("[load_planning_xlsx] Erreur lecture Excel %s: %s", path, exc)
        return pd.DataFrame()

    if df_raw.empty:
        return pd.DataFrame()

    # Certains fichiers ont moins de colonnes : on pad jusqu’à 17 colonnes.
    min_cols = 17
    n_cols = max(min_cols, df_raw.shape[1])
    df = df_raw.reindex(columns=range(n_cols)).iloc[:, :17].copy()
    df.columns = list(range(17))

    df2 = pd.DataFrame()
    df2["date_longue"] = df[2].apply(lambda val: parse_date_long_fr(val, default_year=default_year))
    df2["date"] = df2["date_longue"].ffill().dt.date.astype("string")

    df2["nom"] = df[3]
    df2["destination_nom"] = df[5]
    df2["destination_iata"] = df[6]
    df2["routing"] = df[7]
    df2["vol_info"] = df[8]
    df2["heure"] = df[9]
    df2["be_raw"] = df[10]
    df2["nb_colis"] = df[11]
    df2["type"] = df[12]
    df2["expediteur"] = df[15]   # Colonne P
    df2["destinataire"] = df[16]  # Colonne Q

    # Certaines lignes masquent volontairement routing/vol/heure pour lisibilité.
    # On remplit les vides successifs avec la première ligne complète du bloc.
    fill_cols = [
        "nom",
        "destination_nom",
        "destination_iata",
        "routing",
        "vol_info",
        "heure",
        "date",
        "expediteur",
        "destinataire",
    ]
    for col in fill_cols:
        df2[col] = df2[col].replace(r"^\s*$", pd.NA, regex=True).ffill()

    df2["be"] = (
        df2["be_raw"]
        .astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.strip()
    )

    mask_be = df2["be"].str.match(r"^\d+$", na=False)
    df2 = df2[mask_be].copy()

    if df2.empty:
        return pd.DataFrame()

    try:
        df2["nb_colis"] = (
            pd.to_numeric(df2["nb_colis"], errors="coerce")
            .fillna(0)
            .astype(int)
        )
    except Exception:
        df2["nb_colis"] = 0

    for col in [
        "nom",
        "destination_nom",
        "destination_iata",
        "routing",
        "vol_info",
        "heure",
        "type",
        "expediteur",
        "destinataire",
    ]:
        df2[col] = df2[col].astype(str).str.strip()

    keep = [
        "date",
        "nom",
        "destination_nom",
        "destination_iata",
        "routing",
        "vol_info",
        "heure",
        "be",
        "nb_colis",
        "type",
        "expediteur",
        "destinataire",
    ]
    return df2[keep]
