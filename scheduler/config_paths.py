# scheduler/config_paths.py
# -*- coding: utf-8 -*-

from pathlib import Path
import os
import shutil
import unicodedata
import glob
from datetime import datetime

IS_STREAMLIT_CLOUD = bool(
    os.getenv("STREAMLIT_RUNTIME")
    or os.getenv("STREAMLIT_SERVER_ENABLED")
    or os.getenv("STREAMLIT_BROWSER_GAP_DETECTION")
)
CLOUD_MESSAGE = (
    "Pas de chargement automatique sur Streamlit Cloud — "
    "merci de sélectionner manuellement TABLEAU DE BORD, PLANNING BENEVOLE et VOLS."
)

# =============================================================================
# ONEDRIVE MODE (LOCAL vs GRAPH)
# =============================================================================

ONEDRIVE_MODE = os.getenv("ASF_ONEDRIVE_MODE", "").strip().lower()
USE_GRAPH_ONEDRIVE = ONEDRIVE_MODE == "graph" or os.getenv("ASF_GRAPH_ENABLE", "").strip() == "1"
GRAPH_CLIENT_ID = os.getenv("ASF_GRAPH_CLIENT_ID", "").strip()
GRAPH_TENANT_ID = os.getenv("ASF_GRAPH_TENANT_ID", "").strip()
GRAPH_SCOPES = [
    s.strip()
    for s in os.getenv(
        "ASF_GRAPH_SCOPES",
        "User.Read,Files.ReadWrite,offline_access",
    ).split(",")
    if s.strip()
]
# =============================================================================
# NORMALISATION & BASES
# =============================================================================

def normalize(p):
    """Normalise les accents (NFC), expanduser, resolve."""
    return Path(unicodedata.normalize("NFC", str(p))).expanduser().resolve()


BASE_DIR = Path(__file__).resolve().parent.parent


# =============================================================================
# ONEDRIVE ASF — CONFIGURABLE
# =============================================================================

def detect_onedrive_asf() -> Path:
    """
    Détecte OneDrive ASF (macOS CloudStorage ou OneDrive local Windows).
    Peut être surchargé via l’ENV ASF_ONEDRIVE_ROOT.
    """
    env_override = os.getenv("ASF_ONEDRIVE_ROOT")
    if env_override:
        return normalize(env_override)

    home = Path.home()

    # 1) macOS CloudStorage (OneDrive-* et OneDrive-Bibliothèquespartagées-*)
    cloud = normalize(home / "Library/CloudStorage")
    if cloud.exists():
        patterns = [
            "OneDrive-AviationSansFrontières",  # chemin confirmé mac
            "OneDrive-AviationSansFrontières",
            "OneDrive-*",
            "OneDrive-Bibliothèquespartagées-*",
            "OneDrive-Bibliothequespartagees-*",
        ]
        for pat in patterns:
            candidates = list(glob.glob(str(cloud / pat)))
            for c in candidates:
                name = unicodedata.normalize("NFC", Path(c).name)
                if "OneDrive" in name:
                    return normalize(c)

    # 2) Windows / macOS OneDrive classique
    candidates = [
        home / "OneDrive - Aviation Sans Frontières",
        home / "OneDrive - AviationSansFrontières",
        home / "OneDrive",
    ]
    for c in candidates:
        if c.exists():
            return normalize(c)

    # 3) Fallback : HOME (permet de continuer même sans OneDrive)
    return normalize(home)


ASF_ONEDRIVE = detect_onedrive_asf()


# =============================================================================
# CHEMINS DES FICHIERS SOURCES (ONEDRIVE)
# =============================================================================

TABLEAU_DE_BORD_SRC = normalize(ASF_ONEDRIVE / "Hélida" / "TABLEAU DE BORD.xlsx")
PLANNING_BENEVOLES_SRC = normalize(
    ASF_ONEDRIVE / "Planning Bénévoles" / "Planning BENEVOLE.xlsx"
)
# Fallback : ancien nom avec année si besoin
PLANNING_BENEVOLES_SRC_LEGACY = normalize(
    ASF_ONEDRIVE / "Planning Bénévoles" / "Planning BENEVOLE 2025.xlsx"
)
VOLS_SRC = normalize(
    ASF_ONEDRIVE / "Planning MAB" / "Fichiers Source" / "aVols" / "Vols.xlsx"
)

