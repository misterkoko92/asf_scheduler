# scheduler/config_paths.py
# -*- coding: utf-8 -*-

from pathlib import Path
import unicodedata
import sys
import os


def normalize_path(p: str | Path) -> Path:
    """Normalise les chemins avec accents sur macOS et renvoie un Path absolu."""
    return Path(unicodedata.normalize("NFC", str(p))).expanduser().resolve()


# =============================================================================
# 1. Détection mode packagé PyInstaller
# =============================================================================

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    # Mode bundle .app / .exe
    BASE_DIR = Path(sys._MEIPASS)
else:
    # Mode développement
    BASE_DIR = Path(__file__).resolve().parent.parent


# =============================================================================
# 2. Fichiers OneDrive (chemins absolus, inchangés)
# =============================================================================

TABLEAU_DE_BORD = normalize_path(
    "/Users/EdouardGonnu/Library/CloudStorage/"
    "OneDrive-AviationSansFrontières/Hélida/TABLEAU DE BORD.xlsx"
)

PLANNING_BENEVOLES = normalize_path(
    "/Users/EdouardGonnu/Library/CloudStorage/"
    "OneDrive-AviationSansFrontières/Planning Bénévoles/Planning BENEVOLE 2025.xlsx"
)


# =============================================================================
# 3. Chemins locaux embarqués dans le bundle
# =============================================================================

VOLS = normalize_path(BASE_DIR / "data" / "Vols.xlsx")
(VOLS.parent).mkdir(exist_ok=True, parents=True)


# =============================================================================
# 4. Feuilles Excel
# =============================================================================

SHEET_MAG_CENTRAL = "MAG CENTRAL"
SHEET_PARAM_BE = "ParamBE"
SHEET_PARAM_DEST = "ParamDest"
SHEET_PARAM_EXP = "ParamExpediteur"

SHEET_PARAM_BENEV = "ParamBenev"
SHEET_BENEV_DISPO = "Disponibilités"
SHEET_SOURCE_BENEV = "Source"

SHEET_VOLS = "Vols"


# =============================================================================
# 5. Sorties
# =============================================================================

OUTPUT_DIR = normalize_path(BASE_DIR / "planning_resultats")
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

OUTPUT_PLANNING = normalize_path(OUTPUT_DIR / "Planning.xlsx")
OUTPUT_BILAN = normalize_path(OUTPUT_DIR / "Bilan.xlsx")


# =============================================================================
# 6. Logo PDF ASF
# =============================================================================

LOGO_HORIZONTAL = normalize_path(
    BASE_DIR / "asf_app" / "assets" / "HORIZONTAL.jpg"
)

if not LOGO_HORIZONTAL.exists():
    print(f"⚠️ LOGO_HORIZONTAL introuvable : {LOGO_HORIZONTAL}")


# =============================================================================
# 7. Maquette de planning
# =============================================================================

PLANNING_TEMPLATE = normalize_path(BASE_DIR / "data" / "Planning-maquette.xlsx")

OUTPUT_PLANNING_DIR = normalize_path(
    "/Users/EdouardGonnu/Library/CloudStorage/"
    "OneDrive-AviationSansFrontières/Planning MAB/ASFmm PLANNING 2025"
)
OUTPUT_PLANNING_DIR.mkdir(exist_ok=True, parents=True)
