# scheduler/config_paths.py
# -*- coding: utf-8 -*-

from __future__ import annotations

import glob
import logging
import os
import shutil
import unicodedata
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("ASF-SCHEDULER")

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

CONFIG_PATH_IO_ERRORS = (
    FileNotFoundError,
    OSError,
    PermissionError,
    RuntimeError,
    TypeError,
    ValueError,
    AttributeError,
    ImportError,
)
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
            matches = list(glob.glob(str(cloud / pat)))
            for match_path in matches:
                name = unicodedata.normalize("NFC", Path(match_path).name)
                if "OneDrive" in name:
                    return normalize(match_path)

    # 2) Windows / macOS OneDrive classique
    local_candidates = [
        home / "OneDrive - Aviation Sans Frontières",
        home / "OneDrive - AviationSansFrontières",
        home / "OneDrive",
    ]
    for candidate_path in local_candidates:
        if candidate_path.exists():
            return normalize(candidate_path)

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


def _download_to_tmp(
    remote_path: str,
    dst_name: str,
    *,
    strict: bool = False,
    runtime: RuntimePaths | None = None,
) -> Path:
    """Télécharge un fichier Graph vers TMP (placeholder vide si manquant)."""
    runtime_paths = runtime or get_runtime_paths()
    dst = runtime_paths.tmp_dir / dst_name
    dst.parent.mkdir(parents=True, exist_ok=True)
    ok = False
    try:
        ok = download_onedrive_file(
            remote_path,
            dst,
            interactive=False,
            runtime=runtime_paths,
        )
    except CONFIG_PATH_IO_ERRORS:
        ok = False
    if not ok:
        msg = f"OneDrive Graph: fichier introuvable ou téléchargement échoué ({remote_path})"
        logger.error(msg)
        if strict:
            raise FileNotFoundError(msg)
        try:
            dst.touch()
        except (FileNotFoundError, OSError, PermissionError):
            pass
    return normalize(dst)


def _copy_to_tmp(
    src: Path,
    dst_name: str,
    *,
    strict: bool = False,
    runtime: RuntimePaths | None = None,
) -> Path:
    """Copie src → TMP/dst_name (placeholder vide si manquant)."""
    runtime_paths = runtime or get_runtime_paths()
    dst = runtime_paths.tmp_dir / dst_name
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        if src.exists():
            shutil.copy2(src, dst)
        else:
            msg = f"Source introuvable: {src}"
            logger.error(msg)
            if strict:
                raise FileNotFoundError(msg)
            dst.touch()
    except CONFIG_PATH_IO_ERRORS:
        msg = f"Erreur copie source: {src}"
        logger.error(msg)
        if strict:
            raise
        try:
            dst.touch()
        except (FileNotFoundError, OSError, PermissionError):
            pass
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
# RUNTIME SNAPSHOT (IMMUTABLE)
# =============================================================================

@dataclass(frozen=True)
class RuntimePaths:
    asf_onedrive: Path
    tableau_de_bord_src: Path
    planning_benevoles_src: Path
    planning_benevoles_src_legacy: Path
    vols_src: Path
    tmp_dir: Path
    tableau_de_bord: Path
    planning_benevoles: Path
    vols: Path
    output_planning_dir: Path
    output_planning: Path
    output_bilan: Path
    planning_template: Path
    planning_maquette_onedrive: Path
    tableau_de_bord_remote: str
    planning_benevoles_remote: str
    vols_remote: str
    output_planning_remote_dir_template: str
    listes_colisage_remote_dir: str = ""
    use_graph_onedrive: bool = False
    is_streamlit_cloud: bool = False
    graph_client_id: str = ""
    graph_tenant_id: str = ""
    graph_scopes: tuple[str, ...] = ()
    graph_token_cache: Path = Path(".")


