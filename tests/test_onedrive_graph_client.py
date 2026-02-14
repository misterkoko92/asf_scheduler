# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import pytest
import requests


class _DummyCache:
    def __init__(self, *, changed: bool = False) -> None:
        self.has_state_changed = changed
        self.deserialized = None

    def deserialize(self, payload: str) -> None:
        self.deserialized = payload

    def serialize(self) -> str:
        return '{"ok": true}'


class _Response:
    def __init__(
        self,
        *,
        status_code: int = 200,
        json_data: dict | None = None,
        chunks: list[bytes] | None = None,
    ) -> None:
        self.status_code = status_code
        self._json_data = json_data or {}
        self._chunks = chunks or []

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return self._json_data

    def iter_content(self, chunk_size: int = 8192):
        _ = chunk_size
        for chunk in self._chunks:
            yield chunk


def _build_client(monkeypatch, tmp_path: Path, *, app):
    pytest.importorskip("msal")
    import scheduler.onedrive_graph as odg

    cache = _DummyCache(changed=True)
    monkeypatch.setattr(odg.msal, "SerializableTokenCache", lambda: cache)
    monkeypatch.setattr(odg.msal, "PublicClientApplication", lambda **kwargs: app)

    cfg = odg.GraphConfig(
        tenant_id="tenant-id",
        client_id="client-id",
        scopes=["User.Read"],
        token_cache_path=tmp_path / "cache.json",
    )
    client = odg.OneDriveGraphClient(cfg)
    return odg, client, cache


def test_init_deserializes_existing_cache(monkeypatch, tmp_path):
    class _App:
        pass

    token_cache = tmp_path / "cache.json"
    token_cache.write_text("SERIALIZED", encoding="utf-8")

    odg, client, cache = _build_client(monkeypatch, tmp_path, app=_App())

    assert cache.deserialized == "SERIALIZED"
    assert client.config.token_cache_path == token_cache
    assert odg.GRAPH_BASE_URL.startswith("https://graph.microsoft.com")


def test_acquire_token_silent_returns_none_without_accounts(monkeypatch, tmp_path):
    class _App:
        def get_accounts(self):
            return []

    _, client, _ = _build_client(monkeypatch, tmp_path, app=_App())
    assert client.acquire_token_silent() is None


def test_acquire_token_silent_returns_token_and_persists(monkeypatch, tmp_path):
    class _App:
        def get_accounts(self):
            return [{"id": "acc"}]

        def acquire_token_silent(self, scopes, account):
            _ = scopes, account
            return {"access_token": "abc"}

    _, client, _ = _build_client(monkeypatch, tmp_path, app=_App())
    called = {"persist": 0}
    monkeypatch.setattr(client, "_persist_cache", lambda: called.__setitem__("persist", called["persist"] + 1))

    assert client.acquire_token_silent() == "abc"
    assert called["persist"] == 1


def test_device_flow_errors_raise_graphauthrequired(monkeypatch, tmp_path):
    class _App:
        def initiate_device_flow(self, scopes):
            _ = scopes
            return {"error_description": "init failed"}

        def acquire_token_by_device_flow(self, flow):
            _ = flow
            return {"error_description": "flow failed"}

    odg, client, _ = _build_client(monkeypatch, tmp_path, app=_App())

    with pytest.raises(odg.GraphAuthRequired):
        client.begin_device_flow()
    with pytest.raises(odg.GraphAuthRequired):
        client.complete_device_flow({"user_code": "1234"})


def test_ensure_token_paths(monkeypatch, tmp_path):
    class _App:
        pass

    odg, client, _ = _build_client(monkeypatch, tmp_path, app=_App())
    monkeypatch.setattr(client, "acquire_token_silent", lambda: None)

    with pytest.raises(odg.GraphAuthRequired):
        client.ensure_token(interactive=False)

    monkeypatch.setattr(client, "begin_device_flow", lambda: {"user_code": "1234"})
    monkeypatch.setattr(client, "complete_device_flow", lambda flow: "tok-" + flow["user_code"])
    assert client.ensure_token(interactive=True) == "tok-1234"


def test_download_file_404_and_success(monkeypatch, tmp_path):
    class _App:
        pass

    odg, client, _ = _build_client(monkeypatch, tmp_path, app=_App())
    monkeypatch.setattr(client, "ensure_token", lambda interactive=False: "token")

    responses = [
        _Response(status_code=404),
        _Response(status_code=200, chunks=[b"a", b"b"]),
    ]

    def _fake_get(url, headers, stream, timeout):
        _ = url, headers, stream, timeout
        return responses.pop(0)

    monkeypatch.setattr(odg.requests, "get", _fake_get)

    missing = tmp_path / "missing.bin"
    assert client.download_file("remote/missing.bin", missing) is False
    assert not missing.exists()

    out = tmp_path / "ok.bin"
    assert client.download_file("remote/ok.bin", out) is True
    assert out.read_bytes() == b"ab"


