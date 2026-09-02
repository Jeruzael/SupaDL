"""Central lifecycle transition policy for immutable download tasks."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime
from types import MappingProxyType

from supadl.domain.enums import DownloadStatus
from supadl.domain.errors import DomainValidationError, InvalidStateTransitionError
from supadl.domain.models import DownloadTask

_ALLOWED_TRANSITIONS: Mapping[DownloadStatus, frozenset[DownloadStatus]] = MappingProxyType(
    {
        DownloadStatus.CREATED: frozenset({DownloadStatus.PROBING, DownloadStatus.CANCELLED}),
        DownloadStatus.PROBING: frozenset(
            {DownloadStatus.QUEUED, DownloadStatus.FAILED, DownloadStatus.CANCELLED}
        ),
        DownloadStatus.QUEUED: frozenset(
            {DownloadStatus.DOWNLOADING, DownloadStatus.PAUSED, DownloadStatus.CANCELLED}
        ),
        DownloadStatus.DOWNLOADING: frozenset(
            {
                DownloadStatus.PAUSING,
                DownloadStatus.VERIFYING,
                DownloadStatus.COMPLETED,
                DownloadStatus.FAILED,
                DownloadStatus.CANCELLED,
            }
        ),
        DownloadStatus.PAUSING: frozenset(
            {DownloadStatus.PAUSED, DownloadStatus.FAILED, DownloadStatus.CANCELLED}
        ),
        DownloadStatus.PAUSED: frozenset(
            {DownloadStatus.QUEUED, DownloadStatus.DOWNLOADING, DownloadStatus.CANCELLED}
        ),
        DownloadStatus.VERIFYING: frozenset(
            {DownloadStatus.COMPLETED, DownloadStatus.FAILED, DownloadStatus.CANCELLED}
        ),
        DownloadStatus.FAILED: frozenset(
            {DownloadStatus.QUEUED, DownloadStatus.DOWNLOADING, DownloadStatus.CANCELLED}
        ),
        DownloadStatus.COMPLETED: frozenset(),
        DownloadStatus.CANCELLED: frozenset(),
    }
)


def allowed_transitions(status: DownloadStatus) -> frozenset[DownloadStatus]:
    """Return the immutable set of legal targets for a status."""
    return _ALLOWED_TRANSITIONS[status]


def can_transition(current: DownloadStatus, target: DownloadStatus) -> bool:
    """Return whether a lifecycle transition is legal."""
    return target in _ALLOWED_TRANSITIONS[current]


def require_transition(current: DownloadStatus, target: DownloadStatus) -> None:
    """Raise a typed error when a lifecycle transition is illegal."""
    if not can_transition(current, target):
        raise InvalidStateTransitionError(current, target)


def transition_task(
    task: DownloadTask,
    target: DownloadStatus,
    *,
    at: datetime | None = None,
) -> DownloadTask:
    """Return a validated task snapshot after one legal transition."""
    require_transition(task.status, target)
    transition_time = datetime.now(UTC) if at is None else at
    if not isinstance(transition_time, datetime):
        raise DomainValidationError("transition timestamp must be a datetime", field="at")
    if transition_time.tzinfo is None or transition_time.utcoffset() is None:
        raise DomainValidationError("transition timestamp must include a timezone", field="at")
    transition_time = transition_time.astimezone(UTC)
    if transition_time < task.updated_at:
        raise DomainValidationError(
            "transition timestamp cannot be earlier than the current task state",
            field="at",
        )
    if (
        target is DownloadStatus.COMPLETED
        and task.status is DownloadStatus.DOWNLOADING
        and task.checksum is not None
    ):
        raise InvalidStateTransitionError(task.status, target)

    started_at = task.started_at
    if target is DownloadStatus.DOWNLOADING and started_at is None:
        started_at = transition_time
    completed_at = transition_time if target is DownloadStatus.COMPLETED else None
    return replace(
        task,
        status=target,
        updated_at=transition_time,
        started_at=started_at,
        completed_at=completed_at,
    )
