"""Pure, immutable domain models for download state and metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from math import isfinite
from typing import Final
from urllib.parse import urlsplit
from uuid import uuid4

from supadl.domain.enums import ChecksumAlgorithm, DownloadStatus, SegmentStatus
from supadl.domain.errors import DomainValidationError, ErrorCode

_HEX_CHARACTERS: Final = frozenset("0123456789abcdef")
_CHECKSUM_LENGTHS: Final = {
    ChecksumAlgorithm.SHA256: 64,
    ChecksumAlgorithm.SHA512: 128,
}


def _require_non_empty(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise DomainValidationError(f"{field_name} must be a string", field=field_name)
    normalized = value.strip()
    if not normalized:
        raise DomainValidationError(f"{field_name} cannot be empty", field=field_name)
    return normalized


def _require_non_negative_number(value: int | float, *, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DomainValidationError(f"{field_name} must be numeric", field=field_name)
    if not isfinite(value) or value < 0:
        raise DomainValidationError(
            f"{field_name} must be finite and non-negative",
            field=field_name,
        )


def _require_non_negative_integer(value: int, *, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise DomainValidationError(f"{field_name} must be an integer", field=field_name)
    if value < 0:
        raise DomainValidationError(f"{field_name} cannot be negative", field=field_name)


def _normalize_timestamp(value: datetime, *, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise DomainValidationError(f"{field_name} must be a datetime", field=field_name)
    if value.tzinfo is None or value.utcoffset() is None:
        raise DomainValidationError(f"{field_name} must include a timezone", field=field_name)
    return value.astimezone(UTC)


def _validate_http_url(value: str, *, field_name: str) -> str:
    normalized = _require_non_empty(value, field_name=field_name)
    try:
        parsed = urlsplit(normalized)
        port = parsed.port
    except ValueError as error:
        raise DomainValidationError(f"{field_name} is not a valid URL", field=field_name) from error
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
        raise DomainValidationError(f"{field_name} must be an HTTP or HTTPS URL", field=field_name)
    if parsed.username is not None or parsed.password is not None:
        raise DomainValidationError(
            f"{field_name} cannot contain embedded credentials",
            field=field_name,
        )
    if port is not None and not 1 <= port <= 65535:
        raise DomainValidationError(f"{field_name} contains an invalid port", field=field_name)
    return normalized


@dataclass(frozen=True, slots=True)
class DownloadSource:
    """Original URL and metadata discovered by a future probe service."""

    original_url: str
    final_url: str | None = None
    content_length: int | None = None
    mime_type: str | None = None
    etag: str | None = None
    last_modified: str | None = None
    range_supported: bool | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "original_url",
            _validate_http_url(self.original_url, field_name="original_url"),
        )
        if self.final_url is not None:
            object.__setattr__(
                self,
                "final_url",
                _validate_http_url(self.final_url, field_name="final_url"),
            )
        if self.content_length is not None:
            _require_non_negative_integer(self.content_length, field_name="content_length")
        for field_name in ("mime_type", "etag", "last_modified"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    _require_non_empty(value, field_name=field_name),
                )
        if self.range_supported is not None and not isinstance(self.range_supported, bool):
            raise DomainValidationError(
                "range_supported must be a boolean when provided",
                field="range_supported",
            )

    def to_dict(self) -> dict[str, object]:
        """Return storage-friendly primitive values."""
        return {
            "original_url": self.original_url,
            "final_url": self.final_url,
            "content_length": self.content_length,
            "mime_type": self.mime_type,
            "etag": self.etag,
            "last_modified": self.last_modified,
            "range_supported": self.range_supported,
        }


@dataclass(frozen=True, slots=True)
class ChecksumSpec:
    """A normalized user-supplied checksum expectation."""

    algorithm: ChecksumAlgorithm
    expected_digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.algorithm, ChecksumAlgorithm):
            raise DomainValidationError(
                "algorithm must be a supported checksum algorithm",
                field="algorithm",
            )
        digest = _require_non_empty(
            self.expected_digest,
            field_name="expected_digest",
        ).casefold()
        expected_length = _CHECKSUM_LENGTHS[self.algorithm]
        if len(digest) != expected_length or any(
            character not in _HEX_CHARACTERS for character in digest
        ):
            raise DomainValidationError(
                f"expected_digest must be a {expected_length}-character hexadecimal value",
                field="expected_digest",
            )
        object.__setattr__(self, "expected_digest", digest)

    def to_dict(self) -> dict[str, str]:
        return {"algorithm": self.algorithm.value, "expected_digest": self.expected_digest}


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Validated retry limits used by future transfer workers."""

    max_retries: int = 5
    base_delay_seconds: float = 0.5
    maximum_delay_seconds: float = 30.0
    jitter_ratio: float = 0.2

    def __post_init__(self) -> None:
        if (
            isinstance(self.max_retries, bool)
            or not isinstance(self.max_retries, int)
            or not 0 <= self.max_retries <= 20
        ):
            raise DomainValidationError("max_retries must be between 0 and 20", field="max_retries")
        for field_name in ("base_delay_seconds", "maximum_delay_seconds"):
            value = getattr(self, field_name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
                or not 0 < value <= 3600
            ):
                raise DomainValidationError(
                    f"{field_name} must be greater than 0 and at most 3600",
                    field=field_name,
                )
        if self.base_delay_seconds > self.maximum_delay_seconds:
            raise DomainValidationError(
                "base_delay_seconds cannot exceed maximum_delay_seconds",
                field="base_delay_seconds",
            )
        if (
            isinstance(self.jitter_ratio, bool)
            or not isinstance(self.jitter_ratio, (int, float))
            or not isfinite(self.jitter_ratio)
            or not 0 <= self.jitter_ratio <= 1
        ):
            raise DomainValidationError(
                "jitter_ratio must be between 0 and 1",
                field="jitter_ratio",
            )

    def to_dict(self) -> dict[str, int | float]:
        return {
            "max_retries": self.max_retries,
            "base_delay_seconds": self.base_delay_seconds,
            "maximum_delay_seconds": self.maximum_delay_seconds,
            "jitter_ratio": self.jitter_ratio,
        }


