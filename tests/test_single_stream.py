from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlsplit

import httpx
import pytest

from supadl.config import DownloadSettings
from supadl.domain import DownloadSource, ErrorCode, SupaDLError
from supadl.storage import PartialFileWriter
from supadl.transfer import SingleStreamWorker, create_http_client

_PAYLOAD = bytes(range(256)) * 1024
_ETAG = '"single-stream-v1"'
_LAST_MODIFIED = "Wed, 02 Sep 2026 09:00:00 GMT"


@dataclass(slots=True)
class _FixtureState:
    base_url: str = ""
    requested_paths: list[str] = field(default_factory=list)


def _handler_type(state: _FixtureState) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: object) -> None:
            del format, args

        def _begin_response(
            self,
            *,
            content_length: int | None,
            etag: str = _ETAG,
            content_encoding: str | None = None,
        ) -> None:
            self.send_response(200)
            if content_length is not None:
                self.send_header("Content-Length", str(content_length))
            else:
                self.send_header("Connection", "close")
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("ETag", etag)
            self.send_header("Last-Modified", _LAST_MODIFIED)
            if content_encoding is not None:
                self.send_header("Content-Encoding", content_encoding)
            self.end_headers()

        def _write(self, content: bytes) -> None:
            with suppress(BrokenPipeError, ConnectionResetError):
                self.wfile.write(content)

        def do_GET(self) -> None:
            path = urlsplit(self.path).path
            state.requested_paths.append(path)
            if path == "/not-found":
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.end_headers()
            elif path == "/redirect":
                self.send_response(302)
                self.send_header("Location", "/ok")
                self.send_header("Content-Length", "0")
                self.end_headers()
            elif path == "/short":
                self._begin_response(content_length=len(_PAYLOAD))
                self._write(_PAYLOAD[:-17])
                self.close_connection = True
            elif path == "/extra":
                self._begin_response(content_length=None)
                self._write(_PAYLOAD + b"unexpected")
            elif path == "/header-mismatch":
                self._begin_response(content_length=len(_PAYLOAD) + 1)
                self._write(_PAYLOAD)
            elif path == "/encoded":
                self._begin_response(content_length=len(_PAYLOAD), content_encoding="gzip")
                self._write(_PAYLOAD)
            elif path == "/changed-etag":
                self._begin_response(content_length=len(_PAYLOAD), etag='"changed"')
                self._write(_PAYLOAD)
            elif path == "/unknown":
                self._begin_response(content_length=None)
                self._write(_PAYLOAD)
            elif path == "/zero":
                self._begin_response(content_length=0)
            else:
                self._begin_response(content_length=len(_PAYLOAD))
                self._write(_PAYLOAD)

    return Handler


@contextmanager
def _fixture_server() -> Iterator[_FixtureState]:
    state = _FixtureState()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler_type(state))
    server.daemon_threads = True
    state.base_url = f"http://{server.server_name}:{server.server_port}"
    thread = Thread(target=server.serve_forever, name="supadl-transfer-fixture", daemon=True)
    thread.start()
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _settings(tmp_path: Path) -> DownloadSettings:
    return DownloadSettings(default_destination=tmp_path)


def _source(
    url: str,
    *,
    content_length: int | None = len(_PAYLOAD),
    etag: str | None = _ETAG,
) -> DownloadSource:
    return DownloadSource(
        original_url=url,
        final_url=url,
        content_length=content_length,
        etag=etag,
        last_modified=_LAST_MODIFIED,
    )


@pytest.mark.asyncio
async def test_single_stream_writes_exact_partial_length_and_sha256(tmp_path: Path) -> None:
    with _fixture_server() as fixture:
        url = f"{fixture.base_url}/ok"
        partial_path = tmp_path / "fixture.bin.supadl.part"
        async with create_http_client(_settings(tmp_path)) as client:
            result = await SingleStreamWorker(
                client,
                PartialFileWriter(tmp_path),
                chunk_size=4096,
            ).download(_source(url), partial_path)

    assert result.partial_path == partial_path.resolve()
    assert result.bytes_written == len(_PAYLOAD)
    assert result.sha256_digest == sha256(_PAYLOAD).hexdigest()
    assert partial_path.read_bytes() == _PAYLOAD
    assert not (tmp_path / "fixture.bin").exists()
    json.dumps(result.to_dict())
    assert client.is_closed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("endpoint", "content_length"),
    [("unknown", None), ("zero", 0)],
)
async def test_single_stream_supports_unknown_and_zero_lengths(
    tmp_path: Path,
    endpoint: str,
    content_length: int | None,
) -> None:
    with _fixture_server() as fixture:
        url = f"{fixture.base_url}/{endpoint}"
        partial_path = tmp_path / f"{endpoint}.supadl.part"
        async with create_http_client(_settings(tmp_path)) as client:
            result = await SingleStreamWorker(client, PartialFileWriter(tmp_path)).download(
                _source(url, content_length=content_length),
                partial_path,
            )

    expected = b"" if endpoint == "zero" else _PAYLOAD
    assert result.bytes_written == len(expected)
    assert result.sha256_digest == sha256(expected).hexdigest()
    assert partial_path.read_bytes() == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ["short", "extra", "header-mismatch"])
