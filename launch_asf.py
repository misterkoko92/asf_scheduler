"""
Launcher minimal pour ASF Scheduler avec Streamlit.

Usage (depuis le venv) :
    python launch_asf.py

PyInstaller pourra empaqueter ce fichier (avec --add-data pour le code).
"""

from pathlib import Path
import sys
import os
import traceback
import threading
import time
import webbrowser


def main():
    # Support PyInstaller: sys._MEIPASS = répertoire temporaire d'extraction
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    repo = Path(__file__).resolve().parent

    # Localisation d'app.py
    candidates = [
        base / "app.py",
        repo / "app.py",
        Path.cwd() / "app.py",
    ]
    app_path = None
    for c in candidates:
        if c.exists():
            app_path = c
            break

    if app_path is None:
        print("Impossible de trouver app.py")
        input("Appuyez sur Entrée pour fermer.")
        return

    # Paramètres Streamlit par défaut (headless, port, CORS)
    # Nom d'env correct : STREAMLIT_GLOBAL_DEVELOPMENT_MODE (sinon le port est ignoré)
    os.environ["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"
    # Pas de port imposé : Streamlit choisira un port libre
    os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"
    os.environ["STREAMLIT_BROWSER_SERVER_ADDRESS"] = os.environ.get("STREAMLIT_BROWSER_SERVER_ADDRESS", "localhost")
    os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    # Pour éviter le warning CORS/XSRF : on aligne les deux
    os.environ["STREAMLIT_SERVER_ENABLE_CORS"] = "true"
    os.environ["STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION"] = "false"

    # Exécution streamlit dans le même processus pour garder les logs
    try:
        from streamlit.web import cli as stcli

        # Ouvrir automatiquement le navigateur après un léger délai
        def _open_browser():
            # On attend un peu et on ouvre la dernière URL connue (Streamlit affiche son URL dans la console)
            time.sleep(3)
            # Port non fixé : on tente le dernier port affiché par Streamlit (fallback 8501)
            port = os.environ.get("STREAMLIT_SERVER_PORT", "8501")
            url = f"http://localhost:{port}"
            webbrowser.open(url)

        threading.Thread(target=_open_browser, daemon=True).start()

        sys.argv = ["streamlit", "run", str(app_path)]
        # Forcer cwd sur base pour les chemins relatifs
        os.chdir(base)
        stcli.main()
    except Exception:
        traceback.print_exc()
        input("Erreur lors du lancement. Appuyez sur Entrée pour fermer.")


if __name__ == "__main__":
    main()
