# asf_app/ui/loader.py
# -----------------------------------------------------------
# Loader centralisé pour ParamDest / ParamExp / ParamBenev / ParamBE
# (délégué au service params_loader)
# -----------------------------------------------------------

from asf_app.services.params_loader import load_parameters

__all__ = ["load_parameters"]
