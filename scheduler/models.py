# scheduler/models.py
# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from typing import List, Optional


# ===========================
#  EXPÉDITIONS (BE)
# ===========================

@dataclass
class Shipment:
    """Représente un BE (expédition) à planifier sur un vol."""
    be_numero: str
    dest: str                          # Destination IATA (TNR, BZV…)
    nb_colis_physiques: int
    nb_hf: int
    priority: int

    # Champs supplémentaires
    type_colis: str = ""
    expediteur: str = ""
    customs: bool = False
    special: Optional[str] = None
    status: str = "D"

    # Charge équivalente utilisée pour le calcul des capacités vols
    equiv_colis: int = 0

    # Renseignés par le scheduler
    assigned_flight: Optional["Flight"] = None
    reason_not_planned: Optional[str] = None


# ===========================
#  VOL
# ===========================

@dataclass
class Flight:
    """Représente un vol potentiellement planifiable pour des BE."""
    flight_number: str
    date: date
    departure_time: Optional[time]
    routing: List[str]

    max_colis_base: Optional[int] = None
    chosen_destination: Optional[str] = None

    shipments: List[Shipment] = field(default_factory=list)

    # Charge équivalente totale utilisée
    total_colis: int = 0

    # Liste des bénévoles affectés
    assigned_volunteers: List["Volunteer"] = field(default_factory=list)

    # ---- Méthodes utilitaires ----
    def remaining_capacity(self) -> Optional[int]:
        """
        Retourne la capacité restante en unités équivalentes.
        """
        if self.max_colis_base is None:
            return None
        return max(self.max_colis_base - self.total_colis, 0)

    def add_shipment(self, s: Shipment) -> None:
        """
        Ajoute un BE sur ce vol (méthode centralisée pour éviter
        les erreurs dans flight_manager).
        """
        if s not in self.shipments:
            self.shipments.append(s)

        units = s.equiv_colis if s.equiv_colis > 0 else s.nb_colis_physiques
        self.total_colis += units
        s.assigned_flight = self


# ===========================
#  BÉNÉVOLE
# ===========================

@dataclass
class Volunteer:
    """Représente un bénévole et ses contraintes journalières."""
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

    assigned_flights: List["Flight"] = field(default_factory=list)

    def is_time_window_valid(self) -> bool:
        return self.heure_arrivee is not None and self.heure_depart is not None
