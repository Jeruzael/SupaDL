"""Metadata probing that never consumes or retains a complete response body."""

from __future__ import annotations

import re
import socket
import ssl
from dataclasses import dataclass
from typing import Final

import httpx

from supadl.domain import DownloadSource, ErrorCode, SupaDLError
from supadl.storage import DEFAULT_MAXIMUM_FILENAME_LENGTH, resolve_filename

_CONTENT_RANGE_PATTERN: Final = re.compile(
    r"bytes\s+(?P<start>\d+)-(?P<end>\d+)/(?P<total>\d+)",
    re.IGNORECASE,
)
_RANGE_REJECTION_STATUSES: Final = frozenset({400, 405, 416, 501})


@dataclass(frozen=True, slots=True)
class ProbeResult:
    """Serializable metadata produced by a successful probe."""

    source: DownloadSource
    filename: str
    status_code: int
    content_disposition: str | None
    accept_ranges: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source.to_dict(),
            "filename": self.filename,
            "status_code": self.status_code,
            "content_disposition": self.content_disposition,
            "accept_ranges": self.accept_ranges,
        }


@dataclass(frozen=True, slots=True)
class _ResponseMetadata:
    status_code: int
    final_url: str
    headers: httpx.Headers


def _optional_header(headers: httpx.Headers, name: str) -> str | None:
    value = headers.get(name)
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _content_length(headers: httpx.Headers) -> int | None:
    value = _optional_header(headers, "Content-Length")
    if value is None or not value.isdecimal():
        return None
    return int(value)


def _range_total(response: _ResponseMetadata) -> int | None:
    if response.status_code != 206:
        return None
    value = _optional_header(response.headers, "Content-Range")
    if value is None:
        return None
    match = _CONTENT_RANGE_PATTERN.fullmatch(value)
    if match is None:
        return None
    start = int(match.group("start"))
    end = int(match.group("end"))
    total = int(match.group("total"))
    response_length = _content_length(response.headers)
    content_encoding = _optional_header(response.headers, "Content-Encoding")
    if (
        start != 0
        or end != 0
        or total < 1
        or (response_length is not None and response_length != 1)
        or (content_encoding is not None and content_encoding.casefold() != "identity")
    ):
        return None
    return total


def _iter_exception_chain(error: BaseException) -> tuple[BaseException, ...]:
    chain: list[BaseException] = []
    current: BaseException | None = error
    while current is not None and current not in chain:
        chain.append(current)
        current = current.__cause__ or current.__context__
    return tuple(chain)


def _map_transport_error(error: httpx.HTTPError) -> SupaDLError:
    if isinstance(error, httpx.TooManyRedirects):
        return SupaDLError(
            "the server exceeded the configured redirect limit",
            code=ErrorCode.REDIRECT_LIMIT_EXCEEDED,
        )
    if isinstance(error, (httpx.ConnectTimeout, httpx.PoolTimeout)):
        return SupaDLError("the connection timed out", code=ErrorCode.CONNECT_TIMEOUT)
    if isinstance(error, httpx.ReadTimeout):
        return SupaDLError("the server response timed out", code=ErrorCode.READ_TIMEOUT)

    chain = _iter_exception_chain(error)
    if any(isinstance(item, ssl.SSLError) for item in chain):
        return SupaDLError("TLS certificate validation failed", code=ErrorCode.TLS_ERROR)
    if any(isinstance(item, socket.gaierror) for item in chain):
        return SupaDLError("the server name could not be resolved", code=ErrorCode.DNS_FAILURE)
    if isinstance(error, httpx.NetworkError):
        return SupaDLError("the server could not be reached", code=ErrorCode.NETWORK_UNAVAILABLE)
    return SupaDLError("the HTTP request failed", code=ErrorCode.HTTP_CLIENT_ERROR)


