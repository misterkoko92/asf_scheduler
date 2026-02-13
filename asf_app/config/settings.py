# asf_app/config/settings.py
# -*- coding: utf-8 -*-
import datetime
from pathlib import Path

import yaml

import scheduler.config as engine_cfg

CONFIG_YAML = Path(__file__).parent / "config_defaults.yml"


# ============================================================================
#   HELPERS
# ============================================================================
def _coerce_int(val, default=None):
    """Convertit proprement vers int, sinon renvoie default."""
    try:
        if val is None or val == "":
            return default
        return int(val)
    except (TypeError, ValueError, OverflowError):
        return default


def _coerce_optional_int(val):
    """"" -> None, " " -> None, nombre -> int"""
    if val in ("", None):
        return None
    try:
        return int(val)
    except (TypeError, ValueError, OverflowError):
        return None


def _coerce_time(val: str, default: datetime.time) -> datetime.time:
    if not isinstance(val, str):
        return default
    try:
        h, m = map(int, val.split(":"))
        return datetime.time(h, m)
    except (TypeError, ValueError):
        return default


# ============================================================================
#   SETTINGS : façade UI ↔ moteur
# ============================================================================
class Settings:
    """
    Façade de configuration utilisée par l’UI pour manipuler les paramètres
    du moteur (scheduler.config). Les setters écrivent directement dans le moteur.
    """

    # ----------------------------------------------------------------------
    #   YAML : chargement
    # ----------------------------------------------------------------------
    def load_from_yaml(self):
        """Charge config_defaults.yml → injecte dans scheduler.config."""
        if not CONFIG_YAML.exists():
            return

        with open(CONFIG_YAML, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        # RÈGLES BE
        self.max_be_per_flight = _coerce_int(
            data.get("MAX_BE_PER_FLIGHT"),
            default=engine_cfg.MAX_BE_PER_FLIGHT
        )

        self.max_equiv_per_volunteer = _coerce_int(
            data.get("MAX_EQUIV_PER_VOLUNTEER"),
            default=engine_cfg.MAX_EQUIV_PER_VOLUNTEER
        )

        # RÈGLES BÉNÉVOLE
        self.duree_mission_heures = _coerce_int(
            data.get("DUREE_MISSION_HEURES"),
            default=engine_cfg.DUREE_MISSION_HEURES
        )

        self.max_benev_per_vol = _coerce_optional_int(
            data.get("MAX_BENEV_PER_VOL")
        )

        # RÈGLE VOL / HEURE PAR DÉFAUT
        self.default_flight_time = _coerce_time(
            data.get("DEFAULT_FLIGHT_TIME", ""),
            engine_cfg.DEFAULT_FLIGHT_TIME
        )

        # Capacités
        self.max_capacite_par_vol = _coerce_optional_int(
            data.get("MAX_CAPACITE_PAR_VOL")
        )

    # ----------------------------------------------------------------------
    #   YAML : sauvegarde
    # ----------------------------------------------------------------------
    def save_to_yaml(self):
        data = {
            "MAX_BE_PER_FLIGHT": self.max_be_per_flight,
            "MAX_EQUIV_PER_VOLUNTEER": self.max_equiv_per_volunteer,
            "DUREE_MISSION_HEURES": self.duree_mission_heures,
            "MAX_BENEV_PER_VOL": self.max_benev_per_vol,
            "DEFAULT_FLIGHT_TIME": self.default_flight_time.strftime("%H:%M"),
            "MAX_CAPACITE_PAR_VOL": self.max_capacite_par_vol,
        }

        with open(CONFIG_YAML, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True)

    # ----------------------------------------------------------------------
    #   RESET GLOBAL (remet le moteur à zéro)
    # ----------------------------------------------------------------------
    def reset_to_defaults(self):
        """Reset complet aux valeurs natives du moteur (scheduler.config)."""
        self.max_be_per_flight = engine_cfg.MAX_BE_PER_FLIGHT
        self.max_equiv_per_volunteer = engine_cfg.MAX_EQUIV_PER_VOLUNTEER

        self.duree_mission_heures = engine_cfg.DUREE_MISSION_HEURES
        self.max_benev_per_vol = engine_cfg.MAX_BENEV_PER_VOL

        self.default_flight_time = engine_cfg.DEFAULT_FLIGHT_TIME
        self.max_capacite_par_vol = engine_cfg.MAX_CAPACITE_PAR_VOL

    # ============================================================================
    #   PROPRIÉTÉS (accès live au moteur)
    # ============================================================================

    # ---- BE ----
    @property
    def max_be_per_flight(self) -> int:
        return int(engine_cfg.MAX_BE_PER_FLIGHT)

    @max_be_per_flight.setter
    def max_be_per_flight(self, value: int) -> None:
        engine_cfg.MAX_BE_PER_FLIGHT = _coerce_int(value, default=1)

    @property
    def max_equiv_per_volunteer(self) -> int:
        return int(engine_cfg.MAX_EQUIV_PER_VOLUNTEER)

    @max_equiv_per_volunteer.setter
    def max_equiv_per_volunteer(self, value: int) -> None:
        engine_cfg.MAX_EQUIV_PER_VOLUNTEER = _coerce_int(value, default=1)

    # ---- BÉNÉVOLES ----
    @property
    def duree_mission_heures(self) -> int:
        return int(engine_cfg.DUREE_MISSION_HEURES)

    @duree_mission_heures.setter
    def duree_mission_heures(self, value: int) -> None:
        engine_cfg.DUREE_MISSION_HEURES = _coerce_int(value, default=1)

    @property
    def max_benev_per_vol(self):
        return engine_cfg.MAX_BENEV_PER_VOL

    @max_benev_per_vol.setter
    def max_benev_per_vol(self, value):
        engine_cfg.MAX_BENEV_PER_VOL = _coerce_optional_int(value)

    # ---- VOLS / RÈGLES TEMPORELLES ----
    @property
    def default_flight_time(self) -> datetime.time:
        return engine_cfg.DEFAULT_FLIGHT_TIME

    @default_flight_time.setter
    def default_flight_time(self, value: datetime.time) -> None:
        if isinstance(value, datetime.time):
            engine_cfg.DEFAULT_FLIGHT_TIME = value

    @property
    def max_capacite_par_vol(self):
        return engine_cfg.MAX_CAPACITE_PAR_VOL

    @max_capacite_par_vol.setter
    def max_capacite_par_vol(self, value):
        engine_cfg.MAX_CAPACITE_PAR_VOL = _coerce_optional_int(value)

    # ============================================================================
    #   UTILITAIRE DEBUG
    # ============================================================================
    def to_dict(self):
        """Retourne tous les paramètres (pour affichage UI / debug)."""
        return {
            "MAX_BE_PER_FLIGHT": self.max_be_per_flight,
            "MAX_EQUIV_PER_VOLUNTEER": self.max_equiv_per_volunteer,
            "DUREE_MISSION_HEURES": self.duree_mission_heures,
            "MAX_BENEV_PER_VOL": self.max_benev_per_vol,
            "DEFAULT_FLIGHT_TIME": self.default_flight_time.strftime("%H:%M"),
            "MAX_CAPACITE_PAR_VOL": self.max_capacite_par_vol,
        }


# Instance global utilisée dans l’UI
settings = Settings()