async def test_length_mismatches_never_produce_a_final_file(
    tmp_path: Path,
    endpoint: str,
) -> None:
    with _fixture_server() as fixture:
        url = f"{fixture.base_url}/{endpoint}"
        partial_path = tmp_path / f"{endpoint}.supadl.part"
        async with create_http_client(_settings(tmp_path)) as client:
            with pytest.raises(SupaDLError) as captured:
                await SingleStreamWorker(client, PartialFileWriter(tmp_path)).download(
                    _source(url),
                    partial_path,
                )

    assert captured.value.code is ErrorCode.CONTENT_LENGTH_MISMATCH
    assert not (tmp_path / endpoint).exists()
    if partial_path.exists():
        assert partial_path.stat().st_size <= len(_PAYLOAD)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("endpoint", "expected_code"),
    [
        ("not-found", ErrorCode.NOT_FOUND),
        ("encoded", ErrorCode.SOURCE_CHANGED),
        ("changed-etag", ErrorCode.SOURCE_CHANGED),
        ("redirect", ErrorCode.SOURCE_CHANGED),
    ],
)
async def test_invalid_response_is_typed_and_never_finalized(
    tmp_path: Path,
    endpoint: str,
    expected_code: ErrorCode,
) -> None:
    with _fixture_server() as fixture:
        url = f"{fixture.base_url}/{endpoint}"
        partial_path = tmp_path / f"{endpoint}.supadl.part"
        async with create_http_client(_settings(tmp_path)) as client:
            with pytest.raises(SupaDLError) as captured:
                await SingleStreamWorker(client, PartialFileWriter(tmp_path)).download(
                    _source(url),
                    partial_path,
                )

    assert captured.value.code is expected_code
    assert not partial_path.exists()


@pytest.mark.asyncio
async def test_existing_partial_is_preserved_without_network_request(tmp_path: Path) -> None:
    partial_path = tmp_path / "existing.supadl.part"
    partial_path.write_bytes(b"owned data")

    with _fixture_server() as fixture:
        url = f"{fixture.base_url}/ok"
        async with create_http_client(_settings(tmp_path)) as client:
            with pytest.raises(SupaDLError) as captured:
                await SingleStreamWorker(client, PartialFileWriter(tmp_path)).download(
                    _source(url),
                    partial_path,
                )

    assert captured.value.code is ErrorCode.FILE_CONFLICT
    assert partial_path.read_bytes() == b"owned data"
    assert fixture.requested_paths == []


@pytest.mark.parametrize(
    "partial_path",
    [
        Path("relative.supadl.part"),
        Path("C:/outside/final.bin"),
    ],
)
def test_partial_writer_rejects_relative_or_non_part_paths(
    tmp_path: Path,
    partial_path: Path,
) -> None:
    writer = PartialFileWriter(tmp_path)
    with pytest.raises(ValueError, match="partial_path"):
        writer.validate_target(partial_path)


def test_partial_writer_rejects_paths_outside_temporary_root(tmp_path: Path) -> None:
    temporary_root = tmp_path / "temporary"
    outside_root = tmp_path / "outside"
    temporary_root.mkdir()
    outside_root.mkdir()

    with pytest.raises(ValueError, match="temporary_root"):
        PartialFileWriter(temporary_root).validate_target(outside_root / "escape.supadl.part")


class _ClosingStream(httpx.AsyncByteStream):
    def __init__(self) -> None:
        self.closed = False

    async def __aiter__(self) -> AsyncIterator[bytes]:
        yield _PAYLOAD
        yield b"extra"

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_response_and_partial_file_close_after_stream_failure(tmp_path: Path) -> None:
    stream = _ClosingStream()

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=stream, request=request)

    url = "https://example.test/file.bin"
    partial_path = tmp_path / "failure.supadl.part"
    async with create_http_client(
        _settings(tmp_path),
        transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(SupaDLError) as captured:
            await SingleStreamWorker(client, PartialFileWriter(tmp_path)).download(
                _source(url),
                partial_path,
            )

    assert captured.value.code is ErrorCode.CONTENT_LENGTH_MISMATCH
    assert stream.closed
    with partial_path.open("ab") as handle:
        handle.write(b"")


@pytest.mark.parametrize("chunk_size", [0, -1, True, 8 * 1024 * 1024 + 1])
@pytest.mark.asyncio
async def test_single_stream_rejects_unbounded_chunk_sizes(
    tmp_path: Path,
    chunk_size: object,
) -> None:
    async def unused_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request)

    async with create_http_client(
        _settings(tmp_path),
        transport=httpx.MockTransport(unused_handler),
    ) as client:
        with pytest.raises(ValueError, match="chunk_size"):
            SingleStreamWorker(
                client,
                PartialFileWriter(tmp_path),
                chunk_size=chunk_size,  # type: ignore[arg-type]
            )
