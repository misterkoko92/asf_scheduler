# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import date, datetime, time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
import os

import pandas as pd
import requests

from loaders.load_benevoles import load_benevoles
from loaders.load_shipments import load_shipments_df
from loaders.load_vols import load_vols_df
from loaders.load_params import (
    load_param_be_from_path,
    load_param_dest_from_path,
    load_param_benev_from_path,
)
import scheduler.config_paths as cp
from scheduler.config_paths import normalize


class DataSource(Protocol):
    name: str

    def is_available(self) -> bool: ...

    def load_param_be(self) -> pd.DataFrame: ...
    def load_param_dest(self) -> pd.DataFrame: ...
    def load_param_benev(self) -> pd.DataFrame: ...

    def load_shipments_df(
        self,
        param_be: pd.DataFrame | None = None,
        *,
        planifiables_only: bool = True,
    ) -> pd.DataFrame: ...
    def load_vols_df(self, param_dest: pd.DataFrame | None = None) -> pd.DataFrame: ...
    def load_benevoles_df(self, param_benev: pd.DataFrame | None = None) -> pd.DataFrame: ...


class BaseDataSource:
    name = "base"

    def is_available(self) -> bool:
        return True

    def load_param_be(self) -> pd.DataFrame:
        raise NotImplementedError

    def load_param_dest(self) -> pd.DataFrame:
        raise NotImplementedError

    def load_param_benev(self) -> pd.DataFrame:
        raise NotImplementedError

    def load_shipments_df(
        self,
        param_be: pd.DataFrame | None = None,
        *,
        planifiables_only: bool = True,
    ) -> pd.DataFrame:
        raise NotImplementedError

    def load_vols_df(self, param_dest: pd.DataFrame | None = None) -> pd.DataFrame:
        raise NotImplementedError

    def load_benevoles_df(self, param_benev: pd.DataFrame | None = None) -> pd.DataFrame:
        raise NotImplementedError


@dataclass(frozen=True)
class ExcelSourcePaths:
    tableau_de_bord: Path
    planning_benevoles: Path
    vols: Path

    @classmethod
    def from_defaults(cls) -> "ExcelSourcePaths":
        return cls(
            tableau_de_bord=Path(cp.TABLEAU_DE_BORD),
            planning_benevoles=Path(cp.PLANNING_BENEVOLES),
            vols=Path(cp.VOLS),
        )


class ExcelDataSource(BaseDataSource):
    name = "excel"

    def __init__(self, paths: ExcelSourcePaths | None = None) -> None:
        self.paths = paths or ExcelSourcePaths.from_defaults()

    def load_param_be(self) -> pd.DataFrame:
        return load_param_be_from_path(self.paths.tableau_de_bord)

    def load_param_dest(self) -> pd.DataFrame:
        return load_param_dest_from_path(self.paths.tableau_de_bord)

    def load_param_benev(self) -> pd.DataFrame:
        return load_param_benev_from_path(self.paths.planning_benevoles)

    def load_shipments_df(
        self,
        param_be: pd.DataFrame | None = None,
        *,
        planifiables_only: bool = True,
    ) -> pd.DataFrame:
        if param_be is None:
            param_be = self.load_param_be()
        return load_shipments_df(
            tdb_path=self.paths.tableau_de_bord,
            param_be_raw=param_be,
            planifiables_only=planifiables_only,
        )

    def load_vols_df(self, param_dest: pd.DataFrame | None = None) -> pd.DataFrame:
        if param_dest is None:
            param_dest = self.load_param_dest()
        return load_vols_df(
            vols_path=self.paths.vols,
            param_dest_df=param_dest,
        )

    def load_benevoles_df(self, param_benev: pd.DataFrame | None = None) -> pd.DataFrame:
        return load_benevoles(planning_path=self.paths.planning_benevoles)


@dataclass(frozen=True)
class ExternalRepoPaths:
    wms_root: Path
    benev_root: Path

    @classmethod
    def detect(cls) -> "ExternalRepoPaths":
        return cls(
            wms_root=_detect_repo_root("ASF_WMS_ROOT", "asf-wms"),
            benev_root=_detect_repo_root("ASF_BENEV_ROOT", "asf-benev"),
        )


def _detect_repo_root(env_var: str, fallback_dir: str) -> Path:
    override = os.getenv(env_var)
    if override:
        return normalize(override)
    return normalize(Path.home() / fallback_dir)


