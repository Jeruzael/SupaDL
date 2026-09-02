"""Structured logging with centralized, defense-in-depth secret redaction."""

from __future__ import annotations

import json
import logging
import re
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Final, TextIO
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

REDACTED: Final = "[REDACTED]"
_LOGGER_NAME: Final = "supadl"
_HANDLER_NAME: Final = "supadl-json"
_SENSITIVE_KEYS: Final = frozenset(
    {
        "api-key",
        "api_key",
        "apikey",
        "authorization",
        "cookie",
        "credential",
        "credentials",
        "password",
        "proxy-authorization",
        "secret",
        "set-cookie",
        "signature",
        "token",
        "x-api-key",
    }
)
_CONTEXT_FIELDS: Final = ("download_id", "event", "error_code", "url", "headers", "context")
_URL_PATTERN: Final = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)
_HEADER_PATTERN: Final = re.compile(
    r"(?i)\b(authorization|proxy-authorization|cookie|set-cookie|x-api-key|api-key)"
    r"\s*[:=]\s*[^\r\n]+"
)
_KEY_VALUE_PATTERN: Final = re.compile(
    r"(?i)\b(token|password|secret|signature|api[_-]?key)\s*[:=]\s*"
    r"(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)


def _normalized_key(key: object) -> str:
    return str(key).strip().casefold().replace("_", "-")


def _is_sensitive_key(key: object) -> bool:
    normalized = _normalized_key(key)
    return normalized in {_normalized_key(item) for item in _SENSITIVE_KEYS} or any(
        marker in normalized for marker in ("password", "secret", "token", "signature")
    )


def redact_headers(headers: Mapping[str, object]) -> dict[str, object]:
    """Copy headers while replacing known credential-bearing values."""
    return {
        key: REDACTED if _is_sensitive_key(key) else _redact_value(value, key=key)
        for key, value in headers.items()
    }


def redact_url(url: str) -> str:
    """Redact credentials, every query value, and fragments from an HTTP(S) URL."""
    try:
        parsed = urlsplit(url)
        if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
            return "[REDACTED_URL]"

        hostname = parsed.hostname
        rendered_host = f"[{hostname}]" if ":" in hostname else hostname
        if parsed.port is not None:
            rendered_host = f"{rendered_host}:{parsed.port}"
        redacted_query = urlencode(
            [(key, REDACTED) for key, _value in parse_qsl(parsed.query, keep_blank_values=True)]
        )
        redacted_fragment = REDACTED if parsed.fragment else ""
        return urlunsplit(
            (
                parsed.scheme.casefold(),
                rendered_host,
                parsed.path,
                redacted_query,
                redacted_fragment,
            )
        )
    except TypeError:
        return "[REDACTED_URL]"
    except ValueError:
        return "[REDACTED_URL]"


def redact_text(text: str) -> str:
    """Redact common credential forms and URLs embedded in unstructured text."""
    without_urls = _URL_PATTERN.sub(lambda match: redact_url(match.group(0)), text)
    without_headers = _HEADER_PATTERN.sub(
        lambda match: f"{match.group(1)}={REDACTED}", without_urls
    )
    return _KEY_VALUE_PATTERN.sub(lambda match: f"{match.group(1)}={REDACTED}", without_headers)


def _redact_value(value: object, *, key: object | None = None) -> object:
    if key is not None and _is_sensitive_key(key):
        return REDACTED
    if isinstance(value, str):
        if key is not None and _normalized_key(key).endswith("url"):
            return redact_url(value)
        return redact_text(value)
    if isinstance(value, Mapping):
        return {
            str(item_key): _redact_value(item_value, key=item_key)
            for item_key, item_value in value.items()
        }
    if isinstance(value, tuple):
        return tuple(_redact_value(item) for item in value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, set):
        return sorted((_redact_value(item) for item in value), key=str)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return redact_text(str(value))


class RedactingFilter(logging.Filter):
    """Sanitize message arguments and supported structured context in place."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            rendered_message = record.getMessage()
        except TypeError:
            rendered_message = f"{record.msg!s} {record.args!s}"
        except ValueError:
            rendered_message = f"{record.msg!s} {record.args!s}"
        record.msg = redact_text(rendered_message)
        record.args = ()
        for field_name in _CONTEXT_FIELDS:
            if hasattr(record, field_name):
                setattr(
                    record,
                    field_name,
                    _redact_value(getattr(record, field_name), key=field_name),
                )
        return True


class JsonFormatter(logging.Formatter):
    """Format one sanitized JSON object per log record."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_text(record.getMessage()),
        }
        for field_name in _CONTEXT_FIELDS:
            if hasattr(record, field_name):
                payload[field_name] = _redact_value(
                    getattr(record, field_name),
                    key=field_name,
                )
        if record.exc_info:
            payload["exception"] = redact_text(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)


def _managed_handler(logger: logging.Logger) -> logging.StreamHandler[Any] | None:
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler) and handler.get_name() == _HANDLER_NAME:
            return handler
    return None


def configure_logging(
    *,
    level: int = logging.INFO,
    stream: TextIO | None = None,
) -> logging.Logger:
    """Configure and return the SupaDL logger without duplicating managed handlers."""
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False

    handler = _managed_handler(logger)
    if handler is None:
        handler = logging.StreamHandler(stream if stream is not None else sys.stderr)
        handler.set_name(_HANDLER_NAME)
        logger.addHandler(handler)
    elif stream is not None and handler.stream is not stream:
        handler.setStream(stream)

    handler.setLevel(level)
    handler.setFormatter(JsonFormatter())
    if not any(isinstance(item, RedactingFilter) for item in handler.filters):
        handler.addFilter(RedactingFilter())
    return logger
