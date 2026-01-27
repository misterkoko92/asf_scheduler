import logging
from pathlib import Path
import scheduler.config_paths as cp
from asf_app.config.runtime import get_tmp_dir


def get_logger(
    name: str,
    *,
    log_path: Path | None = None,
    level: int = logging.INFO,
    console: bool = False,
) -> logging.Logger:
    """
    Crée/récupère un logger avec un FileHandler (et optionnellement un StreamHandler).
    Le fichier par défaut est <tmp_dir> / f"{name}.log" (session si dispo).
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if log_path is None:
        log_path = get_tmp_dir() / f"{name}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # File handler unique
    has_file_handler = any(
        isinstance(h, logging.FileHandler) and Path(getattr(h, "baseFilename", "")) == log_path
        for h in logger.handlers
    )
    if not has_file_handler:
        fh = logging.FileHandler(log_path, mode="a", encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(fh)

    # Console handler optionnel
    if console:
        has_console = any(isinstance(h, logging.StreamHandler) for h in logger.handlers)
        if not has_console:
            ch = logging.StreamHandler()
            ch.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
            logger.addHandler(ch)

    logger.propagate = False
    return logger
