"""Safe filename extraction, sanitization, and deterministic collision naming."""

from __future__ import annotations

import re
import unicodedata
from pathlib import PurePath
from typing import Final
from urllib.parse import unquote, unquote_to_bytes, urlsplit

DEFAULT_FILENAME: Final = "download"
DEFAULT_MAXIMUM_FILENAME_LENGTH: Final = 180
_MINIMUM_FILENAME_LENGTH: Final = 8
_MAXIMUM_FILENAME_LENGTH: Final = 240
_MAXIMUM_CONTENT_DISPOSITION_LENGTH: Final = 8192
_WINDOWS_INVALID_CHARACTERS: Final = frozenset('<>:"/\\|?*')
_WINDOWS_RESERVED_NAMES: Final = frozenset(
    {
        "aux",
        "clock$",
        "con",
        "conin$",
        "conout$",
        "nul",
        "prn",
        *(f"com{index}" for index in range(1, 10)),
        *(f"lpt{index}" for index in range(1, 10)),
    }
)


def _validate_maximum_length(maximum_length: int) -> None:
    if isinstance(maximum_length, bool) or not isinstance(maximum_length, int):
        raise ValueError("maximum_length must be an integer")
    if not _MINIMUM_FILENAME_LENGTH <= maximum_length <= _MAXIMUM_FILENAME_LENGTH:
        raise ValueError(
            f"maximum_length must be between {_MINIMUM_FILENAME_LENGTH} and "
            f"{_MAXIMUM_FILENAME_LENGTH}"
        )