# Chemins OneDrive (Graph) — relatifs à la racine OneDrive
TABLEAU_DE_BORD_REMOTE = os.getenv(
    "ASF_TDB_REMOTE_PATH",
    "Hélida/TABLEAU DE BORD.xlsx",
).strip()
PLANNING_BENEVOLES_REMOTE = os.getenv(
    "ASF_BENEV_REMOTE_PATH",
    "Planning Bénévoles/Planning BENEVOLE.xlsx",
).strip()
VOLS_REMOTE = os.getenv(
    "ASF_VOLS_REMOTE_PATH",
    "Planning MAB/Fichiers Source/aVols/Vols.xlsx",
).strip()
LISTES_COLISAGE_REMOTE_DIR = os.getenv(
    "ASF_LISTES_COLISAGE_REMOTE_DIR",
    "8-Listes de colisage",
).strip()
OUTPUT_PLANNING_REMOTE_DIR_TEMPLATE = os.getenv(
    "ASF_OUTPUT_REMOTE_DIR_TEMPLATE",
    "Planning MAB/ASFmm PLANNING {year}",
).strip()


# =============================================================================
# DOSSIER TMP (toujours recréé par prepare_paths)
# =============================================================================

TMP_DIR = normalize(os.getenv("ASF_TMP_DIR", BASE_DIR / ".tmp_asf"))
GRAPH_TOKEN_CACHE = normalize(os.getenv("ASF_GRAPH_TOKEN_CACHE", TMP_DIR / ".msal_cache.json"))


def _download_to_tmp(remote_path: str, dst_name: str) -> Path:
    """Télécharge un fichier Graph vers TMP (placeholder vide si manquant)."""
    dst = TMP_DIR / dst_name
    dst.parent.mkdir(parents=True, exist_ok=True)
    ok = False
    try:
        ok = download_onedrive_file(remote_path, dst, interactive=False)
    except Exception:
        ok = False
    if not ok:
        try:
            dst.touch()
        except Exception:
            pass
    return normalize(dst)


def _copy_to_tmp(src: Path, dst_name: str) -> Path:
    """Copie src → TMP/dst_name (placeholder vide si manquant)."""
    dst = TMP_DIR / dst_name
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        if src.exists():
            shutil.copy2(src, dst)
        else:
            dst.touch()
    except Exception:
        dst.touch()
    return normalize(dst)


# Valeurs actuelles des chemins utilisés par le moteur (seront mises à jour)
TABLEAU_DE_BORD = TMP_DIR / "TABLEAU_DE_BORD.xlsx"
PLANNING_BENEVOLES = TMP_DIR / "PLANNING_BENEVOLES.xlsx"
VOLS = TMP_DIR / "VOLS.xlsx"


# =============================================================================
# FEUILLES ATTENDUES
# =============================================================================

SHEET_MAG_CENTRAL = "MAG CENTRAL"
SHEET_PARAM_BE = "ParamBE"
SHEET_PARAM_DEST = "ParamDest"
SHEET_PARAM_EXP = "ParamExpediteur"
SHEET_PARAM_BENEV = "ParamBenev"
SHEET_BENEV_DISPO = "Disponibilités"
SHEET_VOLS = "Vols"

# =============================================================================
# MAG CENTRAL - COLONNES
# =============================================================================

MAG_CENTRAL_COL_DEPART_MAG = 10
MAG_CENTRAL_COL_DEPART_VOL = 12
MAG_CENTRAL_COL_ID_BENEV = 23  # Col W
MAG_CENTRAL_COL_BENEV = 24     # Col X
MAG_CENTRAL_COL_VOL = 25       # Col Y
MAG_CENTRAL_COL_HEURE = 26     # Col Z


# =============================================================================
# TEMPLATE PLANNING
# =============================================================================

PLANNING_TEMPLATE = normalize(BASE_DIR / "data_test" / "Planning_TEMPLATE.xlsx")
if not PLANNING_TEMPLATE.exists():
    alt = ASF_ONEDRIVE / "Planning MAB" / "Planning_TEMPLATE.xlsx"
    PLANNING_TEMPLATE = normalize(alt if alt.exists() else PLANNING_TEMPLATE)