def get_runtime_paths() -> RuntimePaths:
    """Retourne un snapshot immuable des chemins runtime actuels."""
    return RuntimePaths(
        asf_onedrive=Path(ASF_ONEDRIVE),
        tableau_de_bord_src=Path(TABLEAU_DE_BORD_SRC),
        planning_benevoles_src=Path(PLANNING_BENEVOLES_SRC),
        planning_benevoles_src_legacy=Path(PLANNING_BENEVOLES_SRC_LEGACY),
        vols_src=Path(VOLS_SRC),
        tmp_dir=Path(TMP_DIR),
        tableau_de_bord=Path(TABLEAU_DE_BORD),
        planning_benevoles=Path(PLANNING_BENEVOLES),
        vols=Path(VOLS),
        output_planning_dir=Path(OUTPUT_PLANNING_DIR),
        output_planning=Path(OUTPUT_PLANNING),
        output_bilan=Path(OUTPUT_BILAN),
        planning_template=Path(PLANNING_TEMPLATE),
        planning_maquette_onedrive=Path(PLANNING_MAQUETTE_ONEDRIVE),
        tableau_de_bord_remote=str(TABLEAU_DE_BORD_REMOTE),
        planning_benevoles_remote=str(PLANNING_BENEVOLES_REMOTE),
        vols_remote=str(VOLS_REMOTE),
        output_planning_remote_dir_template=str(OUTPUT_PLANNING_REMOTE_DIR_TEMPLATE),
        listes_colisage_remote_dir=str(LISTES_COLISAGE_REMOTE_DIR),
        use_graph_onedrive=bool(USE_GRAPH_ONEDRIVE),
        is_streamlit_cloud=bool(IS_STREAMLIT_CLOUD),
        graph_client_id=str(GRAPH_CLIENT_ID),
        graph_tenant_id=str(GRAPH_TENANT_ID),
        graph_scopes=tuple(GRAPH_SCOPES),
        graph_token_cache=Path(GRAPH_TOKEN_CACHE),
    )


# =============================================================================
# HELPERS PLANNING
# =============================================================================

def get_planning_dirs(year: int | None = None, *, runtime: RuntimePaths | None = None):
    """
    Retourne une liste de dossiers où chercher les plannings :
      - Planning MAB
      - Planning MAB/ASFmm PLANNING <année> (si existe)
      - OUTPUT_PLANNING_DIR
    """
    runtime_paths = runtime or get_runtime_paths()
    dirs = []
    base_root = runtime_paths.asf_onedrive
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
    dirs.append(runtime_paths.output_planning_dir)
    # Dédupliquer en conservant l'ordre
    seen = set()
    unique = []
    for d in dirs:
        if d not in seen:
            seen.add(d)
            unique.append(d)
    return unique


def get_planning_maquette_path(*, runtime: RuntimePaths | None = None) -> Path:
    """
    Retourne le chemin de la maquette prioritaire OneDrive si présente,
    sinon la maquette locale.
    """
    runtime_paths = runtime or get_runtime_paths()
    if runtime_paths.planning_maquette_onedrive.exists():
        return runtime_paths.planning_maquette_onedrive
    return runtime_paths.planning_template


# =============================================================================
# UTILITAIRES
# =============================================================================

