from __future__ import annotations

import ast
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from supadl.domain import (
    ChecksumAlgorithm,
    ChecksumSpec,
    DomainValidationError,
    DownloadErrorInfo,
    DownloadProgress,
    DownloadSegment,
    DownloadSource,
    DownloadStatus,
    DownloadTask,
    ErrorCode,
    InvalidStateTransitionError,
    RetryPolicy,
    SegmentStatus,
    allowed_transitions,
    can_transition,
    transition_task,
)

NOW = datetime(2026, 9, 2, 8, 0, tzinfo=UTC)


def test_download_status_values_match_the_approved_state_machine() -> None:
    assert {status.name for status in DownloadStatus} == {
        "CREATED",
        "PROBING",
        "QUEUED",
        "DOWNLOADING",
        "PAUSING",
        "PAUSED",
        "VERIFYING",
        "COMPLETED",
        "FAILED",
        "CANCELLED",
    }


def test_segment_status_is_a_distinct_enum() -> None:
    assert SegmentStatus.__name__ != DownloadStatus.__name__
    assert id(SegmentStatus.DOWNLOADING) != id(DownloadStatus.DOWNLOADING)
    assert SegmentStatus.PENDING.value == "pending"


@pytest.mark.parametrize(
    "url",
    [
        "",
        "ftp://example.test/file.iso",
        "https:///missing-host",
        "https://user:secret@example.test/file.iso",
        "https://example.test:99999/file.iso",
    ],
)
def test_download_source_rejects_invalid_or_credential_bearing_urls(url: str) -> None:
    with pytest.raises(DomainValidationError):
        DownloadSource(original_url=url)


def test_download_source_normalizes_metadata_and_serializes() -> None:
    source = DownloadSource(
        original_url=" https://example.test/file.iso ",
        final_url="https://cdn.example.test/file.iso",
        content_length=1024,
        mime_type=" application/octet-stream ",
        etag=' "abc" ',
        range_supported=True,
    )

    assert source.original_url == "https://example.test/file.iso"
    assert source.mime_type == "application/octet-stream"
    assert source.etag == '"abc"'
    assert source.to_dict()["content_length"] == 1024


def test_checksum_spec_normalizes_hex_and_rejects_invalid_digest() -> None:
    checksum = ChecksumSpec(ChecksumAlgorithm.SHA256, "A" * 64)

    assert checksum.expected_digest == "a" * 64
    assert checksum.to_dict() == {"algorithm": "sha256", "expected_digest": "a" * 64}

    with pytest.raises(DomainValidationError, match="64-character hexadecimal"):
        ChecksumSpec(ChecksumAlgorithm.SHA256, "not-a-digest")


@pytest.mark.parametrize(
    "changes",
    [
        {"max_retries": -1},
        {"max_retries": True},
        {"base_delay_seconds": 0},
        {"maximum_delay_seconds": 3601},
        {"base_delay_seconds": 2, "maximum_delay_seconds": 1},
        {"jitter_ratio": 1.1},
        {"base_delay_seconds": float("inf")},
        {"jitter_ratio": float("nan")},
    ],
)
def test_retry_policy_rejects_invalid_limits(changes: dict[str, object]) -> None:
    with pytest.raises(DomainValidationError):
        RetryPolicy(**changes)  # type: ignore[arg-type]


def test_progress_validates_lengths_rates_and_eta() -> None:
    progress = DownloadProgress(
        bytes_downloaded=25,
        total_bytes=100,
        bytes_per_second=12.5,
        eta_seconds=6,
    )
    assert progress.to_dict()["bytes_downloaded"] == 25

    with pytest.raises(DomainValidationError, match="cannot exceed"):
        DownloadProgress(bytes_downloaded=101, total_bytes=100)
    with pytest.raises(DomainValidationError, match="numeric"):
        DownloadProgress(bytes_per_second=True)
    with pytest.raises(DomainValidationError):
        DownloadProgress(bytes_per_second=float("inf"))


