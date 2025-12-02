# launcher.py
# -*- coding: utf-8 -*-

"""
Lance Streamlit correctement en mode :
 - Développement normal (source)
 - Application packagée (.app PyInstaller sur macOS)
 - EXE PyInstaller Windows

Corrige :
 - chemins relatifs/absolus
 - working directory incorrect
 - app.py introuvable dans bundle
"""

import subprocess
import sys
import os
from pathlib import Path


def resolve_app_path() -> Path:
    """
    Détermine le bon emplacement de app.py selon le mode d'exécution :
      - mode développement → dossier courant
      - bundle PyInstaller → Contents/Resources/python
      - exe → dossier du binaire

    Retourne un Path absolu vers app.py.
    """

    # Cas 1 : exécution PyInstaller (Windows .exe OU macOS .app)
    if getattr(sys, "frozen", False):
        base_dir = Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else Path.cwd()

        # cas macOS .app → structure :
        # MyApp.app/Contents/MacOS/launcher
        # ressources Python : MyApp.app/Contents/Resources/python/
        mac_path = base_dir / "app.py"
        resources_path = base_dir / "python" / "app.py"

        if mac_path.exists():
            return mac_path.resolve()

        if resources_path.exists():
            return resources_path.resolve()

        # fallback : dossier de l'exécutable
        exe_path = Path(sys.executable).parent / "app.py"
        if exe_path.exists():
            return exe_path.resolve()

    # Cas 2 : mode développement → projet source
    here = Path(__file__).resolve().parent
    source_path = here / "app.py"
    if source_path.exists():
        return source_path

    raise FileNotFoundError("Impossible de localiser app.py – vérifie le bundle ou le dossier source.")


def run_streamlit():
    """
    Lance Streamlit en s'assurant du bon working directory.
    """

    app_path = resolve_app_path()
    base_dir = app_path.parent

    # Important : qe le working directory soit le répertoire de app.py
    os.chdir(base_dir)

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
    ]

    # Sur macOS .app → éviter d'ouvrir une console
    if sys.platform == "darwin" and getattr(sys, "frozen", False):
        subprocess.Popen(cmd)
        return

    # Windows / Dev → exécution standard
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    run_streamlit()
