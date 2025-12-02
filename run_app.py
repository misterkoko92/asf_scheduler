"""Launcher to run the Streamlit app inside PyInstaller onefile builds."""
import sys
from streamlit.web import cli as stcli


if __name__ == "__main__":
    # Mimic `streamlit run app.py` so Streamlit initializes its context properly.
    sys.argv = ["streamlit", "run", "app.py", "--server.headless=true"]
    sys.exit(stcli.main())