# Maquette OneDrive (aaSOURCE)
PLANNING_MAQUETTE_ONEDRIVE = normalize(
    ASF_ONEDRIVE
    / "Planning MAB"
    / "ASFmm PLANNING 2025"
    / "aaSOURCE"
    / "Planning-maquette.xlsx"
)


# =============================================================================
# SORTIES
# =============================================================================

OUTPUT_PLANNING_DIR = normalize(
    os.getenv(
        "ASF_OUTPUT_DIR",
        ASF_ONEDRIVE / "Planning MAB" / "ASFmm PLANNING 2025" / "Resultat",
    )
)
OUTPUT_PLANNING = OUTPUT_PLANNING_DIR / "Planning.xlsx"
OUTPUT_BILAN = OUTPUT_PLANNING_DIR / "Bilan.xlsx"


# =============================================================================
# HELPERS PLANNING
# =============================================================================

def get_planning_dirs(year: int | None = None):
    """
    Retourne une liste de dossiers où chercher les plannings :
      - Planning MAB
      - Planning MAB/ASFmm PLANNING <année> (si existe)
      - OUTPUT_PLANNING_DIR
    """
    dirs = []
    base_root = detect_onedrive_asf()
    planning_mab = normalize(base_root / "Planning MAB")
    if planning_mab.exists():
        dirs.append(planning_mab)
        # Parcours des sous-dossiers ASFmm PLANNING *
        pattern = "ASFmm PLANNING *"
        for d in planning_mab.glob(pattern):
            if d.is_dir():
                dirs.append(normalize(d))
        # Année explicitement demandée
        if year:
            cand = planning_mab / f"ASFmm PLANNING {year}"
            if cand.exists():
                dirs.insert(0, normalize(cand))
    # Fallback sortie
    dirs.append(OUTPUT_PLANNING_DIR)
    # Dédupliquer en conservant l'ordre
    seen = set()
    unique = []
    for d in dirs:
        if d not in seen:
            seen.add(d)
            unique.append(d)
    return unique


def get_planning_maquette_path() -> Path:
    """
    Retourne le chemin de la maquette prioritaire OneDrive si présente,
    sinon la maquette locale.
    """
    if PLANNING_MAQUETTE_ONEDRIVE.exists():
        return PLANNING_MAQUETTE_ONEDRIVE
    return PLANNING_TEMPLATE


# =============================================================================
# UTILITAIRES
# =============================================================================

