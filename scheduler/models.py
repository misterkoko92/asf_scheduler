# scheduler/models.py
# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from typing import List, Optional, Dict, Any
import uuid


# =============================================================
#  EXPÉDITION (BE)
# =============================================================

@dataclass
class Shipment:
    """
    Représente un BE (expédition) à planifier :
      - chargé depuis MAG CENTRAL normalisé
      - enrichi par ParamBE
      - affecté ensuite à un vol + bénévole
    """

    # ---------------------------------------------------------
    # 🔵 Champs principaux
    # ---------------------------------------------------------
    be_numero: str                   # N° BE formaté
    dest: str                        # Code IATA
    nb_colis_physiques: int          # NB (col NB)
    nb_hf: int                       # HF (legacy)
    priority: int                    # priorité finale

    type_colis: str = ""
    expediteur: str = ""
    customs: bool = False
    special: Optional[str] = None
    status: str = "D"

    equiv_colis: int = 0
    uid: str = field(default_factory=lambda: str(uuid.uuid4()))

    # ---------------------------------------------------------
    # 🔵 Champs MAG CENTRAL
    # ---------------------------------------------------------
    be_numero_suffix: Optional[str] = ""

    type_mag: Optional[str] = ""
    expediteur_mag: Optional[str] = ""
    destinataire_mag: Optional[str] = ""
    nb_colis_mag: Optional[int] = None

    date_conditionnement: Optional[object] = None
    date_impression_be: Optional[object] = None
    date_depart_mag: Optional[object] = None
    date_vol_mag: Optional[object] = None
    delai_mag: Optional[object] = None
    delai_depart: Optional[object] = None

    special_mag: Optional[str] = None
    douane_brut: Optional[str] = None

    planifiable: bool = False

    mag_fields: Dict[str, Any] = field(default_factory=dict)

    # ---------------------------------------------------------
    # 🔵 Affectations moteur
    # ---------------------------------------------------------
    assigned_flight: Optional["Flight"] = None
    assigned_volunteer: Optional["Volunteer"] = None
    reason_not_planned: Optional[str] = None

    # Rétrocompatibilité
    @property
    def be_num(self) -> str:
        return self.be_numero

    @be_num.setter
    def be_num(self, value: str) -> None:
        self.be_numero = value


# =============================================================
#  VOL
# =============================================================

@dataclass
class Flight:
    """Vol physique unique"""

    flight_number: str
    date: date
    departure_time: Optional[time]
    routing: List[str]

    max_colis_base: Optional[int] = None
    chosen_destination: Optional[str] = None

    shipments: List[Shipment] = field(default_factory=list)
    total_colis: int = 0
    assigned_volunteers: List["Volunteer"] = field(default_factory=list)

    def remaining_capacity(self) -> Optional[int]:
        if self.max_colis_base is None:
            return None
        return max(self.max_colis_base - self.total_colis, 0)

    def add_shipment(self, s: Shipment) -> None:
        if s not in self.shipments:
            self.shipments.append(s)

        units = s.equiv_colis if s.equiv_colis > 0 else s.nb_colis_physiques
        self.total_colis += units

        s.assigned_flight = self


# =============================================================
#  BÉNÉVOLE
# =============================================================

@dataclass
class Volunteer:
    """
    Une ligne de disponibilité = un bénévole disponible un créneau donné.
    """

    id: str
    benevole: str
    nom: str
    prenom: str
    prenom_court: str

    date: date
    heure_arrivee: Optional[time]
    heure_depart: Optional[time]

    max_exped_jour: Optional[int] = None
    max_exped_semaine: Optional[int] = None
    max_jours_semaine: Optional[int] = None

    assigned_flights: List[Flight] = field(default_factory=list)

    def is_time_window_valid(self) -> bool:
        return (
            self.heure_arrivee is not None
            and self.heure_depart is not None
            and self.heure_arrivee <= self.heure_depart
        )
