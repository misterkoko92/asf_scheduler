# scheduler/config.py
# -*- coding: utf-8 -*-
"""
Paramètres généraux du moteur de planification.
Aucun chemin d’accès ici : uniquement des règles métier.
"""

from datetime import time

# ============================================================================
#  RÈGLES BE
# ============================================================================

# Nombre maximum de BE (numéros distincts) affectables sur un même vol
MAX_BE_PER_FLIGHT = 5

# Charge équivalente maximale portées par un bénévole sur un vol
# Exemple : 22 = 22 équivalents = ~2 BE de 10 équiv chacun
MAX_EQUIV_PER_VOLUNTEER = 22


# ============================================================================
#  RÈGLES BÉNÉVOLES
# ============================================================================

# Durée de mission bénévole (heures avant l'heure de départ du vol)
DUREE_MISSION_HEURES = 3

# Limite ABSOLUE facultative de bénévoles par vol
# Laisser à None pour désactiver la limite.
MAX_BENEV_PER_VOL = None   # ex: 3 si un jour tu veux brider


# ============================================================================
#  RÈGLES VOL / SÉCURITÉ
# ============================================================================

# Heure par défaut si un vol n'a pas d'heure (rare)
DEFAULT_FLIGHT_TIME = time(0, 0)

# Capacité maximale par vol (fallback si ParamDest ne donne rien)
# Laisser None pour désactiver.
MAX_CAPACITE_PAR_VOL = None


# ============================================================================
#  FONCTIONS UTILITAIRES (DEBUG)
# ============================================================================

def get_config_summary() -> str:
    """Renvoie un résumé lisible de la configuration."""
    return (
        "=== CONFIGURATION PLANNING ===\n"
        f"• MAX_BE_PER_FLIGHT = {MAX_BE_PER_FLIGHT}\n"
        f"• MAX_EQUIV_PER_VOLUNTEER = {MAX_EQUIV_PER_VOLUNTEER}\n"
        f"• MAX_BENEV_PER_VOL = {MAX_BENEV_PER_VOL}\n"
        f"• DUREE_MISSION_HEURES = {DUREE_MISSION_HEURES}\n"
        f"• DEFAULT_FLIGHT_TIME = {DEFAULT_FLIGHT_TIME}\n"
        f"• MAX_CAPACITE_PAR_VOL = {MAX_CAPACITE_PAR_VOL}\n"
    )