@dataclass(frozen=True, slots=True)
class DownloadProgress:
    """A validated snapshot of task progress and display metrics."""

    bytes_downloaded: int = 0
    total_bytes: int | None = None
    bytes_per_second: float = 0.0
    eta_seconds: float | None = None

    def __post_init__(self) -> None:
        _require_non_negative_integer(self.bytes_downloaded, field_name="bytes_downloaded")
        _require_non_negative_number(self.bytes_per_second, field_name="bytes_per_second")
        if self.total_bytes is not None:
            _require_non_negative_integer(self.total_bytes, field_name="total_bytes")
            if self.bytes_downloaded > self.total_bytes:
                raise DomainValidationError(
                    "bytes_downloaded cannot exceed total_bytes",
                    field="bytes_downloaded",
                )
        if self.eta_seconds is not None:
            _require_non_negative_number(self.eta_seconds, field_name="eta_seconds")

    def to_dict(self) -> dict[str, int | float | None]:
        return {
            "bytes_downloaded": self.bytes_downloaded,
            "total_bytes": self.total_bytes,
            "bytes_per_second": self.bytes_per_second,
            "eta_seconds": self.eta_seconds,
        }


@dataclass(frozen=True, slots=True)
class DownloadSegment:
    """One inclusive byte range and its durable resume position."""

    id: str
    download_id: str
    index: int
    start_byte: int
    end_byte: int
    next_byte: int
    status: SegmentStatus = SegmentStatus.PENDING
    retry_count: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _require_non_empty(self.id, field_name="id"))
        object.__setattr__(
            self,
            "download_id",
            _require_non_empty(self.download_id, field_name="download_id"),
        )
        for field_name in ("index", "start_byte", "end_byte", "next_byte", "retry_count"):
            value = getattr(self, field_name)
            _require_non_negative_integer(value, field_name=field_name)
        if not isinstance(self.status, SegmentStatus):
            raise DomainValidationError("status must be a SegmentStatus", field="status")
        if self.end_byte < self.start_byte:
            raise DomainValidationError("end_byte cannot be less than start_byte", field="end_byte")
        if not self.start_byte <= self.next_byte <= self.end_byte + 1:
            raise DomainValidationError(
                "next_byte must be within the segment or one byte beyond its end",
                field="next_byte",
            )
        if self.status is SegmentStatus.COMPLETED and self.next_byte != self.end_byte + 1:
            raise DomainValidationError(
                "a completed segment must have consumed its complete range",
                field="next_byte",
            )

    @property
    def bytes_downloaded(self) -> int:
        return self.next_byte - self.start_byte

    @property
    def expected_bytes(self) -> int:
        return self.end_byte - self.start_byte + 1

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "download_id": self.download_id,
            "index": self.index,
            "start_byte": self.start_byte,
            "end_byte": self.end_byte,
            "next_byte": self.next_byte,
            "bytes_downloaded": self.bytes_downloaded,
            "status": self.status.value,
            "retry_count": self.retry_count,
        }


@dataclass(frozen=True, slots=True)
class DownloadErrorInfo:
    """Sanitized error data suitable for persistence and presentation."""

    code: ErrorCode
    message: str
    retryable: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.code, ErrorCode):
            raise DomainValidationError("code must be an ErrorCode", field="code")
        object.__setattr__(self, "message", _require_non_empty(self.message, field_name="message"))
        if not isinstance(self.retryable, bool):
            raise DomainValidationError("retryable must be a boolean", field="retryable")

    def to_dict(self) -> dict[str, str | bool]:
        return {"code": self.code.value, "message": self.message, "retryable": self.retryable}


