# -*- coding: utf-8 -*-
from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd
import pytest

import scheduler.config_paths as cp
from loaders import load_shipments as ls
from loaders import load_vols as lv
from loaders import load_benevoles as lb
from loaders.load_params import clear_param_caches
from loaders.load_shipments import clear_shipments_cache
from loaders.load_benevoles import clear_benevoles_cache
from loaders.load_vols import clear_vols_cache
from scheduler import be_manager


@pytest.fixture()
def sample_onedrive(tmp_path, monkeypatch):
    """
    Build a minimal OneDrive-like tree with Excel sources and wire config_paths to it.
    """
    root = tmp_path / "onedrive"
    root.mkdir(parents=True, exist_ok=True)

    tdb_dir = root / "Helida"
    tdb_dir.mkdir(parents=True, exist_ok=True)
    tdb_path = tdb_dir / "TABLEAU DE BORD.xlsx"

    df_mag = pd.DataFrame(
        [
            {
                "N° BE": "250001",
                "NB": 2,
                "DEST": "DLA",
                "TYPE": "MM",
                "Douane ?": "",
                "EXP": "ASF",
                "DESTINATAIRE": "Hopital",
                "DATE IMPRESSION BE": "01/01/2025",
                "Statut BE": "D",
                "Plannification Spéciale": "",
            },
            {
                "N° BE": "250002",
                "NB": 1,
                "DEST": "DLA",
                "TYPE": "MM",
                "Douane ?": "",
                "EXP": "ASF",
                "DESTINATAIRE": "Hopital",
                "DATE IMPRESSION BE": "01/01/2025",
                "Statut BE": "X",
                "Plannification Spéciale": "",
            },
        ]
    )

    df_param_be = pd.DataFrame(
        [
            {"Type": "MM", "Priorite_Type": 3, "Equiv": 2},
            {"Type": "AUTRE", "Priorite_Type": 99, "Equiv": 1},
        ]
    )

    df_param_dest = pd.DataFrame(
        [
            {
                "Destination": "DLA",
                "Ville": "DOUALA",
                "Max_Colis_Par_Vol": 10,
                "Freq_Semaine": 1,
                "Mercredi": "OK",
            }
        ]
    )

    with pd.ExcelWriter(tdb_path) as writer:
        df_mag.to_excel(writer, sheet_name="MAG CENTRAL", index=False, startrow=5)
        df_param_be.to_excel(writer, sheet_name="ParamBE", index=False)
        df_param_dest.to_excel(writer, sheet_name="ParamDest", index=False)

    benev_dir = root / "Planning Bénévoles"
    benev_dir.mkdir(parents=True, exist_ok=True)
    benev_path = benev_dir / "Planning BENEVOLE 2025.xlsx"

    df_param_benev = pd.DataFrame(
        [
            {
                "ID": "1",
                "BENEVOLE": "DUPONT",
                "NOM": "Dupont",
                "PRENOM": "Jean",
                "PRENOM_COURT": "Jean",
                "MAX_JOURS_SEMAINE": 5,
                "MAX_EXP_SEMAINE": 10,
                "MAX_EXP_JOUR": 5,
                "ATTENTE_MAX_H": 5,
                "Telephone": "0600000000",
            }
        ]
    )

    df_dispos = pd.DataFrame(
        [
            {
                "ID": "1",
                "BENEVOLE": "Dupont",
                "NOM": "Dupont",
                "PRENOM": "Jean",
                "PRENOM_COURT": "Jean",
                "DATE": "01/01/2025",
                "HEURE_ARRIVEE": "06h00",
                "HEURE_DEPART": "12:00",
            }
        ]
    )

    with pd.ExcelWriter(benev_path) as writer:
        df_param_benev.to_excel(writer, sheet_name="ParamBenev", index=False)
        df_dispos.to_excel(writer, sheet_name="Disponibilités", index=False)

    vols_dir = root / "Planning MAB" / "Fichiers Source" / "aVols"
    vols_dir.mkdir(parents=True, exist_ok=True)
    vols_path = vols_dir / "Vols.xlsx"

    df_vols = pd.DataFrame(
        [
            {
                "PVOL_DATE": "01/01/2025",
                "PVOL_HEURE": "10:00",
                "PVOL_NUMERO": "1234",
                "PVOL_ROUTE_API": "CDG, DLA",
            }
        ]
    )
    df_vols.to_excel(vols_path, sheet_name="Vols", index=False)

    tmp_dir = (tmp_path / "tmp_asf").resolve()
    tmp_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(tdb_path, tmp_dir / "TABLEAU_DE_BORD.xlsx")
    shutil.copy2(benev_path, tmp_dir / "PLANNING_BENEVOLES.xlsx")
    shutil.copy2(vols_path, tmp_dir / "VOLS.xlsx")

    monkeypatch.setattr(cp, "ASF_ONEDRIVE", root)
    monkeypatch.setattr(cp, "TABLEAU_DE_BORD_SRC", tdb_path)
    monkeypatch.setattr(cp, "PLANNING_BENEVOLES_SRC", benev_path)
    monkeypatch.setattr(cp, "VOLS_SRC", vols_path)
    monkeypatch.setattr(cp, "TMP_DIR", tmp_dir)
    monkeypatch.setattr(cp, "TABLEAU_DE_BORD", tmp_dir / "TABLEAU_DE_BORD.xlsx")
    monkeypatch.setattr(cp, "PLANNING_BENEVOLES", tmp_dir / "PLANNING_BENEVOLES.xlsx")
    monkeypatch.setattr(cp, "VOLS", tmp_dir / "VOLS.xlsx")

    monkeypatch.setattr(ls, "TABLEAU_DE_BORD", cp.TABLEAU_DE_BORD)
    monkeypatch.setattr(lv, "TABLEAU_DE_BORD", cp.TABLEAU_DE_BORD)
    monkeypatch.setattr(lv, "VOLS", cp.VOLS)
    monkeypatch.setattr(lv, "VOLS_SRC", cp.VOLS_SRC)
    monkeypatch.setattr(lb, "PLANNING_BENEVOLES", cp.PLANNING_BENEVOLES)

    be_manager.reset_param_be_cache()
    clear_param_caches()
    clear_shipments_cache()
    clear_benevoles_cache()
    clear_vols_cache()

    return root