def test_segment_uses_inclusive_boundaries_and_derived_progress() -> None:
    segment = DownloadSegment(
        id="segment-1",
        download_id="download-1",
        index=0,
        start_byte=10,
        end_byte=19,
        next_byte=15,
    )

    assert segment.bytes_downloaded == 5
    assert segment.expected_bytes == 10
    assert segment.to_dict()["status"] == "pending"


def test_completed_segment_requires_end_plus_one() -> None:
    with pytest.raises(DomainValidationError, match="complete range"):
        DownloadSegment(
            id="segment-1",
            download_id="download-1",
            index=0,
            start_byte=0,
            end_byte=9,
            next_byte=9,
            status=SegmentStatus.COMPLETED,
        )


def test_download_task_is_immutable_timezone_aware_and_json_serializable() -> None:
    task = DownloadTask(
        id="download-1",
        source=DownloadSource("https://example.test/file.iso", content_length=100),
        filename="file.iso",
        destination_path="C:/Downloads",
        temp_path="C:/Temp/file.part",
        progress=DownloadProgress(total_bytes=100),
        checksum=ChecksumSpec(ChecksumAlgorithm.SHA256, "a" * 64),
        error=DownloadErrorInfo(ErrorCode.NETWORK_UNAVAILABLE, "Network unavailable", True),
        created_at=NOW,
        updated_at=NOW,
    )

    serialized = task.to_dict()
    json.dumps(serialized)
    assert serialized["status"] == "created"
    assert serialized["source"] == task.source.to_dict()
    assert task.checksum is not None
    assert serialized["checksum"] == task.checksum.to_dict()

    with pytest.raises(AttributeError):
        task.status = DownloadStatus.FAILED  # type: ignore[misc]


def test_download_task_rejects_naive_or_inconsistent_timestamps() -> None:
    source = DownloadSource("https://example.test/file.iso")
    with pytest.raises(DomainValidationError, match="timezone"):
        DownloadTask(source=source, created_at=datetime(2026, 9, 2), updated_at=NOW)
    with pytest.raises(DomainValidationError, match="earlier"):
        DownloadTask(source=source, created_at=NOW, updated_at=NOW - timedelta(seconds=1))
    with pytest.raises(DomainValidationError, match="later than updated_at"):
        DownloadTask(
            source=source,
            created_at=NOW,
            updated_at=NOW,
            started_at=NOW + timedelta(seconds=1),
        )


def test_download_task_requires_matching_known_lengths() -> None:
    with pytest.raises(DomainValidationError, match="must match"):
        DownloadTask(
            source=DownloadSource("https://example.test/file.iso", content_length=10),
            progress=DownloadProgress(total_bytes=11),
        )


def test_completed_task_requires_all_known_bytes() -> None:
    with pytest.raises(DomainValidationError, match="every expected byte"):
        DownloadTask(
            source=DownloadSource("https://example.test/file.iso", content_length=10),
            status=DownloadStatus.COMPLETED,
            filename="file.iso",
            destination_path="C:/Downloads",
            progress=DownloadProgress(bytes_downloaded=9, total_bytes=10),
            created_at=NOW,
            updated_at=NOW,
            started_at=NOW,
            completed_at=NOW,
        )


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (DownloadStatus.CREATED, DownloadStatus.PROBING),
        (DownloadStatus.PROBING, DownloadStatus.QUEUED),
        (DownloadStatus.QUEUED, DownloadStatus.DOWNLOADING),
        (DownloadStatus.DOWNLOADING, DownloadStatus.PAUSING),
        (DownloadStatus.PAUSING, DownloadStatus.PAUSED),
        (DownloadStatus.PAUSED, DownloadStatus.QUEUED),
        (DownloadStatus.DOWNLOADING, DownloadStatus.VERIFYING),
        (DownloadStatus.VERIFYING, DownloadStatus.COMPLETED),
        (DownloadStatus.DOWNLOADING, DownloadStatus.FAILED),
        (DownloadStatus.FAILED, DownloadStatus.QUEUED),
    ],
)
def test_documented_state_transitions_are_legal(
    current: DownloadStatus,
    target: DownloadStatus,
) -> None:
    assert can_transition(current, target)
    assert target in allowed_transitions(current)


