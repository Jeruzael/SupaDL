from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any
from urllib.parse import urlsplit

import httpx
import pytest

from supadl.config import DownloadSettings
from supadl.domain import DomainValidationError, ErrorCode, SupaDLError
from supadl.transfer import DEFAULT_USER_AGENT, ProbeService, create_http_client

_PAYLOAD = b"deterministic-probe-payload"


@dataclass(slots=True)
class _RequestRecord:
    method: str
    path: str
    range_header: str | None
    user_agent: str | None


@dataclass(slots=True)
class _FixtureState:
    base_url: str = ""
    requests: list[_RequestRecord] = field(default_factory=list)


class _ObservedStream(httpx.AsyncByteStream):
    def __init__(self) -> None:
        self.was_iterated = False
        self.was_closed = False

    async def __aiter__(self) -> AsyncIterator[bytes]:
        self.was_iterated = True
        yield _PAYLOAD

    async def aclose(self) -> None:
        self.was_closed = True


def _handler_type(state: _FixtureState) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: object) -> None:
            del format, args

        def _record(self) -> str:
            path = urlsplit(self.path).path
            state.requests.append(
                _RequestRecord(
                    method=self.command,
                    path=path,
                    range_header=self.headers.get("Range"),
                    user_agent=self.headers.get("User-Agent"),
                )
            )
            return path

        def _empty(self, status: int, **headers: str) -> None:
            self.send_response(status)
            self.send_header("Content-Length", "0")
            for name, value in headers.items():
                self.send_header(name.replace("_", "-"), value)
            self.end_headers()

        def _metadata_headers(self, *, length: int | None = len(_PAYLOAD)) -> None:
            if length is not None:
                self.send_header("Content-Length", str(length))
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header(
                "Content-Disposition",
                "attachment; filename*=UTF-8''probe%20result.bin",
            )
            self.send_header("ETag", '"fixture-v1"')
            self.send_header("Last-Modified", "Wed, 02 Sep 2026 08:00:00 GMT")
            self.send_header("Accept-Ranges", "bytes")

        def _head_metadata(self) -> None:
            self.send_response(200)
            self._metadata_headers()
            self.end_headers()

        def _range_metadata(self, *, malformed: bool = False) -> None:
            self.send_response(206)
            self.send_header("Content-Length", "1")
            value = f"bytes 1-1/{len(_PAYLOAD)}" if malformed else f"bytes 0-0/{len(_PAYLOAD)}"
            self.send_header("Content-Range", value)
            self._metadata_headers(length=None)
            self.end_headers()
            with suppress(BrokenPipeError, ConnectionResetError):
                self.wfile.write(_PAYLOAD[:1])

        def do_HEAD(self) -> None:
            path = self._record()
            if path in {"/head-rejected", "/double-fallback", "/unknown"}:
                self._empty(405)
            elif path == "/redirect":
                self._empty(302, Location="/file")
            elif path == "/loop-a":
                self._empty(302, Location="/loop-b")
            elif path == "/loop-b":
                self._empty(302, Location="/loop-a")
            elif path == "/credential-redirect":
                unsafe_url = state.base_url.replace("http://", "http://user:secret@", 1)
                self._empty(302, Location=f"{unsafe_url}/file")
            elif path == "/not-found":
                self._empty(404)
            else:
                self._head_metadata()

        def do_GET(self) -> None:
            path = self._record()
            range_header = self.headers.get("Range")
            if path == "/redirect":
                self._empty(302, Location="/file")
            elif path == "/loop-a":
                self._empty(302, Location="/loop-b")
            elif path == "/loop-b":
                self._empty(302, Location="/loop-a")
            elif path == "/credential-redirect":
                unsafe_url = state.base_url.replace("http://", "http://user:secret@", 1)
                self._empty(302, Location=f"{unsafe_url}/file")
            elif path == "/not-found":
                self._empty(404)
            elif path == "/double-fallback" and range_header is not None:
                self._empty(416)
            elif path == "/double-fallback":
                self._head_metadata()
            elif path == "/unknown":
                self.send_response(200)
                self.send_header("Connection", "close")
                self.end_headers()
            elif path == "/ignores-range":
                self._head_metadata()
            elif path == "/malformed-range":
                self._range_metadata(malformed=True)
            elif range_header == "bytes=0-0":
                self._range_metadata()
            else:
                self._head_metadata()

    return Handler


