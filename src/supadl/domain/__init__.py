"""Pure domain models, errors, enums, and policies."""

from supadl.domain.enums import ChecksumAlgorithm, DownloadStatus, SegmentStatus
from supadl.domain.errors import (
    DomainValidationError,
    ErrorCode,
    InvalidStateTransitionError,
    SupaDLError,
)
from supadl.domain.models import (
    ChecksumSpec,
    DownloadErrorInfo,
    DownloadProgress,
    DownloadSegment,
    DownloadSource,
    DownloadTask,
    RetryPolicy,
)
from supadl.domain.policies import (
    allowed_transitions,
    can_transition,
    require_transition,
    transition_task,
)

__all__ = [
    "ChecksumAlgorithm",
    "ChecksumSpec",
    "DomainValidationError",
    "DownloadErrorInfo",
    "DownloadProgress",
    "DownloadSegment",
    "DownloadSource",
    "DownloadStatus",
    "DownloadTask",
    "ErrorCode",
    "InvalidStateTransitionError",
    "RetryPolicy",
    "SegmentStatus",
    "SupaDLError",
    "allowed_transitions",
    "can_transition",
    "require_transition",
    "transition_task",
]
