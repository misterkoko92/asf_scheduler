# scheduler/models.py
# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# =============================================================
# EXPEDITION (BE)
# =============================================================

@dataclass
class Shipment:
    """
    Representation minimale d'un BE pour les regles metier.
    """

    be_numero: str
    dest: str
    nb_colis_physiques: int
    nb_hf: int
    priority: int

    type_colis: str = ""
    expediteur: str = ""
    customs: bool = False
    special: Optional[str] = None
    status: str = "D"

    # Retrocompatibilite
    @property
    def be_num(self) -> str:
        return self.be_numero

    @be_num.setter
    def be_num(self, value: str) -> None:
        self.be_numero = value
