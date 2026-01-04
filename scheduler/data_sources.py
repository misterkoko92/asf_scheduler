# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
import os

import pandas as pd

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


class AsfWmsDataSource(BaseDataSource):
    name = "asf-wms"

    def __init__(self, root: Path, *, enabled: bool = False) -> None:
        self.root = root
        self.enabled = enabled

    def is_available(self) -> bool:
        return self.enabled and self.root.exists()

    def load_param_be(self) -> pd.DataFrame:
        raise NotImplementedError("WMS param BE integration not implemented yet.")

    def load_param_dest(self) -> pd.DataFrame:
        raise NotImplementedError("WMS does not provide ParamDest.")

    def load_param_benev(self) -> pd.DataFrame:
        raise NotImplementedError("WMS does not provide ParamBenev.")

    def load_shipments_df(
        self,
        param_be: pd.DataFrame | None = None,
        *,
        planifiables_only: bool = True,
    ) -> pd.DataFrame:
        raise NotImplementedError("WMS shipment integration not implemented yet.")

    def load_vols_df(self, param_dest: pd.DataFrame | None = None) -> pd.DataFrame:
        raise NotImplementedError("WMS does not provide flights.")

    def load_benevoles_df(self, param_benev: pd.DataFrame | None = None) -> pd.DataFrame:
        raise NotImplementedError("WMS does not provide volunteers.")


class AsfBenevDataSource(BaseDataSource):
    name = "asf-benev"

    def __init__(self, root: Path, *, enabled: bool = False) -> None:
        self.root = root
        self.enabled = enabled

    def is_available(self) -> bool:
        return self.enabled and self.root.exists()

    def load_param_be(self) -> pd.DataFrame:
        raise NotImplementedError("Benev does not provide ParamBE.")

    def load_param_dest(self) -> pd.DataFrame:
        raise NotImplementedError("Benev does not provide ParamDest.")

    def load_param_benev(self) -> pd.DataFrame:
        raise NotImplementedError("Benev param integration not implemented yet.")

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
        raise NotImplementedError("Benev availability integration not implemented yet.")


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