def test_transition_task_updates_started_and_completed_timestamps() -> None:
    task = DownloadTask(
        id="download-1",
        source=DownloadSource("https://example.test/file.iso"),
        filename="file.iso",
        destination_path="C:/Downloads",
        created_at=NOW,
        updated_at=NOW,
    )
    probing = transition_task(task, DownloadStatus.PROBING, at=NOW + timedelta(seconds=1))
    queued = transition_task(probing, DownloadStatus.QUEUED, at=NOW + timedelta(seconds=2))
    downloading = transition_task(queued, DownloadStatus.DOWNLOADING, at=NOW + timedelta(seconds=3))
    verifying = transition_task(
        downloading,
        DownloadStatus.VERIFYING,
        at=NOW + timedelta(seconds=4),
    )
    completed = transition_task(
        verifying,
        DownloadStatus.COMPLETED,
        at=NOW + timedelta(seconds=5),
    )

    assert task.status is DownloadStatus.CREATED
    assert downloading.started_at == NOW + timedelta(seconds=3)
    assert completed.completed_at == NOW + timedelta(seconds=5)
    assert completed.updated_at == completed.completed_at


def test_task_with_checksum_cannot_bypass_verification() -> None:
    task = DownloadTask(
        source=DownloadSource("https://example.test/file.iso"),
        filename="file.iso",
        destination_path="C:/Downloads",
        checksum=ChecksumSpec(ChecksumAlgorithm.SHA256, "a" * 64),
        status=DownloadStatus.DOWNLOADING,
        created_at=NOW,
        updated_at=NOW,
        started_at=NOW,
    )

    with pytest.raises(InvalidStateTransitionError):
        transition_task(task, DownloadStatus.COMPLETED, at=NOW + timedelta(seconds=1))

    verifying = transition_task(task, DownloadStatus.VERIFYING, at=NOW + timedelta(seconds=1))
    completed = transition_task(
        verifying,
        DownloadStatus.COMPLETED,
        at=NOW + timedelta(seconds=2),
    )
    assert completed.status is DownloadStatus.COMPLETED


def test_illegal_transition_raises_typed_error_without_mutating_task() -> None:
    task = DownloadTask(
        source=DownloadSource("https://example.test/file.iso"),
        created_at=NOW,
        updated_at=NOW,
    )

    with pytest.raises(InvalidStateTransitionError) as captured:
        transition_task(task, DownloadStatus.COMPLETED, at=NOW + timedelta(seconds=1))

    assert captured.value.current is DownloadStatus.CREATED
    assert captured.value.target is DownloadStatus.COMPLETED
    assert captured.value.code is ErrorCode.INVALID_STATE_TRANSITION
    assert task.status is DownloadStatus.CREATED


def test_completed_and_cancelled_states_are_terminal() -> None:
    assert not allowed_transitions(DownloadStatus.COMPLETED)
    assert not allowed_transitions(DownloadStatus.CANCELLED)


def test_transition_rejects_naive_or_older_timestamp() -> None:
    task = DownloadTask(
        source=DownloadSource("https://example.test/file.iso"),
        created_at=NOW,
        updated_at=NOW,
    )

    with pytest.raises(DomainValidationError, match="timezone"):
        transition_task(task, DownloadStatus.PROBING, at=datetime(2026, 9, 2))
    with pytest.raises(DomainValidationError, match="earlier"):
        transition_task(task, DownloadStatus.PROBING, at=NOW - timedelta(seconds=1))


def test_domain_package_has_no_infrastructure_dependencies() -> None:
    domain_directory = Path(__file__).parents[1] / "src" / "supadl" / "domain"
    forbidden_roots = {"PySide6", "httpx", "sqlite3"}
    forbidden_supadl_packages = {"supadl.config", "supadl.observability", "supadl.storage"}

    for source_path in domain_directory.glob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        imported_names = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        imported_names.update(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        assert not {name.split(".", maxsplit=1)[0] for name in imported_names} & forbidden_roots
        assert not {
            name
            for name in imported_names
            if any(name.startswith(root) for root in forbidden_supadl_packages)
        }