def _clean_candidate(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    characters = (
        "_"
        if character in _WINDOWS_INVALID_CHARACTERS
        or unicodedata.category(character).startswith("C")
        else character
        for character in normalized
    )
    return "".join(characters).strip().strip(". ").strip()


def _neutralize_reserved_name(filename: str) -> str:
    first_component = filename.split(".", maxsplit=1)[0].rstrip(" .").casefold()
    return f"_{filename}" if first_component in _WINDOWS_RESERVED_NAMES else filename


def _split_extension(filename: str) -> tuple[str, str]:
    path = PurePath(filename)
    suffix = "" if filename.startswith(".") else "".join(path.suffixes)
    stem = filename[: -len(suffix)] if suffix else filename
    return stem, suffix


def _windows_length(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def _take_windows_units(value: str, maximum_units: int) -> str:
    result: list[str] = []
    used_units = 0
    for character in value:
        character_units = 2 if ord(character) > 0xFFFF else 1
        if used_units + character_units > maximum_units:
            break
        result.append(character)
        used_units += character_units
    return "".join(result)


def _fit_filename(stem: str, suffix: str, maximum_length: int) -> str:
    if _windows_length(stem) + _windows_length(suffix) <= maximum_length:
        return f"{stem}{suffix}"
    suffix_length = _windows_length(suffix)
    if suffix and suffix_length < maximum_length:
        fitted_stem = _take_windows_units(stem, maximum_length - suffix_length).rstrip(". ")
        if fitted_stem:
            return f"{fitted_stem}{suffix}"
    return _take_windows_units(f"{stem}{suffix}", maximum_length).rstrip(". ")


def _split_header_parameters(value: str) -> list[str]:
    parameters: list[str] = []
    current: list[str] = []
    quoted = False
    escaped = False
    for character in value:
        if escaped:
            current.append(character)
            escaped = False
        elif quoted and character == "\\":
            current.append(character)
            escaped = True
        elif character == '"':
            current.append(character)
            quoted = not quoted
        elif character == ";" and not quoted:
            parameters.append("".join(current).strip())
            current = []
        else:
            current.append(character)
    parameters.append("".join(current).strip())
    return parameters


def _unquote_header_value(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped.startswith('"') and stripped.endswith('"'):
        stripped = stripped[1:-1]
        stripped = re.sub(r"\\(.)", r"\1", stripped)
    return stripped


def _decode_extended_filename(value: str) -> str | None:
    unquoted = _unquote_header_value(value)
    try:
        charset, _language, encoded = unquoted.split("'", maxsplit=2)
    except ValueError:
        return None
    if not charset or re.search(r"%(?![0-9A-Fa-f]{2})", encoded):
        return None
    try:
        return unquote_to_bytes(encoded).decode(charset, errors="strict")
    except LookupError:
        return None
    except UnicodeDecodeError:
        return None


def filename_from_content_disposition(value: str | None) -> str | None:
    """Extract an RFC 2231/5987-aware filename without trusting it as a path."""
    if (
        value is None
        or not isinstance(value, str)
        or not value.strip()
        or len(value) > _MAXIMUM_CONTENT_DISPOSITION_LENGTH
        or "\r" in value
        or "\n" in value
    ):
        return None

    regular_filenames: list[str] = []
    extended_filenames: list[str] = []
    for parameter in _split_header_parameters(value)[1:]:
        name, separator, raw_value = parameter.partition("=")
        if not separator:
            continue
        normalized_name = name.strip().casefold()
        if normalized_name == "filename*":
            decoded = _decode_extended_filename(raw_value)
            if decoded:
                extended_filenames.append(decoded)
        elif normalized_name == "filename":
            decoded = _unquote_header_value(raw_value)
            if decoded:
                regular_filenames.append(decoded)

    selected = next(iter(extended_filenames or regular_filenames), None)
    return None if selected is None else selected.strip() or None


def filename_from_url(url: str) -> str | None:
    """Extract the decoded final path component from an HTTP(S) URL."""
    try:
        parsed = urlsplit(url)
    except TypeError:
        return None
    except ValueError:
        return None
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
        return None
    candidate = unquote(parsed.path.rsplit("/", maxsplit=1)[-1]).strip()
    return candidate or None


def sanitize_filename(
    value: str | None,
    *,
    fallback: str = DEFAULT_FILENAME,
    maximum_length: int = DEFAULT_MAXIMUM_FILENAME_LENGTH,
) -> str:
    """Return a Windows-safe basename constrained to a deterministic maximum length."""
    _validate_maximum_length(maximum_length)
    fallback_candidate = _neutralize_reserved_name(_clean_candidate(fallback))
    if not fallback_candidate:
        fallback_candidate = DEFAULT_FILENAME

    candidate = _clean_candidate(value or "")
    if not candidate:
        candidate = fallback_candidate
    candidate = _neutralize_reserved_name(candidate)
    stem, suffix = _split_extension(candidate)
    fitted = _fit_filename(stem, suffix, maximum_length)
    if not fitted:
        fitted = _fit_filename(fallback_candidate, "", maximum_length)
    return _neutralize_reserved_name(fitted)


def resolve_filename(
    url: str,
    *,
    content_disposition: str | None = None,
    fallback: str = DEFAULT_FILENAME,
    maximum_length: int = DEFAULT_MAXIMUM_FILENAME_LENGTH,
) -> str:
    """Resolve and sanitize a filename using header, URL, then fallback precedence."""
    candidate = filename_from_content_disposition(content_disposition)
    if candidate is None:
        candidate = filename_from_url(url)
    return sanitize_filename(candidate, fallback=fallback, maximum_length=maximum_length)


def collision_filename(
    filename: str,
    collision_index: int,
    *,
    maximum_length: int = DEFAULT_MAXIMUM_FILENAME_LENGTH,
) -> str:
    """Return `name (n).ext` without checking or mutating the filesystem."""
    _validate_maximum_length(maximum_length)
    if isinstance(collision_index, bool) or not isinstance(collision_index, int):
        raise ValueError("collision_index must be an integer")
    if collision_index < 1:
        raise ValueError("collision_index must be at least 1")

    safe_name = sanitize_filename(filename, maximum_length=maximum_length)
    stem, suffix = _split_extension(safe_name)
    marker = f" ({collision_index})"
    available_for_stem = maximum_length - _windows_length(marker) - _windows_length(suffix)
    if available_for_stem < 1:
        suffix = ""
        available_for_stem = maximum_length - _windows_length(marker)
    if available_for_stem < 1:
        raise ValueError("maximum_length is too small for the collision suffix")
    fitted_stem = _take_windows_units(stem, available_for_stem).rstrip(". ") or _take_windows_units(
        DEFAULT_FILENAME, available_for_stem
    )
    return _neutralize_reserved_name(f"{fitted_stem}{marker}{suffix}")


def is_safe_filename(
    filename: str, *, maximum_length: int = DEFAULT_MAXIMUM_FILENAME_LENGTH
) -> bool:
    """Return whether a value is already in canonical sanitized form."""
    try:
        return bool(filename) and filename == sanitize_filename(
            filename,
            maximum_length=maximum_length,
        )
    except TypeError:
        return False
    except ValueError:
        return False
