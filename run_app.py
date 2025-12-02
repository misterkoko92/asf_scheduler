"""Launcher to run the Streamlit app inside PyInstaller onefile builds."""
import sys
from pathlib import Path
from streamlit.web import cli as stcli


def _app_path() -> Path:
    # In a PyInstaller bundle, sources are unpacked into sys._MEIPASS.
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "app.py"  # type: ignore[attr-defined]
    return Path(__file__).parent / "app.py"


if __name__ == "__main__":
    app_file = _app_path()
    sys.argv = ["streamlit", "run", str(app_file), "--server.headless=true"]
    sys.exit(stcli.main())
