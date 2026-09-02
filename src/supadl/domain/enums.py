"""Pure domain enumerations."""

from __future__ import annotations

from enum import Enum


class DownloadStatus(Enum):
    """Lifecycle states for a download task."""

    CREATED = "created"
    PROBING = "probing"
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    PAUSING = "pausing"
    PAUSED = "paused"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SegmentStatus(Enum):
    """Lifecycle states for one byte-range segment."""

    PENDING = "pending"
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ChecksumAlgorithm(Enum):
    """Checksum algorithms supported by the first public beta."""

    SHA256 = "sha256"
    SHA512 = "sha512"