def _apply_runtime_paths_snapshot(runtime: RuntimePaths) -> None:
    """Projette un snapshot runtime dans les globals legacy (compatibilité)."""
    global TABLEAU_DE_BORD, PLANNING_BENEVOLES, VOLS, TMP_DIR, ASF_ONEDRIVE
    global OUTPUT_PLANNING_DIR, OUTPUT_PLANNING, OUTPUT_BILAN, GRAPH_TOKEN_CACHE
    global TABLEAU_DE_BORD_SRC, PLANNING_BENEVOLES_SRC, PLANNING_BENEVOLES_SRC_LEGACY, VOLS_SRC
    global TABLEAU_DE_BORD_REMOTE, PLANNING_BENEVOLES_REMOTE, VOLS_REMOTE
    global OUTPUT_PLANNING_REMOTE_DIR_TEMPLATE, LISTES_COLISAGE_REMOTE_DIR
    global USE_GRAPH_ONEDRIVE, IS_STREAMLIT_CLOUD
    global GRAPH_CLIENT_ID, GRAPH_TENANT_ID, GRAPH_SCOPES

    ASF_ONEDRIVE = normalize(runtime.asf_onedrive)
    TABLEAU_DE_BORD_SRC = normalize(runtime.tableau_de_bord_src)
    PLANNING_BENEVOLES_SRC = normalize(runtime.planning_benevoles_src)
    PLANNING_BENEVOLES_SRC_LEGACY = normalize(runtime.planning_benevoles_src_legacy)
    VOLS_SRC = normalize(runtime.vols_src)
    TMP_DIR = normalize(runtime.tmp_dir)
    TABLEAU_DE_BORD = normalize(runtime.tableau_de_bord)
    PLANNING_BENEVOLES = normalize(runtime.planning_benevoles)
    VOLS = normalize(runtime.vols)
    OUTPUT_PLANNING_DIR = normalize(runtime.output_planning_dir)
    OUTPUT_PLANNING = normalize(runtime.output_planning)
    OUTPUT_BILAN = normalize(runtime.output_bilan)
    GRAPH_TOKEN_CACHE = normalize(runtime.graph_token_cache)
    TABLEAU_DE_BORD_REMOTE = str(runtime.tableau_de_bord_remote)
    PLANNING_BENEVOLES_REMOTE = str(runtime.planning_benevoles_remote)
    VOLS_REMOTE = str(runtime.vols_remote)
    OUTPUT_PLANNING_REMOTE_DIR_TEMPLATE = str(runtime.output_planning_remote_dir_template)
    LISTES_COLISAGE_REMOTE_DIR = str(runtime.listes_colisage_remote_dir)
    USE_GRAPH_ONEDRIVE = bool(runtime.use_graph_onedrive)
    IS_STREAMLIT_CLOUD = bool(runtime.is_streamlit_cloud)
    GRAPH_CLIENT_ID = str(runtime.graph_client_id).strip()
    GRAPH_TENANT_ID = str(runtime.graph_tenant_id).strip()
    GRAPH_SCOPES = [s for s in runtime.graph_scopes if str(s).strip()]
    if "_GRAPH_CLIENTS" in globals():
        _GRAPH_CLIENTS.clear()


def prepare_paths(
    copy_sources: bool = True,
    *,
    strict_sources: bool = False,
    runtime: RuntimePaths | None = None,
) -> RuntimePaths:
    """
    Crée le TMP local et copie les 3 sources OneDrive dedans.
    Met à jour les chemins globaux TABLEAU_DE_BORD / PLANNING_BENEVOLES / VOLS.
    """
    global TABLEAU_DE_BORD, PLANNING_BENEVOLES, VOLS, TMP_DIR, ASF_ONEDRIVE
    global OUTPUT_PLANNING_DIR, OUTPUT_PLANNING, OUTPUT_BILAN, GRAPH_TOKEN_CACHE
    global TABLEAU_DE_BORD_SRC, PLANNING_BENEVOLES_SRC, PLANNING_BENEVOLES_SRC_LEGACY, VOLS_SRC

    if runtime is not None:
        _apply_runtime_paths_snapshot(runtime)
    else:
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

    runtime_paths = get_runtime_paths()
    effective_copy = copy_sources and (
        runtime_paths.use_graph_onedrive or not runtime_paths.is_streamlit_cloud
    )

    if effective_copy:
        if runtime_paths.use_graph_onedrive:
            TABLEAU_DE_BORD = _download_to_tmp(
                runtime_paths.tableau_de_bord_remote,
                "TABLEAU_DE_BORD.xlsx",
                strict=strict_sources,
                runtime=runtime_paths,
            )
            PLANNING_BENEVOLES = _download_to_tmp(
                runtime_paths.planning_benevoles_remote,
                "PLANNING_BENEVOLES.xlsx",
                strict=strict_sources,
                runtime=runtime_paths,
            )
            VOLS = _download_to_tmp(
                runtime_paths.vols_remote,
                "VOLS.xlsx",
                strict=strict_sources,
                runtime=runtime_paths,
            )
            TABLEAU_DE_BORD_SRC = TABLEAU_DE_BORD
            PLANNING_BENEVOLES_SRC = PLANNING_BENEVOLES
            VOLS_SRC = VOLS
        else:
            bene_src = PLANNING_BENEVOLES_SRC if PLANNING_BENEVOLES_SRC.exists() else PLANNING_BENEVOLES_SRC_LEGACY
            TABLEAU_DE_BORD = _copy_to_tmp(
                TABLEAU_DE_BORD_SRC,
                "TABLEAU_DE_BORD.xlsx",
                strict=strict_sources,
                runtime=runtime_paths,
            )
            PLANNING_BENEVOLES = _copy_to_tmp(
                bene_src,
                "PLANNING_BENEVOLES.xlsx",
                strict=strict_sources,
                runtime=runtime_paths,
            )
            VOLS = _copy_to_tmp(
                VOLS_SRC,
                "VOLS.xlsx",
                strict=strict_sources,
                runtime=runtime_paths,
            )
    else:
        # On ne copie pas mais on s'assure que les fichiers existent au moins vides
        for dst in [TABLEAU_DE_BORD, PLANNING_BENEVOLES, VOLS]:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.touch(exist_ok=True)
    return get_runtime_paths()


