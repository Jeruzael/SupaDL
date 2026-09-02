from __future__ import annotations

import io
import json
import logging
from collections.abc import Iterator
from typing import cast

import pytest

from supadl.observability import configure_logging, redact_headers, redact_text, redact_url


@pytest.fixture(autouse=True)
def isolated_supadl_logger() -> Iterator[None]:
    logger = logging.getLogger("supadl")
    original_handlers = list(logger.handlers)
    original_level = logger.level
    original_propagate = logger.propagate
    logger.handlers.clear()
    yield
    for handler in logger.handlers:
        handler.close()
    logger.handlers[:] = original_handlers
    logger.setLevel(original_level)
    logger.propagate = original_propagate


def _read_record(stream: io.StringIO) -> dict[str, object]:
    value = json.loads(stream.getvalue().strip())
    if not isinstance(value, dict):
        raise AssertionError("log line must contain a JSON object")
    return cast(dict[str, object], value)


def test_configure_logging_is_idempotent() -> None:
    stream = io.StringIO()

    first = configure_logging(stream=stream)
    second = configure_logging(stream=stream)
    first.info("one event")

    assert first is second
    assert len(first.handlers) == 1
    assert len(stream.getvalue().splitlines()) == 1


def test_structured_record_contains_context() -> None:
    stream = io.StringIO()
    logger = configure_logging(stream=stream)

    logger.info(
        "download queued",
        extra={"download_id": "download-123", "event": "download.queued"},
    )

    record = _read_record(stream)
    assert record["level"] == "INFO"
    assert record["logger"] == "supadl"
    assert record["message"] == "download queued"
    assert record["download_id"] == "download-123"
    assert record["event"] == "download.queued"
    assert isinstance(record["timestamp"], str)


def test_header_redaction_is_case_insensitive() -> None:
    redacted = redact_headers(
        {
            "Authorization": "Bearer auth-secret",
            "cookie": "session=cookie-secret",
            "SET-COOKIE": "session=set-cookie-secret",
            "X-Api-Key": "api-secret",
            "Content-Type": "application/octet-stream",
        }
    )

    assert redacted["Authorization"] == "[REDACTED]"
    assert redacted["cookie"] == "[REDACTED]"
    assert redacted["SET-COOKIE"] == "[REDACTED]"
    assert redacted["X-Api-Key"] == "[REDACTED]"
    assert redacted["Content-Type"] == "application/octet-stream"


def test_url_redacts_user_info_query_values_and_fragment() -> None:
    result = redact_url(
        "https://alice:user-secret@example.test:8443/file.iso?token=query-secret&name=public#fragment-secret"
    )

    assert result.startswith("https://example.test:8443/file.iso?")
    assert "token=" in result
    assert "name=" in result
    assert "alice" not in result
    assert "user-secret" not in result
    assert "query-secret" not in result
    assert "public" not in result
    assert "fragment-secret" not in result


def test_unstructured_message_redacts_header_key_and_embedded_url_secrets() -> None:
    original = (
        "Authorization: Bearer header-secret, token=message-secret "
        "url=https://example.test/file?signature=url-secret"
    )

    result = redact_text(original)

    assert "header-secret" not in result
    assert "message-secret" not in result
    assert "url-secret" not in result
    assert result == "Authorization=[REDACTED]"


def test_logger_redacts_structured_headers_url_context_and_format_arguments() -> None:
    stream = io.StringIO()
    logger = configure_logging(stream=stream)

    logger.warning(
        "request failed token=%s",
        "argument-secret",
        extra={
            "headers": {"Authorization": "Bearer header-secret", "Accept": "*/*"},
            "url": "https://example.test/file?key=query-secret",
            "context": {"nested_token": "context-secret", "attempt": 2},
        },
    )

    emitted = stream.getvalue()
    assert "argument-secret" not in emitted
    assert "header-secret" not in emitted
    assert "query-secret" not in emitted
    assert "context-secret" not in emitted

    record = _read_record(stream)
    assert record["headers"] == {"Authorization": "[REDACTED]", "Accept": "*/*"}
    assert record["context"] == {"nested_token": "[REDACTED]", "attempt": 2}


def test_exception_message_is_redacted() -> None:
    stream = io.StringIO()
    logger = configure_logging(stream=stream)

    try:
        raise RuntimeError("password=exception-secret")
    except RuntimeError:
        logger.exception("operation failed")

    emitted = stream.getvalue()
    assert "exception-secret" not in emitted
    assert "[REDACTED]" in emitted