def prepare_paths(copy_sources: bool = True) -> None:
    """
    Crée le TMP local et copie les 3 sources OneDrive dedans.
    Met à jour les chemins globaux TABLEAU_DE_BORD / PLANNING_BENEVOLES / VOLS.
    """
    global TABLEAU_DE_BORD, PLANNING_BENEVOLES, VOLS, TMP_DIR, ASF_ONEDRIVE
    global OUTPUT_PLANNING_DIR, OUTPUT_PLANNING, OUTPUT_BILAN, GRAPH_TOKEN_CACHE
    global TABLEAU_DE_BORD_SRC, PLANNING_BENEVOLES_SRC, PLANNING_BENEVOLES_SRC_LEGACY, VOLS_SRC

    # Prend en compte un override ENV dynamique (utile en tests)
    env_tmp = os.getenv("ASF_TMP_DIR")
    if env_tmp:
        TMP_DIR = normalize(env_tmp)
        GRAPH_TOKEN_CACHE = normalize(os.getenv("ASF_GRAPH_TOKEN_CACHE", TMP_DIR / ".msal_cache.json"))
    env_root = os.getenv("ASF_ONEDRIVE_ROOT")
    if env_root:
        ASF_ONEDRIVE = normalize(env_root)
        TABLEAU_DE_BORD_SRC = normalize(ASF_ONEDRIVE / "Hélida" / "TABLEAU DE BORD.xlsx")
        PLANNING_BENEVOLES_SRC = normalize(
            ASF_ONEDRIVE / "Planning Bénévoles" / "Planning BENEVOLE.xlsx"
        )
        PLANNING_BENEVOLES_SRC_LEGACY = normalize(
            ASF_ONEDRIVE / "Planning Bénévoles" / "Planning BENEVOLE 2025.xlsx"
        )
        VOLS_SRC = normalize(
            ASF_ONEDRIVE / "Planning MAB" / "Fichiers Source" / "aVols" / "Vols.xlsx"
        )

    TABLEAU_DE_BORD = normalize(TMP_DIR / "TABLEAU_DE_BORD.xlsx")
    PLANNING_BENEVOLES = normalize(TMP_DIR / "PLANNING_BENEVOLES.xlsx")
    VOLS = normalize(TMP_DIR / "VOLS.xlsx")

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    if USE_GRAPH_ONEDRIVE:
        OUTPUT_PLANNING_DIR = normalize(os.getenv("ASF_OUTPUT_DIR", TMP_DIR / "output"))
        OUTPUT_PLANNING = OUTPUT_PLANNING_DIR / "Planning.xlsx"
        OUTPUT_BILAN = OUTPUT_PLANNING_DIR / "Bilan.xlsx"
    OUTPUT_PLANNING_DIR.mkdir(parents=True, exist_ok=True)

    effective_copy = copy_sources and (USE_GRAPH_ONEDRIVE or not IS_STREAMLIT_CLOUD)

    if effective_copy:
        if USE_GRAPH_ONEDRIVE:
            TABLEAU_DE_BORD = _download_to_tmp(TABLEAU_DE_BORD_REMOTE, "TABLEAU_DE_BORD.xlsx")
            PLANNING_BENEVOLES = _download_to_tmp(PLANNING_BENEVOLES_REMOTE, "PLANNING_BENEVOLES.xlsx")
            VOLS = _download_to_tmp(VOLS_REMOTE, "VOLS.xlsx")
            TABLEAU_DE_BORD_SRC = TABLEAU_DE_BORD
            PLANNING_BENEVOLES_SRC = PLANNING_BENEVOLES
            VOLS_SRC = VOLS
        else:
            bene_src = PLANNING_BENEVOLES_SRC if PLANNING_BENEVOLES_SRC.exists() else PLANNING_BENEVOLES_SRC_LEGACY
            TABLEAU_DE_BORD = _copy_to_tmp(TABLEAU_DE_BORD_SRC, "TABLEAU_DE_BORD.xlsx")
            PLANNING_BENEVOLES = _copy_to_tmp(bene_src, "PLANNING_BENEVOLES.xlsx")
            VOLS = _copy_to_tmp(VOLS_SRC, "VOLS.xlsx")
    else:
        # On ne copie pas mais on s'assure que les fichiers existent au moins vides
        for dst in [TABLEAU_DE_BORD, PLANNING_BENEVOLES, VOLS]:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.touch(exist_ok=True)


def cleanup_tmp() -> None:
    """Vide totalement le dossier TMP."""
    if not TMP_DIR.exists():
        return
    for item in TMP_DIR.iterdir():
        try:
            if item.is_file() or item.is_symlink():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
        except Exception:
            pass


def print_config_paths() -> None:
    print("\n=== CONFIG PATHS ===")
    print(f"ASF_ONEDRIVE            : {ASF_ONEDRIVE}")
    print(f"TABLEAU_DE_BORD_SRC     : {TABLEAU_DE_BORD_SRC}")
    print(f"PLANNING_BENEVOLES_SRC  : {PLANNING_BENEVOLES_SRC}")
    print(f"PLANNING_BENEVOLES_SRC_LEGACY: {PLANNING_BENEVOLES_SRC_LEGACY}")
    print(f"VOLS_SRC                : {VOLS_SRC}")
    print(f"TMP_DIR                 : {TMP_DIR}")
    print(f"OUTPUT_PLANNING_DIR     : {OUTPUT_PLANNING_DIR}")
    print(f"TABLEAU_DE_BORD (TMP)   : {TABLEAU_DE_BORD}")
    print(f"PLANNING_BENEVOLES (TMP): {PLANNING_BENEVOLES}")
    print(f"VOLS (TMP)              : {VOLS}")
    print("=====================\n")


def ensure_tmp_up_to_date() -> None:
    """
    Fallback pour l'UI : regénère les copies si elles n'existent pas.
    """
    if (
        not TABLEAU_DE_BORD.exists()
        or not PLANNING_BENEVOLES.exists()
        or not VOLS.exists()
    ):
        prepare_paths(copy_sources=True)