def _unwrap_list(payload):
    if payload is None:
        return []
    if isinstance(payload, dict) and "results" in payload:
        return payload.get("results") or []
    return payload


def _parse_iso_date(value) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    sval = str(value).strip()
    if not sval:
        return None
    if sval.endswith("Z"):
        sval = f"{sval[:-1]}+00:00"
    try:
        return datetime.fromisoformat(sval).date()
    except ValueError:
        pass
    try:
        return datetime.strptime(sval, "%Y-%m-%d").date()
    except ValueError:
        return None


def _format_time(value) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, datetime):
        return value.time().strftime("%H:%M")
    if isinstance(value, time):
        return value.strftime("%H:%M")
    sval = str(value).strip().replace("h", ":")
    if not sval:
        return ""
    if len(sval) >= 5:
        return sval[:5]
    return sval



class AsfWmsDataSource(BaseDataSource):
    name = "asf-wms"

    def __init__(self, root: Path, *, enabled: bool = False) -> None:
        self.root = root
        self.enabled = enabled
        self.api_url = os.getenv("ASF_WMS_API_URL", "").strip().rstrip("/")
        self.api_key = os.getenv("ASF_WMS_API_KEY", "").strip()
        self.timeout = float(os.getenv("ASF_WMS_API_TIMEOUT", "15"))

    def is_available(self) -> bool:
        return self.enabled and bool(self.api_url)

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["X-ASF-Integration-Key"] = self.api_key
        return headers

    def _get(self, path: str, params: dict | None = None):
        if not self.api_url:
            raise RuntimeError("ASF_WMS_API_URL is not set.")
        url = f"{self.api_url}/{path.lstrip('/')}"
        response = requests.get(url, headers=self._headers(), params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def _post(self, path: str, payload: dict):
        if not self.api_url:
            raise RuntimeError("ASF_WMS_API_URL is not set.")
        url = f"{self.api_url}/{path.lstrip('/')}"
        response = requests.post(url, headers=self._headers(), json=payload, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def load_param_be(self) -> pd.DataFrame:
        return pd.DataFrame([{"Type": "AUTRE", "Priorite_Type": 99, "Equiv": 1}])

    def load_param_dest(self) -> pd.DataFrame:
        data = _unwrap_list(self._get("integrations/destinations/"))
        rows = []
        for item in data:
            rows.append(
                {
                    "Dest_IATA": (item.get("iata_code") or "").strip().upper(),
                    "Dest_Ville": item.get("city") or "",
                    "Dest_Pays": item.get("country") or "",
                    "Max_Colis_Par_Vol": "",
                    "Freq_Semaine": "",
                    "Freq_Lundi": 0,
                    "Freq_Mardi": 0,
                    "Freq_Mercredi": 0,
                    "Freq_Jeudi": 0,
                    "Freq_Vendredi": 0,
                    "Freq_Samedi": 0,
                    "Freq_Dimanche": 0,
                    "Contact_Titre": "",
                    "Contact_Nom": item.get("correspondent_name") or "",
                    "Contact_Prenom": "",
                    "Contact_Email": "",
                    "Contact_Copie": "",
                    "Contact_Tel1": "",
                    "Contact_Tel2": "",
                    "Contact_Tel3": "",
                }
            )
        columns = [
            "Dest_IATA",
            "Dest_Ville",
            "Dest_Pays",
            "Max_Colis_Par_Vol",
            "Freq_Semaine",
            "Freq_Lundi",
            "Freq_Mardi",
            "Freq_Mercredi",
            "Freq_Jeudi",
            "Freq_Vendredi",
            "Freq_Samedi",
            "Freq_Dimanche",
            "Contact_Titre",
            "Contact_Nom",
            "Contact_Prenom",
            "Contact_Email",
            "Contact_Copie",
            "Contact_Tel1",
            "Contact_Tel2",
            "Contact_Tel3",
        ]
        return pd.DataFrame(rows, columns=columns)

    def load_param_benev(self) -> pd.DataFrame:
        raise NotImplementedError("WMS does not provide ParamBenev.")

    def load_shipments_df(
        self,
        param_be: pd.DataFrame | None = None,
        *,
        planifiables_only: bool = True,
    ) -> pd.DataFrame:
        data = _unwrap_list(self._get("integrations/shipments/"))
        rows = []
        for item in data:
            status = (item.get("status") or "").strip().lower()
            be_status = "D" if status in {"draft", "picking", "packed"} else "X"
            country = (item.get("destination_country") or "").strip()
            nb_colis = item.get("carton_count") or 0
            try:
                nb_colis = int(nb_colis)
            except (TypeError, ValueError):
                nb_colis = 0
            equiv = max(1, nb_colis) if nb_colis else 1
            rows.append(
                {
                    "BE_Numero": item.get("reference") or "",
                    "BE_Nb_Colis": nb_colis,
                    "Destination": (item.get("destination_iata") or "").strip().upper()
                    or (item.get("destination_city") or "").strip().upper(),
                    "BE_Type": "AUTRE",
                    "BE_Douane": "OUI" if country and country.lower() != "france" else "",
                    "BE_Expediteur": item.get("shipper_name") or "",
                    "BE_Destinataire": item.get("recipient_name") or "",
                    "BE_Date_Impression": _parse_iso_date(item.get("created_at")),
                    "BE_Date_Conditionnement": _parse_iso_date(item.get("ready_at")),
                    "BE_Date_Depart_Mag": _parse_iso_date(item.get("ready_at")),
                    "BE_Date_Vol": _parse_iso_date(item.get("requested_delivery_date")),
                    "BE_Statut": be_status,
                    "BE_Special": "",
                    "Commentaires": item.get("notes") or "",
                    "Controle_Planning": "",
                    "Controle_Expedition": "",
                    "Controle_Reception": "",
                    "Numero_Facture": "",
                    "Facture_Envoyee": "",
                    "Facture_Payee": "",
                    "Priorite": 99,
                    "Equiv_Colis": equiv,
                }
            )
        columns = [
            "BE_Numero",
            "BE_Nb_Colis",
            "Destination",
            "BE_Type",
            "BE_Douane",
            "BE_Expediteur",
            "BE_Destinataire",
            "BE_Date_Impression",
            "BE_Date_Conditionnement",
            "BE_Date_Depart_Mag",
            "BE_Date_Vol",
            "BE_Statut",
            "BE_Special",
            "Commentaires",
            "Controle_Planning",
            "Controle_Expedition",
            "Controle_Reception",
            "Numero_Facture",
            "Facture_Envoyee",
            "Facture_Payee",
            "Priorite",
            "Equiv_Colis",
        ]
        df = pd.DataFrame(rows, columns=columns)
        if "BE_Nb_Colis" in df.columns:
            df["BE_Nb_Colis"] = pd.to_numeric(df["BE_Nb_Colis"], errors="coerce").astype("Int64")
        if "Equiv_Colis" in df.columns:
            df["Equiv_Colis"] = pd.to_numeric(df["Equiv_Colis"], errors="coerce").astype("Int64")
        if "Priorite" in df.columns:
            df["Priorite"] = pd.to_numeric(df["Priorite"], errors="coerce").astype("Int64")
        if "BE_Statut" in df.columns:
            df["BE_Statut"] = df["BE_Statut"].astype(str).str.strip().str.upper()
        if planifiables_only:
            df = df[df["BE_Statut"] == "D"].copy()
        return df

    def load_vols_df(self, param_dest: pd.DataFrame | None = None) -> pd.DataFrame:
        raise NotImplementedError("WMS does not provide flights.")

    def load_benevoles_df(self, param_benev: pd.DataFrame | None = None) -> pd.DataFrame:
        raise NotImplementedError("WMS does not provide volunteers.")

    def fetch_events(self, *, direction: str | None = None, status: str | None = None, source: str | None = None):
        params = {}
        if direction:
            params["direction"] = direction
        if status:
            params["status"] = status
        if source:
            params["source"] = source
        return _unwrap_list(self._get("integrations/events/", params=params or None))

    def push_event(
        self,
        event_type: str,
        payload: dict,
        *,
        source: str = "asf_scheduler",
        target: str = "",
        external_id: str = "",
    ):
        data = {
            "source": source,
            "target": target,
            "event_type": event_type,
            "external_id": external_id,
            "payload": payload or {},
        }
        return self._post("integrations/events/", data)


class AsfBenevDataSource(BaseDataSource):
    name = "asf-benev"

    def __init__(self, root: Path, *, enabled: bool = False) -> None:
        self.root = root
        self.enabled = enabled
        self.api_url = os.getenv("ASF_BENEV_API_URL", "").strip().rstrip("/")
        self.api_key = os.getenv("ASF_BENEV_API_KEY", "").strip()
        self.api_token = os.getenv("ASF_BENEV_API_TOKEN", "").strip()
        self.timeout = float(os.getenv("ASF_BENEV_API_TIMEOUT", "15"))

    def is_available(self) -> bool:
        return self.enabled and bool(self.api_url)

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["X-ASF-Integration-Key"] = self.api_key
        if self.api_token:
            headers["Authorization"] = f"Token {self.api_token}"
        return headers

    def _get(self, path: str, params: dict | None = None):
        if not self.api_url:
            raise RuntimeError("ASF_BENEV_API_URL is not set.")
        url = f"{self.api_url}/{path.lstrip('/')}"
        response = requests.get(url, headers=self._headers(), params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def _post(self, path: str, payload: dict):
        if not self.api_url:
            raise RuntimeError("ASF_BENEV_API_URL is not set.")
        url = f"{self.api_url}/{path.lstrip('/')}"
        response = requests.post(url, headers=self._headers(), json=payload, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def load_param_be(self) -> pd.DataFrame:
        raise NotImplementedError("Benev does not provide ParamBE.")

    def load_param_dest(self) -> pd.DataFrame:
        raise NotImplementedError("Benev does not provide ParamDest.")

    def load_param_benev(self) -> pd.DataFrame:
        data = _unwrap_list(self._get("integrations/volunteers/"))
        rows = []
        for item in data:
            constraints = item.get("constraints") or {}
            rows.append(
                {
                    "ID": item.get("volunteer_id"),
                    "Benevole": item.get("full_name") or item.get("short_name") or "",
                    "Nom": item.get("last_name") or "",
                    "Prenom": item.get("first_name") or "",
                    "Prenom_Court": item.get("short_name") or "",
                    "Email": item.get("email") or "",
                    "Telephone": item.get("phone") or "",
                    "Max_Jours_Semaine": constraints.get("max_days_per_week"),
                    "Max_Exp_Semaine": constraints.get("max_expeditions_per_week"),
                    "Max_Exp_Jour": constraints.get("max_expeditions_per_day"),
                    "Attente_Max_Heures": constraints.get("max_wait_hours"),
                }
            )
        df = pd.DataFrame(rows)
        if "ID" in df.columns:
            df["ID"] = pd.to_numeric(df["ID"], errors="coerce").astype("Int64")
        for col in ["Max_Jours_Semaine", "Max_Exp_Semaine", "Max_Exp_Jour"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
        if "Attente_Max_Heures" in df.columns:
            df["Attente_Max_Heures"] = pd.to_numeric(df["Attente_Max_Heures"], errors="coerce")
        return df

    def load_shipments_df(
        self,
        param_be: pd.DataFrame | None = None,
        *,
        planifiables_only: bool = True,
    ) -> pd.DataFrame:
        raise NotImplementedError("Benev does not provide shipments.")

    def load_vols_df(self, param_dest: pd.DataFrame | None = None) -> pd.DataFrame:
        raise NotImplementedError("Benev does not provide flights.")

    def load_benevoles_df(self, param_benev: pd.DataFrame | None = None) -> pd.DataFrame:
        if param_benev is None:
            param_benev = self.load_param_benev()
        param_map = {}
        if param_benev is not None and not param_benev.empty:
            for _, row in param_benev.iterrows():
                if pd.isna(row.get("ID")):
                    continue
                try:
                    param_map[int(row.get("ID"))] = row
                except (TypeError, ValueError):
                    continue
        params = {}
        start = os.getenv("ASF_BENEV_API_START", "").strip()
        end = os.getenv("ASF_BENEV_API_END", "").strip()
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        data = _unwrap_list(self._get("integrations/availabilities/", params=params or None))
        rows = []
        for item in data:
            vid = item.get("volunteer_id")
            try:
                vid_int = int(vid)
            except (TypeError, ValueError):
                vid_int = None
            info = param_map.get(vid_int, {})
            rows.append(
                {
                    "ID": vid,
                    "Benevole": info.get("Benevole", "") if info else "",
                    "Nom": info.get("Nom", "") if info else "",
                    "Prenom": info.get("Prenom", "") if info else "",
                    "Prenom_Court": info.get("Prenom_Court", "") if info else "",
                    "Date": _parse_iso_date(item.get("date")) or item.get("date") or "",
                    "Heure_Arrivee": _format_time(item.get("start_time")),
                    "Heure_Depart": _format_time(item.get("end_time")),
                }
            )
        columns = [
            "ID",
            "Benevole",
            "Nom",
            "Prenom",
            "Prenom_Court",
            "Date",
            "Heure_Arrivee",
            "Heure_Depart",
        ]
        return pd.DataFrame(rows, columns=columns)

    def fetch_events(self, *, direction: str | None = None, status: str | None = None, source: str | None = None):
        params = {}
        if direction:
            params["direction"] = direction
        if status:
            params["status"] = status
        if source:
            params["source"] = source
        return _unwrap_list(self._get("integrations/events/", params=params or None))

    def push_event(
        self,
        event_type: str,
        payload: dict,
        *,
        source: str = "asf_scheduler",
        target: str = "",
        external_id: str = "",
    ):
        data = {
            "source": source,
            "target": target,
            "event_type": event_type,
            "external_id": external_id,
            "payload": payload or {},
        }
        return self._post("integrations/events/", data)


class CompositeDataSource(BaseDataSource):
    name = "composite"

    def __init__(
        self,
        *,
        base: DataSource,
        shipments_source: DataSource | None = None,
        volunteers_source: DataSource | None = None,
        vols_source: DataSource | None = None,
    ) -> None:
        self.base = base
        self.shipments_source = shipments_source
        self.volunteers_source = volunteers_source
        self.vols_source = vols_source

    def _select(self, source: DataSource | None) -> DataSource:
        if source is not None and source.is_available():
            return source
        return self.base

    def load_param_be(self) -> pd.DataFrame:
        return self._select(self.shipments_source).load_param_be()

    def load_param_dest(self) -> pd.DataFrame:
        return self._select(self.vols_source).load_param_dest()

    def load_param_benev(self) -> pd.DataFrame:
        return self._select(self.volunteers_source).load_param_benev()

    def load_shipments_df(
        self,
        param_be: pd.DataFrame | None = None,
        *,
        planifiables_only: bool = True,
    ) -> pd.DataFrame:
        source = self._select(self.shipments_source)
        if param_be is None:
            param_be = source.load_param_be()
        return source.load_shipments_df(
            param_be,
            planifiables_only=planifiables_only,
        )

    def load_vols_df(self, param_dest: pd.DataFrame | None = None) -> pd.DataFrame:
        source = self._select(self.vols_source)
        if param_dest is None:
            param_dest = source.load_param_dest()
        return source.load_vols_df(param_dest)

    def load_benevoles_df(self, param_benev: pd.DataFrame | None = None) -> pd.DataFrame:
        source = self._select(self.volunteers_source)
        if param_benev is None:
            param_benev = source.load_param_benev()
        return source.load_benevoles_df(param_benev)


def resolve_data_source(
    name: str | None = None,
    *,
    excel_paths: ExcelSourcePaths | None = None,
    external_paths: ExternalRepoPaths | None = None,
) -> DataSource:
    key = (name or os.getenv("ASF_DATA_SOURCE", "excel")).strip().lower()
    external_paths = external_paths or ExternalRepoPaths.detect()
    if key in {"excel", "default"}:
        return ExcelDataSource(paths=excel_paths)

    if key in {"composite", "auto"}:
        wms = AsfWmsDataSource(
            external_paths.wms_root,
            enabled=os.getenv("ASF_WMS_ENABLE") == "1",
        )
        benev = AsfBenevDataSource(
            external_paths.benev_root,
            enabled=os.getenv("ASF_BENEV_ENABLE") == "1",
        )
        return CompositeDataSource(
            base=ExcelDataSource(paths=excel_paths),
            shipments_source=wms,
            volunteers_source=benev,
        )

    if key == "asf-wms":
        return AsfWmsDataSource(
            external_paths.wms_root,
            enabled=os.getenv("ASF_WMS_ENABLE") == "1",
        )

    if key == "asf-benev":
        return AsfBenevDataSource(
            external_paths.benev_root,
            enabled=os.getenv("ASF_BENEV_ENABLE") == "1",
        )

    return ExcelDataSource(paths=excel_paths)
