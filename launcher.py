# launcher.py
# -*- coding: utf-8 -*-

"""
Lance Streamlit à l'intérieur d'une application PyInstaller .app.

Utilise :
    python -m streamlit run app.py

Fonctionne pour :
 - développement normal
 - version packagée (PyInstaller .app)
"""

import subprocess
import sys
import os


def run_streamlit():
    # Dossier du script (bundle PyInstaller ou dossier normal)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)

    # Chemin du fichier principal Streamlit
    app_path = os.path.join(base_dir, "app.py")

    # Lancer : python -m streamlit run app.py
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", app_path],
        check=True
    )


if __name__ == "__main__":
    run_streamlit()
