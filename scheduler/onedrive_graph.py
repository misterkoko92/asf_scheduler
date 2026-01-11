# scheduler/onedrive_graph.py
# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import quote

import msal
import requests

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
DEFAULT_SCOPES = ["User.Read", "Files.ReadWrite", "offline_access"]
SMALL_UPLOAD_LIMIT = 4 * 1024 * 1024  # 4 MB
CHUNK_SIZE = 10 * 1024 * 1024  # 10 MB, multiple of 320 KiB


class GraphAuthRequired(RuntimeError):
    def __init__(self, message: str, flow: Optional[dict] = None) -> None:
        super().__init__(message)
        self.flow = flow


@dataclass
class GraphConfig:
    tenant_id: str
    client_id: str
    scopes: list[str]
    token_cache_path: Path


class OneDriveGraphClient:
    def __init__(self, config: GraphConfig) -> None:
        self.config = config
        self._cache = msal.SerializableTokenCache()
        if config.token_cache_path.exists():
            self._cache.deserialize(config.token_cache_path.read_text())
        self._app = msal.PublicClientApplication(
            client_id=config.client_id,
            authority=f"https://login.microsoftonline.com/{config.tenant_id}",
            token_cache=self._cache,
        )

    def _persist_cache(self) -> None:
        if not self._cache.has_state_changed:
            return
        self.config.token_cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.config.token_cache_path.write_text(self._cache.serialize())

    def _encode_path(self, path: str) -> str:
        return quote(path.lstrip("/"), safe="/")

    def _headers(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    def acquire_token_silent(self) -> Optional[str]:
        accounts = self._app.get_accounts()
        if not accounts:
            return None
        result = self._app.acquire_token_silent(self.config.scopes, account=accounts[0])
        if result and "access_token" in result:
            self._persist_cache()
            return result["access_token"]
        return None

    def begin_device_flow(self) -> dict:
        flow = self._app.initiate_device_flow(scopes=self.config.scopes)
        if "user_code" not in flow:
            raise GraphAuthRequired(flow.get("error_description", "Device flow init failed."), flow)
        return flow

    def complete_device_flow(self, flow: dict) -> str:
        result = self._app.acquire_token_by_device_flow(flow)
        if "access_token" not in result:
            raise GraphAuthRequired(result.get("error_description", "Device flow failed."), flow)
        self._persist_cache()
        return result["access_token"]

    def ensure_token(self, *, interactive: bool = False, flow: Optional[dict] = None) -> str:
        token = self.acquire_token_silent()
        if token:
            return token
        if not interactive:
            raise GraphAuthRequired("Graph auth required (device code).")
        if flow is None:
            flow = self.begin_device_flow()
        return self.complete_device_flow(flow)

    def download_file(self, remote_path: str, local_path: Path, *, interactive: bool = False) -> bool:
        token = self.ensure_token(interactive=interactive)
        url = f"{GRAPH_BASE_URL}/me/drive/root:/{self._encode_path(remote_path)}:/content"
        res = requests.get(url, headers=self._headers(token), stream=True, timeout=60)
        if res.status_code == 404:
            return False
        res.raise_for_status()
        local_path.parent.mkdir(parents=True, exist_ok=True)
        with open(local_path, "wb") as handle:
            for chunk in res.iter_content(chunk_size=8192):
                if chunk:
                    handle.write(chunk)
        return True

    def _ensure_remote_dir(self, remote_dir: str, token: str) -> None:
        remote_dir = remote_dir.strip("/")
        if not remote_dir:
            return
        parts = remote_dir.split("/")
        current = ""
        for part in parts:
            parent = current
            current = f"{current}/{part}" if current else part
            url = f"{GRAPH_BASE_URL}/me/drive/root:/{self._encode_path(parent)}:/children" if parent else f"{GRAPH_BASE_URL}/me/drive/root/children"
            payload = {
                "name": part,
                "folder": {},
                "@microsoft.graph.conflictBehavior": "fail",
            }
            res = requests.post(url, headers={**self._headers(token), "Content-Type": "application/json"}, json=payload, timeout=30)
            if res.status_code in (201, 409):  # created or already exists
                continue
            res.raise_for_status()

    def upload_file(
        self,
        local_path: Path,
        remote_path: str,
        *,
        interactive: bool = False,
        conflict_behavior: str = "replace",
    ) -> bool:
        token = self.ensure_token(interactive=interactive)
        local_path = Path(local_path)
        size = local_path.stat().st_size
        remote_path = remote_path.strip("/")
        remote_dir = "/".join(remote_path.split("/")[:-1])
        self._ensure_remote_dir(remote_dir, token)

        if size <= SMALL_UPLOAD_LIMIT:
            url = f"{GRAPH_BASE_URL}/me/drive/root:/{self._encode_path(remote_path)}:/content"
            url += f"?@microsoft.graph.conflictBehavior={conflict_behavior}"
            with open(local_path, "rb") as handle:
                res = requests.put(
                    url,
                    headers={**self._headers(token), "Content-Type": "application/octet-stream"},
                    data=handle,
                    timeout=60,
                )
            res.raise_for_status()
            return True

        create_url = f"{GRAPH_BASE_URL}/me/drive/root:/{self._encode_path(remote_path)}:/createUploadSession"
        payload = {"item": {"@microsoft.graph.conflictBehavior": conflict_behavior}}
        res = requests.post(
            create_url,
            headers={**self._headers(token), "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        res.raise_for_status()
        upload_url = res.json().get("uploadUrl")
        if not upload_url:
            raise RuntimeError("Missing uploadUrl from Graph.")

        with open(local_path, "rb") as handle:
            start = 0
            while start < size:
                chunk = handle.read(CHUNK_SIZE)
                if not chunk:
                    break
                end = start + len(chunk) - 1
                headers = {
                    "Content-Length": str(len(chunk)),
                    "Content-Range": f"bytes {start}-{end}/{size}",
                }
                put_res = requests.put(upload_url, headers=headers, data=chunk, timeout=120)
                if put_res.status_code in (200, 201):
                    return True
                if put_res.status_code != 202:
                    put_res.raise_for_status()
                start = end + 1
        return True

    def list_children(self, remote_dir: str, *, interactive: bool = False) -> list[dict]:
        token = self.ensure_token(interactive=interactive)
        remote_dir = remote_dir.strip("/")
        if remote_dir:
            url = f"{GRAPH_BASE_URL}/me/drive/root:/{self._encode_path(remote_dir)}:/children"
        else:
            url = f"{GRAPH_BASE_URL}/me/drive/root/children"
        items: list[dict] = []
        while url:
            res = requests.get(url, headers=self._headers(token), timeout=30)
            res.raise_for_status()
            data = res.json()
            items.extend(data.get("value", []))
            url = data.get("@odata.nextLink")
        return items

    def list_files_recursive(
        self,
        remote_dir: str,
        *,
        interactive: bool = False,
        suffixes: Optional[Iterable[str]] = None,
    ) -> list[dict]:
        suffixes = [s.lower() for s in (suffixes or [])]
        files: list[dict] = []
        for item in self.list_children(remote_dir, interactive=interactive):
            name = item.get("name", "")
            child_path = f"{remote_dir.strip('/')}/{name}".strip("/")
            if "folder" in item:
                files.extend(self.list_files_recursive(child_path, interactive=interactive, suffixes=suffixes))
                continue
            if suffixes and not any(name.lower().endswith(s) for s in suffixes):
                continue
            files.append({"name": name, "path": child_path, "size": item.get("size", 0)})
        return files