def test_ensure_remote_dir_uses_expected_calls(monkeypatch, tmp_path):
    class _App:
        pass

    odg, client, _ = _build_client(monkeypatch, tmp_path, app=_App())
    calls: list[tuple[str, str]] = []
    statuses = [201, 409]

    def _fake_post(url, headers, json, timeout):
        _ = headers, timeout
        calls.append((url, str(json.get("name"))))
        return _Response(status_code=statuses.pop(0))

    monkeypatch.setattr(odg.requests, "post", _fake_post)
    client._ensure_remote_dir("a/b", "token")

    assert calls[0][0].endswith("/me/drive/root/children")
    assert calls[0][1] == "a"
    assert calls[1][0].endswith("/me/drive/root:/a:/children")
    assert calls[1][1] == "b"


def test_upload_file_small_path(monkeypatch, tmp_path):
    class _App:
        pass

    odg, client, _ = _build_client(monkeypatch, tmp_path, app=_App())
    local = tmp_path / "small.txt"
    local.write_bytes(b"abc")
    monkeypatch.setattr(client, "ensure_token", lambda interactive=False: "token")
    captured: dict[str, object] = {}
    monkeypatch.setattr(client, "_ensure_remote_dir", lambda remote_dir, token: captured.update({"dir": remote_dir}))
    monkeypatch.setattr(
        odg.requests,
        "put",
        lambda url, headers, data, timeout: captured.update({"url": url, "headers": headers}) or _Response(status_code=200),
    )

    assert client.upload_file(local, "folder/small.txt") is True
    assert captured["dir"] == "folder"
    assert "conflictBehavior=replace" in str(captured["url"])


def test_upload_file_large_path(monkeypatch, tmp_path):
    class _App:
        pass

    odg, client, _ = _build_client(monkeypatch, tmp_path, app=_App())
    monkeypatch.setattr(odg, "SMALL_UPLOAD_LIMIT", 4)
    monkeypatch.setattr(odg, "CHUNK_SIZE", 3)
    local = tmp_path / "big.bin"
    local.write_bytes(b"abcdefghij")
    monkeypatch.setattr(client, "ensure_token", lambda interactive=False: "token")
    monkeypatch.setattr(client, "_ensure_remote_dir", lambda remote_dir, token: None)

    upload_url = "https://upload.example/session"
    chunk_statuses = [202, 202, 202, 201]
    put_ranges: list[str] = []

    def _fake_post(url, headers, json, timeout):
        _ = headers, json, timeout
        assert url.endswith(":/createUploadSession")
        return _Response(status_code=200, json_data={"uploadUrl": upload_url})

    def _fake_put(url, headers, data, timeout):
        _ = data, timeout
        if url == upload_url:
            put_ranges.append(headers["Content-Range"])
            return _Response(status_code=chunk_statuses.pop(0))
        raise AssertionError(f"Unexpected PUT url: {url}")

    monkeypatch.setattr(odg.requests, "post", _fake_post)
    monkeypatch.setattr(odg.requests, "put", _fake_put)

    assert client.upload_file(local, "folder/big.bin") is True
    assert put_ranges[0] == "bytes 0-2/10"
    assert put_ranges[-1] == "bytes 9-9/10"


def test_list_children_handles_pagination(monkeypatch, tmp_path):
    class _App:
        pass

    odg, client, _ = _build_client(monkeypatch, tmp_path, app=_App())
    monkeypatch.setattr(client, "ensure_token", lambda interactive=False: "token")

    urls = []
    responses = [
        _Response(status_code=200, json_data={"value": [{"name": "a"}], "@odata.nextLink": "NEXT"}),
        _Response(status_code=200, json_data={"value": [{"name": "b"}]}),
    ]

    def _fake_get(url, headers, timeout):
        _ = headers, timeout
        urls.append(url)
        return responses.pop(0)

    monkeypatch.setattr(odg.requests, "get", _fake_get)
    items = client.list_children("folder")

    assert items == [{"name": "a"}, {"name": "b"}]
    assert urls[0].endswith("/me/drive/root:/folder:/children")
    assert urls[1] == "NEXT"


def test_list_files_recursive_filters_suffixes(monkeypatch, tmp_path):
    class _App:
        pass

    _, client, _ = _build_client(monkeypatch, tmp_path, app=_App())

    def _fake_list_children(remote_dir, interactive=False):
        _ = interactive
        mapping = {
            "root": [
                {"name": "A.xlsx"},
                {"name": "B.txt"},
                {"name": "sub", "folder": {}},
            ],
            "root/sub": [
                {"name": "C.xlsm"},
                {"name": "D.csv"},
            ],
        }
        return mapping.get(remote_dir, [])

    monkeypatch.setattr(client, "list_children", _fake_list_children)
    files = client.list_files_recursive("root", suffixes=[".xlsx", ".xlsm"])

    assert files == [
        {"name": "A.xlsx", "path": "root/A.xlsx", "size": 0},
        {"name": "C.xlsm", "path": "root/sub/C.xlsm", "size": 0},
    ]


