"""Reliable bounded-memory single-stream transfer to partial storage."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Final

import httpx

from supadl.domain import DownloadSource, ErrorCode, SupaDLError
from supadl.storage.writer import PartialFileWriter
from supadl.transfer.errors import http_status_error, map_transport_error

DEFAULT_TRANSFER_CHUNK_SIZE: Final = 64 * 1024
_MAXIMUM_TRANSFER_CHUNK_SIZE: Final = 8 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class TransferResult:
    """Validated partial-file output from one complete single-stream response."""

    partial_path: Path
    bytes_written: int
    sha256_digest: str

    def to_dict(self) -> dict[str, object]:
        return {
            "partial_path": str(self.partial_path),
            "bytes_written": self.bytes_written,
            "sha256_digest": self.sha256_digest,
        }


def _content_length(headers: httpx.Headers) -> int | None:
    value = headers.get("Content-Length")
    if value is None:
        return None
    normalized = value.strip()
    if not normalized.isdecimal():
        return None
    return int(normalized)


def _length_error(expected: int, actual: int) -> SupaDLError:
    return SupaDLError(
        "the response length did not match the probed resource",
        code=ErrorCode.CONTENT_LENGTH_MISMATCH,
        context={"expected_bytes": expected, "actual_bytes": actual},
    )


class SingleStreamWorker:
    """Stream one fresh representation to a new contained partial file."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        partial_writer: PartialFileWriter,
        *,
        chunk_size: int = DEFAULT_TRANSFER_CHUNK_SIZE,
    ) -> None:
        if not isinstance(client, httpx.AsyncClient):
            raise TypeError("client must be an httpx.AsyncClient")
        if not isinstance(partial_writer, PartialFileWriter):
            raise TypeError("partial_writer must be a PartialFileWriter")
        if (
            isinstance(chunk_size, bool)
            or not isinstance(chunk_size, int)
            or not 1 <= chunk_size <= _MAXIMUM_TRANSFER_CHUNK_SIZE
        ):
            raise ValueError("chunk_size must be between 1 and 8388608 bytes")
        self._client = client
        self._partial_writer = partial_writer
        self._chunk_size = chunk_size

    async def download(self, source: DownloadSource, partial_path: Path) -> TransferResult:
        """Download a previously probed source without exposing a final destination file."""
        if not isinstance(source, DownloadSource):
            raise TypeError("source must be DownloadSource")
        if source.final_url is None:
            raise ValueError("source.final_url is required before transfer")

        resolved_path = self._partial_writer.validate_target(partial_path)
        expected_url = httpx.URL(source.final_url)
        expected_length = source.content_length
        bytes_written = 0
        digest = sha256()

        try:
            async with self._client.stream(
                "GET",
                source.final_url,
                follow_redirects=True,
            ) as response:
                if response.status_code != 200:
                    raise http_status_error(response.status_code)
                if response.url != expected_url:
                    raise SupaDLError(
                        "the source location changed after probing",
                        code=ErrorCode.SOURCE_CHANGED,
                    )
                content_encoding = response.headers.get("Content-Encoding")
                if (
                    content_encoding is not None
                    and content_encoding.strip().casefold() != "identity"
                ):
                    raise SupaDLError(
                        "the server transformed the probed representation",
                        code=ErrorCode.SOURCE_CHANGED,
                    )
                response_length = _content_length(response.headers)
                if (
                    expected_length is not None
                    and response_length is not None
                    and response_length != expected_length
                ):
                    raise _length_error(expected_length, response_length)
                if expected_length is None:
                    expected_length = response_length

                response_etag = response.headers.get("ETag")
                if (
                    source.etag is not None
                    and response_etag is not None
                    and response_etag != source.etag
                ):
                    raise SupaDLError(
                        "the source validator changed after probing",
                        code=ErrorCode.SOURCE_CHANGED,
                    )
                response_modified = response.headers.get("Last-Modified")
                if (
                    source.last_modified is not None
                    and response_modified is not None
                    and response_modified != source.last_modified
                ):
                    raise SupaDLError(
                        "the source validator changed after probing",
                        code=ErrorCode.SOURCE_CHANGED,
                    )

                with self._partial_writer.open_new(resolved_path) as partial_file:
                    async for chunk in response.aiter_raw(chunk_size=self._chunk_size):
                        if not chunk:
                            continue
                        next_total = bytes_written + len(chunk)
                        if expected_length is not None and next_total > expected_length:
                            raise _length_error(expected_length, next_total)
                        written = partial_file.write(chunk)
                        if written != len(chunk):
                            raise SupaDLError(
                                "partial storage accepted an incomplete write",
                                code=ErrorCode.FILE_WRITE_ERROR,
                            )
                        digest.update(chunk)
                        bytes_written = next_total
        except SupaDLError:
            raise
        except httpx.RemoteProtocolError as error:
            if expected_length is not None:
                raise _length_error(expected_length, bytes_written) from error
            raise map_transport_error(error) from error
        except httpx.HTTPError as error:
            raise map_transport_error(error) from error

        if expected_length is not None and bytes_written != expected_length:
            raise _length_error(expected_length, bytes_written)
        return TransferResult(
            partial_path=resolved_path,
            bytes_written=bytes_written,
            sha256_digest=digest.hexdigest(),
        )