@dataclass(frozen=True, slots=True)
class DownloadTask:
    """Top-level immutable download state."""

    source: DownloadSource
    id: str = field(default_factory=lambda: str(uuid4()))
    status: DownloadStatus = DownloadStatus.CREATED
    filename: str | None = None
    destination_path: str | None = None
    temp_path: str | None = None
    priority: int = 0
    progress: DownloadProgress = field(default_factory=DownloadProgress)
    checksum: ChecksumSpec | None = None
    error: DownloadErrorInfo | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source, DownloadSource):
            raise DomainValidationError("source must be a DownloadSource", field="source")
        if not isinstance(self.status, DownloadStatus):
            raise DomainValidationError("status must be a DownloadStatus", field="status")
        if not isinstance(self.progress, DownloadProgress):
            raise DomainValidationError("progress must be DownloadProgress", field="progress")
        if self.checksum is not None and not isinstance(self.checksum, ChecksumSpec):
            raise DomainValidationError("checksum must be a ChecksumSpec", field="checksum")
        if self.error is not None and not isinstance(self.error, DownloadErrorInfo):
            raise DomainValidationError("error must be DownloadErrorInfo", field="error")
        object.__setattr__(self, "id", _require_non_empty(self.id, field_name="id"))
        if isinstance(self.priority, bool) or not isinstance(self.priority, int):
            raise DomainValidationError("priority must be an integer", field="priority")
        for field_name in ("filename", "destination_path", "temp_path"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    _require_non_empty(value, field_name=field_name),
                )

        created_at = _normalize_timestamp(self.created_at, field_name="created_at")
        updated_at = _normalize_timestamp(self.updated_at, field_name="updated_at")
        object.__setattr__(self, "created_at", created_at)
        object.__setattr__(self, "updated_at", updated_at)
        if updated_at < created_at:
            raise DomainValidationError(
                "updated_at cannot be earlier than created_at", field="updated_at"
            )

        for field_name in ("started_at", "completed_at"):
            value = getattr(self, field_name)
            if value is not None:
                normalized = _normalize_timestamp(value, field_name=field_name)
                if normalized < created_at:
                    raise DomainValidationError(
                        f"{field_name} cannot be earlier than created_at",
                        field=field_name,
                    )
                object.__setattr__(self, field_name, normalized)

        if self.status is DownloadStatus.COMPLETED and self.completed_at is None:
            raise DomainValidationError(
                "a completed task requires completed_at",
                field="completed_at",
            )
        statuses_requiring_start = {
            DownloadStatus.DOWNLOADING,
            DownloadStatus.PAUSING,
            DownloadStatus.VERIFYING,
            DownloadStatus.COMPLETED,
        }
        if self.status in statuses_requiring_start and self.started_at is None:
            raise DomainValidationError(
                f"a {self.status.value} task requires started_at",
                field="started_at",
            )
        if self.status is DownloadStatus.COMPLETED and (
            self.filename is None or self.destination_path is None
        ):
            raise DomainValidationError(
                "a completed task requires filename and destination_path",
                field="filename",
            )
        if self.status is DownloadStatus.COMPLETED:
            expected_bytes = (
                self.progress.total_bytes
                if self.progress.total_bytes is not None
                else self.source.content_length
            )
            if expected_bytes is not None and self.progress.bytes_downloaded != expected_bytes:
                raise DomainValidationError(
                    "a completed task must account for every expected byte",
                    field="progress",
                )
        if self.status is not DownloadStatus.COMPLETED and self.completed_at is not None:
            raise DomainValidationError(
                "completed_at is only valid for a completed task",
                field="completed_at",
            )
        if self.started_at is not None and self.started_at > self.updated_at:
            raise DomainValidationError(
                "started_at cannot be later than updated_at",
                field="started_at",
            )
        if self.completed_at is not None and self.completed_at > self.updated_at:
            raise DomainValidationError(
                "completed_at cannot be later than updated_at",
                field="completed_at",
            )
        if (
            self.started_at is not None
            and self.completed_at is not None
            and self.completed_at < self.started_at
        ):
            raise DomainValidationError(
                "completed_at cannot be earlier than started_at",
                field="completed_at",
            )
        if (
            self.source.content_length is not None
            and self.progress.total_bytes is not None
            and self.source.content_length != self.progress.total_bytes
        ):
            raise DomainValidationError(
                "progress total_bytes must match source content_length",
                field="progress",
            )

    def to_dict(self) -> dict[str, object]:
        """Return a nested representation containing only storage-friendly primitives."""
        return {
            "id": self.id,
            "source": self.source.to_dict(),
            "status": self.status.value,
            "filename": self.filename,
            "destination_path": self.destination_path,
            "temp_path": self.temp_path,
            "priority": self.priority,
            "progress": self.progress.to_dict(),
            "checksum": None if self.checksum is None else self.checksum.to_dict(),
            "error": None if self.error is None else self.error.to_dict(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "started_at": None if self.started_at is None else self.started_at.isoformat(),
            "completed_at": None if self.completed_at is None else self.completed_at.isoformat(),
        }
