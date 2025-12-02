# asf_app/ui/loader.py
# -----------------------------------------------------------
# Loader centralisé pour ParamDest / ParamExp / ParamBenev / ParamBE
# Utilisé par :
#   - ui_planning
#   - ui_communication
#
# Version 3.1 — compatible OneDrive TMP + universal_loader
# -----------------------------------------------------------

import pandas as pd

from scheduler.config_paths import (
    TABLEAU_DE_BORD,
    PLANNING_BENEVOLES,
    SHEET_PARAM_DEST,
    SHEET_PARAM_EXP,
    SHEET_PARAM_BENEV,
    SHEET_PARAM_BE,
)

from scheduler.column_map import (
    column_map_param_dest,
    column_map_param_expediteur,
    column_map_param_benev,
    column_map_param_be,
)

from loaders.universal_loader import load_and_normalize


# ============================================================
# LOAD PARAMETERS
# ============================================================
def load_parameters():
    """
    Charge tous les paramètres utilisés pour Planning + Communication :
    
    - ParamDest        (Destination, IATA, Contact, Téléphones…)
    - ParamExpéditeur  (association, email, copie…)
    - ParamBenev       (ID, prénom, nom, tel, limites…)
    - ParamBE          (équivalences HF, priorités…)

    Retourne dans cet ordre :
        df_paramdest, df_paramexpediteur, df_parambenev, df_parambe
    """

    # Param DESTINATION
    df_paramdest = load_and_normalize(
        path=TABLEAU_DE_BORD,
        sheet_name=SHEET_PARAM_DEST,
        mapping=column_map_param_dest
    )

    # Param EXPÉDITEUR
    df_paramexpediteur = load_and_normalize(
        path=TABLEAU_DE_BORD,
        sheet_name=SHEET_PARAM_EXP,
        mapping=column_map_param_expediteur
    )

    # Param BÉNÉVOLES
    df_parambenev = load_and_normalize(
        path=PLANNING_BENEVOLES,
        sheet_name=SHEET_PARAM_BENEV,
        mapping=column_map_param_benev
    )

    # Param BE
    df_parambe = load_and_normalize(
        path=TABLEAU_DE_BORD,
        sheet_name=SHEET_PARAM_BE,
        mapping=column_map_param_be
    )

    return df_paramdest, df_paramexpediteur, df_parambenev, df_parambe