def test_persist_cache_no_change_does_not_write(monkeypatch, tmp_path):
    class _App:
        pass

    _, client, cache = _build_client(monkeypatch, tmp_path, app=_App())
    cache.has_state_changed = False
    client._persist_cache()
    assert not client.config.token_cache_path.exists()


def test_acquire_and_complete_device_flow_success_paths(monkeypatch, tmp_path):
    class _App:
        def get_accounts(self):
            return [{"id": "acc"}]

        def acquire_token_silent(self, scopes, account):
            _ = scopes, account
            return {"token_type": "Bearer"}

        def initiate_device_flow(self, scopes):
            _ = scopes
            return {"user_code": "1234", "message": "ok"}

        def acquire_token_by_device_flow(self, flow):
            _ = flow
            return {"access_token": "tok"}

    _, client, _ = _build_client(monkeypatch, tmp_path, app=_App())
    called = {"persist": 0}
    monkeypatch.setattr(client, "_persist_cache", lambda: called.__setitem__("persist", called["persist"] + 1))

    assert client.acquire_token_silent() is None
    flow = client.begin_device_flow()
    assert flow["user_code"] == "1234"
    assert client.complete_device_flow(flow) == "tok"
    monkeypatch.setattr(client, "acquire_token_silent", lambda: "tok")
    assert client.ensure_token(interactive=False) == "tok"
    assert called["persist"] == 1


def test_ensure_remote_dir_empty_and_unexpected_status(monkeypatch, tmp_path):
    class _App:
        pass

    odg, client, _ = _build_client(monkeypatch, tmp_path, app=_App())
    calls = {"count": 0}

    def _fake_post(url, headers, json, timeout):
        _ = url, headers, json, timeout
        calls["count"] += 1
        return _Response(status_code=200)

    monkeypatch.setattr(odg.requests, "post", _fake_post)
    client._ensure_remote_dir("", "token")
    client._ensure_remote_dir("a", "token")
    assert calls["count"] == 1


def test_upload_large_missing_upload_url_raises(monkeypatch, tmp_path):
    class _App:
        pass

    odg, client, _ = _build_client(monkeypatch, tmp_path, app=_App())
    monkeypatch.setattr(odg, "SMALL_UPLOAD_LIMIT", 1)
    local = tmp_path / "big.bin"
    local.write_bytes(b"abcdefgh")
    monkeypatch.setattr(client, "ensure_token", lambda interactive=False: "token")
    monkeypatch.setattr(client, "_ensure_remote_dir", lambda remote_dir, token: None)
    monkeypatch.setattr(
        odg.requests,
        "post",
        lambda *_a, **_k: _Response(status_code=200, json_data={}),
    )

    with pytest.raises(RuntimeError):
        client.upload_file(local, "folder/big.bin")


def test_upload_large_chunk_error_and_empty_chunk_break(monkeypatch, tmp_path):
    class _App:
        pass

    odg, client, _ = _build_client(monkeypatch, tmp_path, app=_App())
    monkeypatch.setattr(odg, "SMALL_UPLOAD_LIMIT", 1)
    local = tmp_path / "big.bin"
    local.write_bytes(b"abcdefgh")
    monkeypatch.setattr(client, "ensure_token", lambda interactive=False: "token")
    monkeypatch.setattr(client, "_ensure_remote_dir", lambda remote_dir, token: None)

    upload_url = "https://upload.example/session"
    monkeypatch.setattr(
        odg.requests,
        "post",
        lambda *_a, **_k: _Response(status_code=200, json_data={"uploadUrl": upload_url}),
    )
    monkeypatch.setattr(
        odg.requests,
        "put",
        lambda *_a, **_k: _Response(status_code=500),
    )
    with pytest.raises(requests.HTTPError):
        client.upload_file(local, "folder/big.bin")

    class _EmptyReader:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            _ = exc_type, exc, tb
            return False

        def read(self, _size):
            return b""

    monkeypatch.setattr(odg, "CHUNK_SIZE", 3)
    monkeypatch.setattr("builtins.open", lambda *_a, **_k: _EmptyReader())
    monkeypatch.setattr(odg.requests, "put", lambda *_a, **_k: _Response(status_code=202))
    assert client.upload_file(local, "folder/big.bin") is True


def test_list_children_root_directory_url(monkeypatch, tmp_path):
    class _App:
        pass

    odg, client, _ = _build_client(monkeypatch, tmp_path, app=_App())
    monkeypatch.setattr(client, "ensure_token", lambda interactive=False: "token")
    seen: list[str] = []
    monkeypatch.setattr(
        odg.requests,
        "get",
        lambda url, headers, timeout: seen.append(url) or _Response(status_code=200, json_data={"value": []}),
    )

    assert client.list_children("") == []
    assert seen and seen[0].endswith("/me/drive/root/children")