@contextmanager
def _fixture_server() -> Iterator[_FixtureState]:
    state = _FixtureState()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler_type(state))
    server.daemon_threads = True
    state.base_url = f"http://{server.server_name}:{server.server_port}"
    thread = Thread(target=server.serve_forever, name="supadl-http-fixture", daemon=True)
    thread.start()
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _settings(tmp_path: Path, **changes: object) -> DownloadSettings:
    settings = DownloadSettings(default_destination=tmp_path)
    return settings.with_updates(**changes)


@pytest.mark.asyncio
async def test_client_factory_applies_security_timeouts_redirects_and_lifecycle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    original_constructor = httpx.AsyncClient

    def recording_constructor(**kwargs: Any) -> httpx.AsyncClient:
        captured.update(kwargs)
        return original_constructor(**kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", recording_constructor)
    settings = _settings(
        tmp_path,
        connect_timeout_seconds=1.0,
        read_timeout_seconds=2.0,
        write_timeout_seconds=3.0,
        pool_timeout_seconds=4.0,
        max_redirects=7,
    )
    client = create_http_client(settings)

    assert captured["verify"] is True
    assert captured["trust_env"] is False
    assert captured["http2"] is True
    assert client.follow_redirects is True
    assert client.max_redirects == 7
    assert client.timeout.connect == 1.0
    assert client.timeout.read == 2.0
    assert client.timeout.write == 3.0
    assert client.timeout.pool == 4.0
    assert client.headers["User-Agent"] == DEFAULT_USER_AGENT
    assert client.headers["Accept-Encoding"] == "identity"
    assert not client.is_closed

    await client.aclose()
    assert client.is_closed


@pytest.mark.parametrize("user_agent", ["", "   ", "unsafe\r\nInjected: yes"])
def test_client_factory_rejects_invalid_user_agent(tmp_path: Path, user_agent: str) -> None:
    with pytest.raises(ValueError, match="user_agent"):
        create_http_client(_settings(tmp_path), user_agent=user_agent)


@pytest.mark.asyncio
async def test_probe_captures_metadata_proves_ranges_and_resolves_filename(tmp_path: Path) -> None:
    with _fixture_server() as fixture:
        async with create_http_client(_settings(tmp_path)) as client:
            result = await ProbeService(client).probe(f"{fixture.base_url}/file")
            assert not client.is_closed

    assert result.source.original_url.endswith("/file")
    assert result.source.final_url == f"{fixture.base_url}/file"
    assert result.source.content_length == len(_PAYLOAD)
    assert result.source.mime_type == "application/octet-stream"
    assert result.source.etag == '"fixture-v1"'
    assert result.source.last_modified == "Wed, 02 Sep 2026 08:00:00 GMT"
    assert result.source.range_supported is True
    assert result.filename == "probe result.bin"
    assert result.status_code == 206
    assert result.accept_ranges == "bytes"
    json.dumps(result.to_dict())
    assert [(item.method, item.range_header) for item in fixture.requests] == [
        ("HEAD", None),
        ("GET", "bytes=0-0"),
    ]
    assert {item.user_agent for item in fixture.requests} == {DEFAULT_USER_AGENT}
    assert client.is_closed


@pytest.mark.asyncio
async def test_probe_closes_responses_without_iterating_body(tmp_path: Path) -> None:
    streams: list[_ObservedStream] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        stream = _ObservedStream()
        streams.append(stream)
        headers = {
            "Content-Length": str(len(_PAYLOAD)),
            "Content-Type": "application/octet-stream",
        }
        status = 200
        if request.method == "GET":
            status = 206
            headers["Content-Length"] = "1"
            headers["Content-Range"] = f"bytes 0-0/{len(_PAYLOAD)}"
        return httpx.Response(status, headers=headers, stream=stream, request=request)

    transport = httpx.MockTransport(handler)
    async with create_http_client(_settings(tmp_path), transport=transport) as client:
        result = await ProbeService(client).probe("https://example.test/file.bin")

    assert result.source.range_supported is True
    assert len(streams) == 2
    assert all(stream.was_closed for stream in streams)
    assert not any(stream.was_iterated for stream in streams)


@pytest.mark.asyncio
async def test_probe_falls_back_when_head_is_rejected_and_follows_redirects(
    tmp_path: Path,
) -> None:
    with _fixture_server() as fixture:
        async with create_http_client(_settings(tmp_path)) as client:
            rejected = await ProbeService(client).probe(f"{fixture.base_url}/head-rejected")
            redirected = await ProbeService(client).probe(f"{fixture.base_url}/redirect")

    assert rejected.source.range_supported is True
    assert redirected.source.final_url == f"{fixture.base_url}/file"
    assert redirected.filename == "probe result.bin"


@pytest.mark.asyncio
async def test_probe_uses_streamed_plain_get_when_head_and_range_are_rejected(
    tmp_path: Path,
) -> None:
    with _fixture_server() as fixture:
        async with create_http_client(_settings(tmp_path)) as client:
            result = await ProbeService(client).probe(f"{fixture.base_url}/double-fallback")

    assert result.status_code == 200
    assert result.source.range_supported is False
    assert [item.range_header for item in fixture.requests] == [None, "bytes=0-0", None]


@pytest.mark.asyncio
async def test_accept_ranges_header_alone_does_not_prove_range_support(tmp_path: Path) -> None:
    with _fixture_server() as fixture:
        async with create_http_client(_settings(tmp_path)) as client:
            ignored = await ProbeService(client).probe(f"{fixture.base_url}/ignores-range")
            malformed = await ProbeService(client).probe(f"{fixture.base_url}/malformed-range")

    assert ignored.accept_ranges == "bytes"
    assert ignored.source.range_supported is False
    assert ignored.source.content_length == len(_PAYLOAD)
    assert malformed.source.range_supported is False
    assert malformed.source.content_length == len(_PAYLOAD)


@pytest.mark.asyncio
async def test_unknown_length_remains_eligible_for_single_stream(tmp_path: Path) -> None:
    with _fixture_server() as fixture:
        async with create_http_client(_settings(tmp_path)) as client:
            result = await ProbeService(client).probe(f"{fixture.base_url}/unknown")

    assert result.status_code == 200
    assert result.source.content_length is None
    assert result.source.range_supported is False


@pytest.mark.asyncio
async def test_probe_maps_status_and_redirect_failures_to_typed_errors(tmp_path: Path) -> None:
    with _fixture_server() as fixture:
        async with create_http_client(_settings(tmp_path, max_redirects=2)) as client:
            with pytest.raises(SupaDLError) as not_found:
                await ProbeService(client).probe(f"{fixture.base_url}/not-found")
            with pytest.raises(SupaDLError) as redirects:
                await ProbeService(client).probe(f"{fixture.base_url}/loop-a")

    assert not_found.value.code is ErrorCode.NOT_FOUND
    assert redirects.value.code is ErrorCode.REDIRECT_LIMIT_EXCEEDED


@pytest.mark.asyncio
async def test_redirect_url_is_revalidated_before_credentials_can_be_sent(tmp_path: Path) -> None:
    with _fixture_server() as fixture:
        async with create_http_client(_settings(tmp_path)) as client:
            with pytest.raises(DomainValidationError, match="embedded credentials"):
                await ProbeService(client).probe(f"{fixture.base_url}/credential-redirect")

    assert all(item.path != "/file" for item in fixture.requests)


@pytest.mark.asyncio
async def test_transport_timeouts_are_mapped_without_exposing_url(tmp_path: Path) -> None:
    async def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("secret https://example.test/file?token=value", request=request)

    transport = httpx.MockTransport(timeout_handler)
    async with create_http_client(_settings(tmp_path), transport=transport) as client:
        with pytest.raises(SupaDLError) as captured:
            await ProbeService(client).probe("https://example.test/file?token=value")

    assert captured.value.code is ErrorCode.READ_TIMEOUT
    assert "token" not in str(captured.value)
