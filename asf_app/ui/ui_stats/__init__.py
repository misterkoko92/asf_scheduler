# ui_stats ne contient plus de rendu Streamlit.
# On expose uniquement les loaders.
from .ui_stats import filter_latest as filter_latest
from .ui_stats import load_planning_xlsx as load_planning_xlsx

__all__ = ["filter_latest", "load_planning_xlsx"]