def _status_error(status_code: int) -> SupaDLError:
    if status_code == 401:
        return SupaDLError("the server requires authorization", code=ErrorCode.UNAUTHORIZED)
    if status_code == 403:
        return SupaDLError("the server denied access", code=ErrorCode.FORBIDDEN)
    if status_code == 404:
        return SupaDLError("the requested resource was not found", code=ErrorCode.NOT_FOUND)
    if status_code == 429:
        return SupaDLError("the server rate limit was reached", code=ErrorCode.RATE_LIMITED)
    if 500 <= status_code <= 599:
        return SupaDLError(
            "the server could not complete the request",
            code=ErrorCode.HTTP_SERVER_ERROR,
            context={"status_code": status_code},
        )
    return SupaDLError(
        "the server rejected the request",
        code=ErrorCode.HTTP_CLIENT_ERROR,
        context={"status_code": status_code},
    )


async def _request_metadata(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
) -> _ResponseMetadata:
    try:
        async with client.stream(
            method,
            url,
            headers=headers,
            follow_redirects=True,
        ) as response:
            return _ResponseMetadata(
                status_code=response.status_code,
                final_url=str(response.url),
                headers=httpx.Headers(response.headers),
            )
    except httpx.HTTPError as error:
        raise _map_transport_error(error) from error


def _is_success(response: _ResponseMetadata) -> bool:
    return 200 <= response.status_code <= 299


class ProbeService:
    """Probe HTTP metadata with an injected client owned by the caller."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        maximum_filename_length: int = DEFAULT_MAXIMUM_FILENAME_LENGTH,
    ) -> None:
        if not isinstance(client, httpx.AsyncClient):
            raise TypeError("client must be an httpx.AsyncClient")
        self._client = client
        self._maximum_filename_length = maximum_filename_length

    async def probe(self, url: str) -> ProbeResult:
        """Return trusted probe metadata without downloading the response body."""
        original_source = DownloadSource(original_url=url)
        head = await _request_metadata(self._client, "HEAD", original_source.original_url)

        range_response = await _request_metadata(
            self._client,
            "GET",
            original_source.original_url,
            headers={"Range": "bytes=0-0"},
        )
        metadata_response = range_response
        if not _is_success(range_response):
            if range_response.status_code not in _RANGE_REJECTION_STATUSES:
                raise _status_error(range_response.status_code)
            if _is_success(head):
                metadata_response = head
            else:
                metadata_response = await _request_metadata(
                    self._client,
                    "GET",
                    original_source.original_url,
                )

        if not _is_success(metadata_response):
            raise _status_error(metadata_response.status_code)

        range_total = _range_total(range_response)
        head_length = _content_length(head.headers) if _is_success(head) else None
        content_length: int | None
        if range_total is not None:
            content_length = range_total
        elif metadata_response.status_code == 206:
            content_length = head_length
        else:
            content_length = _content_length(metadata_response.headers)
            if content_length is None:
                content_length = head_length

        content_disposition = _optional_header(
            metadata_response.headers,
            "Content-Disposition",
        ) or (_optional_header(head.headers, "Content-Disposition") if _is_success(head) else None)
        accept_ranges = _optional_header(metadata_response.headers, "Accept-Ranges") or (
            _optional_header(head.headers, "Accept-Ranges") if _is_success(head) else None
        )
        mime_type = _optional_header(metadata_response.headers, "Content-Type") or (
            _optional_header(head.headers, "Content-Type") if _is_success(head) else None
        )
        etag = _optional_header(metadata_response.headers, "ETag") or (
            _optional_header(head.headers, "ETag") if _is_success(head) else None
        )
        last_modified = _optional_header(metadata_response.headers, "Last-Modified") or (
            _optional_header(head.headers, "Last-Modified") if _is_success(head) else None
        )
        source = DownloadSource(
            original_url=original_source.original_url,
            final_url=metadata_response.final_url,
            content_length=content_length,
            mime_type=mime_type,
            etag=etag,
            last_modified=last_modified,
            range_supported=range_total is not None,
        )
        return ProbeResult(
            source=source,
            filename=resolve_filename(
                source.final_url or source.original_url,
                content_disposition=content_disposition,
                maximum_length=self._maximum_filename_length,
            ),
            status_code=metadata_response.status_code,
            content_disposition=content_disposition,
            accept_ranges=accept_ranges,
        )