# =============================================================================
# ONEDRIVE GRAPH HELPERS
# =============================================================================

_GRAPH_CLIENT = None


def is_graph_onedrive() -> bool:
    return USE_GRAPH_ONEDRIVE


def get_output_remote_dir(year: int) -> str:
    return OUTPUT_PLANNING_REMOTE_DIR_TEMPLATE.format(year=year)


def get_output_remote_path(year: int, filename: str) -> str:
    return f"{get_output_remote_dir(year).strip('/')}/{filename}"


def _build_graph_client():
    if not (GRAPH_CLIENT_ID and GRAPH_TENANT_ID):
        return None
    from scheduler.onedrive_graph import GraphConfig, OneDriveGraphClient

    cfg = GraphConfig(
        tenant_id=GRAPH_TENANT_ID,
        client_id=GRAPH_CLIENT_ID,
        scopes=GRAPH_SCOPES,
        token_cache_path=GRAPH_TOKEN_CACHE,
    )
    return OneDriveGraphClient(cfg)


def get_graph_client():
    global _GRAPH_CLIENT
    if _GRAPH_CLIENT is None:
        _GRAPH_CLIENT = _build_graph_client()
    return _GRAPH_CLIENT


def begin_onedrive_device_flow() -> dict | None:
    client = get_graph_client()
    if client is None:
        return None
    return client.begin_device_flow()


def complete_onedrive_device_flow(flow: dict) -> bool:
    client = get_graph_client()
    if client is None:
        return False
    client.complete_device_flow(flow)
    return True


def download_onedrive_file(remote_path: str, local_path: Path, *, interactive: bool = False) -> bool:
    if not USE_GRAPH_ONEDRIVE:
        return False
    client = get_graph_client()
    if client is None:
        return False
    from scheduler.onedrive_graph import GraphAuthRequired

    try:
        return client.download_file(remote_path, Path(local_path), interactive=interactive)
    except GraphAuthRequired:
        return False


def upload_onedrive_file(
    local_path: Path,
    remote_path: str,
    *,
    interactive: bool = False,
    conflict_behavior: str = "replace",
) -> bool:
    if not USE_GRAPH_ONEDRIVE:
        return False
    client = get_graph_client()
    if client is None:
        return False
    from scheduler.onedrive_graph import GraphAuthRequired

    try:
        return client.upload_file(
            Path(local_path),
            remote_path,
            interactive=interactive,
            conflict_behavior=conflict_behavior,
        )
    except GraphAuthRequired:
        return False


def list_onedrive_files(
    remote_dir: str,
    *,
    recursive: bool = False,
    suffixes: list[str] | None = None,
    interactive: bool = False,
) -> list[dict]:
    if not USE_GRAPH_ONEDRIVE:
        return []
    client = get_graph_client()
    if client is None:
        return []
    from scheduler.onedrive_graph import GraphAuthRequired

    try:
        if recursive:
            return client.list_files_recursive(remote_dir, interactive=interactive, suffixes=suffixes)
        items = client.list_children(remote_dir, interactive=interactive)
        prefix = remote_dir.strip("/")
        for item in items:
            name = item.get("name", "")
            item["path"] = f"{prefix}/{name}".strip("/")
        return items
    except GraphAuthRequired:
        return []


def remote_path_for_local(local_path: Path) -> str | None:
    local_path = Path(local_path).resolve()
    if local_path == Path(TABLEAU_DE_BORD).resolve():
        return TABLEAU_DE_BORD_REMOTE
    if local_path == Path(PLANNING_BENEVOLES).resolve():
        return PLANNING_BENEVOLES_REMOTE
    if local_path == Path(VOLS).resolve():
        return VOLS_REMOTE
    return None


def sync_local_file_to_onedrive(
    local_path: Path,
    *,
    remote_path: str | None = None,
    conflict_behavior: str = "replace",
) -> bool:
    if not USE_GRAPH_ONEDRIVE:
        return False
    remote_path = remote_path or remote_path_for_local(local_path)
    if not remote_path:
        return False
    return upload_onedrive_file(local_path, remote_path, conflict_behavior=conflict_behavior)