def cleanup_tmp(*, runtime: RuntimePaths | None = None) -> None:
    """Vide totalement le dossier TMP."""
    runtime_paths = runtime or get_runtime_paths()
    tmp_dir = runtime_paths.tmp_dir
    if not tmp_dir.exists():
        return
    for item in tmp_dir.iterdir():
        try:
            if item.is_file() or item.is_symlink():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
        except (FileNotFoundError, OSError, PermissionError):
            pass


def print_config_paths(*, runtime: RuntimePaths | None = None) -> None:
    runtime_paths = runtime or get_runtime_paths()
    logger.info(
        "\n=== CONFIG PATHS ===\n"
        "ASF_ONEDRIVE            : %s\n"
        "TABLEAU_DE_BORD_SRC     : %s\n"
        "PLANNING_BENEVOLES_SRC  : %s\n"
        "PLANNING_BENEVOLES_SRC_LEGACY: %s\n"
        "VOLS_SRC                : %s\n"
        "TMP_DIR                 : %s\n"
        "OUTPUT_PLANNING_DIR     : %s\n"
        "TABLEAU_DE_BORD (TMP)   : %s\n"
        "PLANNING_BENEVOLES (TMP): %s\n"
        "VOLS (TMP)              : %s\n"
        "=====================",
        runtime_paths.asf_onedrive,
        runtime_paths.tableau_de_bord_src,
        runtime_paths.planning_benevoles_src,
        runtime_paths.planning_benevoles_src_legacy,
        runtime_paths.vols_src,
        runtime_paths.tmp_dir,
        runtime_paths.output_planning_dir,
        runtime_paths.tableau_de_bord,
        runtime_paths.planning_benevoles,
        runtime_paths.vols,
    )


def ensure_tmp_up_to_date(*, runtime: RuntimePaths | None = None) -> None:
    """
    Fallback pour l'UI : regénère les copies si elles n'existent pas.
    """
    runtime_paths = runtime or get_runtime_paths()
    if (
        not runtime_paths.tableau_de_bord.exists()
        or not runtime_paths.planning_benevoles.exists()
        or not runtime_paths.vols.exists()
    ):
        prepare_paths(copy_sources=True, runtime=runtime_paths)


# =============================================================================
# ONEDRIVE GRAPH HELPERS
# =============================================================================

_GRAPH_CLIENTS: dict[tuple[str, str, tuple[str, ...], str], object] = {}


def is_graph_onedrive() -> bool:
    return get_runtime_paths().use_graph_onedrive


def get_output_remote_dir(year: int, *, runtime: RuntimePaths | None = None) -> str:
    runtime_paths = runtime or get_runtime_paths()
    return runtime_paths.output_planning_remote_dir_template.format(year=year)


