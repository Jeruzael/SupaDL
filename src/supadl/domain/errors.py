"""Typed domain errors that are safe to handle above the domain layer."""

from __future__ import annotations

from enum import Enum
from typing import Any

from supadl.domain.enums import DownloadStatus


class ErrorCode(Enum):
    """Stable machine-readable error codes."""

    INVALID_MODEL = "invalid_model"
    INVALID_STATE_TRANSITION = "invalid_state_transition"
    NETWORK_UNAVAILABLE = "network_unavailable"
    DNS_FAILURE = "dns_failure"
    CONNECT_TIMEOUT = "connect_timeout"
    READ_TIMEOUT = "read_timeout"
    TLS_ERROR = "tls_error"
    HTTP_CLIENT_ERROR = "http_client_error"
    HTTP_SERVER_ERROR = "http_server_error"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    RATE_LIMITED = "rate_limited"
    RANGE_UNSUPPORTED = "range_unsupported"
    SOURCE_CHANGED = "source_changed"
    DISK_FULL = "disk_full"
    PERMISSION_DENIED = "permission_denied"
    FILE_CONFLICT = "file_conflict"
    CHECKSUM_MISMATCH = "checksum_mismatch"
    CANCELLED_BY_USER = "cancelled_by_user"


class SupaDLError(Exception):
    """Base exception carrying a stable code and structured context."""

    code: ErrorCode

    def __init__(
        self,
        message: str,
        *,
        code: ErrorCode,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.context = {} if context is None else dict(context)


class DomainValidationError(SupaDLError, ValueError):
    """Raised when a domain value violates an invariant."""

    def __init__(self, message: str, *, field: str | None = None) -> None:
        context = {} if field is None else {"field": field}
        super().__init__(message, code=ErrorCode.INVALID_MODEL, context=context)
        self.field = field


class InvalidStateTransitionError(SupaDLError):
    """Raised when a task attempts an illegal lifecycle transition."""

    def __init__(self, current: DownloadStatus, target: DownloadStatus) -> None:
        super().__init__(
            f"cannot transition download from {current.value} to {target.value}",
            code=ErrorCode.INVALID_STATE_TRANSITION,
            context={"current_status": current.value, "target_status": target.value},
        )
        self.current = current
        self.target = target
