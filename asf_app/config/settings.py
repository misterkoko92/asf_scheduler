# asf_app/config/settings.py
# -*- coding: utf-8 -*-
import datetime
import scheduler.config as engine_cfg

import yaml
from pathlib import Path

CONFIG_YAML = Path(__file__).parent / "config_defaults.yml"

class Settings:
    """Façade pour les paramètres du moteur (scheduler.config)."""

    # ======================================================
    # Chargement / sauvegarde YAML
    # ======================================================

    def load_from_yaml(self):
        """Charge les paramètres depuis config_defaults.yml."""
        if not CONFIG_YAML.exists():
            return  # Rien à charger

        with open(CONFIG_YAML, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        # Applique les valeurs
        self.max_be_per_flight = data.get("MAX_BE_PER_FLIGHT", engine_cfg.MAX_BE_PER_FLIGHT)
        self.max_equiv_per_volunteer = data.get("MAX_EQUIV_PER_VOLUNTEER", engine_cfg.MAX_EQUIV_PER_VOLUNTEER)

        self.duree_mission_heures = data.get("DUREE_MISSION_HEURES", engine_cfg.DUREE_MISSION_HEURES)
        self.max_benev_per_vol = data.get("MAX_BENEV_PER_VOL", engine_cfg.MAX_BENEV_PER_VOL)

        default_time = data.get("DEFAULT_FLIGHT_TIME", engine_cfg.DEFAULT_FLIGHT_TIME.strftime("%H:%M"))
        h, m = map(int, default_time.split(":"))
        self.default_flight_time = datetime.time(h, m)

        max_cap = data.get("MAX_CAPACITE_PAR_VOL", engine_cfg.MAX_CAPACITE_PAR_VOL)
        self.max_capacite_par_vol = max_cap

    def save_to_yaml(self):
        """Sauvegarde l'état actuel des paramètres dans config_defaults.yml."""
        data = {
            "MAX_BE_PER_FLIGHT": self.max_be_per_flight,
            "MAX_EQUIV_PER_VOLUNTEER": self.max_equiv_per_volunteer,
            "DUREE_MISSION_HEURES": self.duree_mission_heures,
            "MAX_BENEV_PER_VOL": self.max_benev_per_vol or "",
            "DEFAULT_FLIGHT_TIME": self.default_flight_time.strftime("%H:%M"),
            "MAX_CAPACITE_PAR_VOL": self.max_capacite_par_vol or "",
        }
        with open(CONFIG_YAML, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True)

    def reset_to_defaults(self):
        """Réinitialise aux valeurs de scheduler/config.py (valeurs 'officielles')."""
        self.max_be_per_flight = engine_cfg.MAX_BE_PER_FLIGHT
        self.max_equiv_per_volunteer = engine_cfg.MAX_EQUIV_PER_VOLUNTEER

        self.duree_mission_heures = engine_cfg.DUREE_MISSION_HEURES
        self.max_benev_per_vol = engine_cfg.MAX_BENEV_PER_VOL

        self.default_flight_time = engine_cfg.DEFAULT_FLIGHT_TIME
        self.max_capacite_par_vol = engine_cfg.MAX_CAPACITE_PAR_VOL

    # ------------------------------------------------------------
    # RÈGLES BE
    # ------------------------------------------------------------
    @property
    def max_be_per_flight(self) -> int:
        return int(engine_cfg.MAX_BE_PER_FLIGHT)

    @max_be_per_flight.setter
    def max_be_per_flight(self, value: int) -> None:
        engine_cfg.MAX_BE_PER_FLIGHT = int(value)

    @property
    def max_equiv_per_volunteer(self) -> int:
        return int(engine_cfg.MAX_EQUIV_PER_VOLUNTEER)

    @max_equiv_per_volunteer.setter
    def max_equiv_per_volunteer(self, value: int) -> None:
        engine_cfg.MAX_EQUIV_PER_VOLUNTEER = int(value)

    # ------------------------------------------------------------
    # RÈGLES BÉNÉVOLES
    # ------------------------------------------------------------
    @property
    def duree_mission_heures(self) -> int:
        return int(engine_cfg.DUREE_MISSION_HEURES)

    @duree_mission_heures.setter
    def duree_mission_heures(self, value: int) -> None:
        engine_cfg.DUREE_MISSION_HEURES = int(value)

    @property
    def max_benev_per_vol(self):
        return engine_cfg.MAX_BENEV_PER_VOL

    @max_benev_per_vol.setter
    def max_benev_per_vol(self, value):
        if value in ("", None):
            engine_cfg.MAX_BENEV_PER_VOL = None
        else:
            engine_cfg.MAX_BENEV_PER_VOL = int(value)

    # ------------------------------------------------------------
    # RÈGLES VOL / SÉCURITÉ
    # ------------------------------------------------------------
    @property
    def default_flight_time(self) -> datetime.time:
        return engine_cfg.DEFAULT_FLIGHT_TIME

    @default_flight_time.setter
    def default_flight_time(self, value: datetime.time) -> None:
        engine_cfg.DEFAULT_FLIGHT_TIME = value

    @property
    def max_capacite_par_vol(self):
        return engine_cfg.MAX_CAPACITE_PAR_VOL

    @max_capacite_par_vol.setter
    def max_capacite_par_vol(self, value):
        if value in ("", None):
            engine_cfg.MAX_CAPACITE_PAR_VOL = None
        else:
            engine_cfg.MAX_CAPACITE_PAR_VOL = int(value)


settings = Settings()
