"""Launcher to run the Streamlit app inside PyInstaller onefile builds."""
import os
import sys
import webbrowser
from pathlib import Path
from streamlit.web import cli as stcli


def _app_path() -> Path:
    # In a PyInstaller bundle, sources are unpacked into sys._MEIPASS.
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "app.py"  # type: ignore[attr-defined]
    return Path(__file__).parent / "app.py"


if __name__ == "__main__":
    app_file = _app_path()
    base_dir = app_file.parent
    # Ensure bundled modules are importable by Streamlit (PyInstaller onefile).
    sys.path.insert(0, str(base_dir))
    os.chdir(base_dir)

    port = os.environ.get("ASF_APP_PORT", "8501")
    url = f"http://localhost:{port}"
    # Headless mode avoids UI issues in onefile; we open the browser ourselves.
    sys.argv = [
        "streamlit",
        "run",
        str(app_file),
        "--server.headless=true",
        f"--server.port={port}",
        "--browser.serverAddress=localhost",
        f"--browser.serverPort={port}",
        "--global.developmentMode=false",
    ]
    try:
        webbrowser.open(url)
    except Exception:
        pass
    sys.exit(stcli.main())