def get_output_remote_path(
    year: int,
    filename: str,
    *,
    runtime: RuntimePaths | None = None,
) -> str:
    return f"{get_output_remote_dir(year, runtime=runtime).strip('/')}/{filename}"


def _graph_client_cache_key(runtime: RuntimePaths) -> tuple[str, str, tuple[str, ...], str]:
    return (
        runtime.graph_tenant_id,
        runtime.graph_client_id,
        tuple(runtime.graph_scopes),
        str(runtime.graph_token_cache),
    )


def _build_graph_client(*, runtime: RuntimePaths | None = None):
    runtime_paths = runtime or get_runtime_paths()
    if not (runtime_paths.graph_client_id and runtime_paths.graph_tenant_id):
        return None
    from scheduler.onedrive_graph import GraphConfig, OneDriveGraphClient

    cfg = GraphConfig(
        tenant_id=runtime_paths.graph_tenant_id,
        client_id=runtime_paths.graph_client_id,
        scopes=list(runtime_paths.graph_scopes),
        token_cache_path=runtime_paths.graph_token_cache,
    )
    return OneDriveGraphClient(cfg)


def get_graph_client(*, runtime: RuntimePaths | None = None):
    runtime_paths = runtime or get_runtime_paths()
    key = _graph_client_cache_key(runtime_paths)
    if key not in _GRAPH_CLIENTS:
        _GRAPH_CLIENTS[key] = _build_graph_client(runtime=runtime_paths)
    return _GRAPH_CLIENTS[key]


def begin_onedrive_device_flow(*, runtime: RuntimePaths | None = None) -> dict | None:
    client = get_graph_client(runtime=runtime)
    if client is None:
        return None
    return client.begin_device_flow()


def complete_onedrive_device_flow(flow: dict, *, runtime: RuntimePaths | None = None) -> bool:
    client = get_graph_client(runtime=runtime)
    if client is None:
        return False
    client.complete_device_flow(flow)
    return True


def download_onedrive_file(
    remote_path: str,
    local_path: Path,
    *,
    interactive: bool = False,
    runtime: RuntimePaths | None = None,
) -> bool:
    runtime_paths = runtime or get_runtime_paths()
    if not runtime_paths.use_graph_onedrive:
        return False
    client = get_graph_client(runtime=runtime_paths)
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
    runtime: RuntimePaths | None = None,
) -> bool:
    runtime_paths = runtime or get_runtime_paths()
    if not runtime_paths.use_graph_onedrive:
        return False
    client = get_graph_client(runtime=runtime_paths)
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
    runtime: RuntimePaths | None = None,
) -> list[dict]:
    runtime_paths = runtime or get_runtime_paths()
    if not runtime_paths.use_graph_onedrive:
        return []
    client = get_graph_client(runtime=runtime_paths)
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


def remote_path_for_local(
    local_path: Path,
    *,
    runtime: RuntimePaths | None = None,
) -> str | None:
    runtime_paths = runtime or get_runtime_paths()
    local_path = Path(local_path).resolve()
    if local_path == Path(runtime_paths.tableau_de_bord).resolve():
        return runtime_paths.tableau_de_bord_remote
    if local_path == Path(runtime_paths.planning_benevoles).resolve():
        return runtime_paths.planning_benevoles_remote
    if local_path == Path(runtime_paths.vols).resolve():
        return runtime_paths.vols_remote
    return None


def sync_local_file_to_onedrive(
    local_path: Path,
    *,
    remote_path: str | None = None,
    conflict_behavior: str = "replace",
    runtime: RuntimePaths | None = None,
) -> bool:
    runtime_paths = runtime or get_runtime_paths()
    if not runtime_paths.use_graph_onedrive:
        return False
    remote_path = remote_path or remote_path_for_local(local_path, runtime=runtime_paths)
    if not remote_path:
        return False
    return upload_onedrive_file(
        local_path,
        remote_path,
        conflict_behavior=conflict_behavior,
        runtime=runtime_paths,
    )
