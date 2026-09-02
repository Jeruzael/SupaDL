from __future__ import annotations

from pathlib import PurePath

import pytest

from supadl.storage import (
    collision_filename,
    filename_from_content_disposition,
    filename_from_url,
    is_safe_filename,
    resolve_filename,
    sanitize_filename,
)


def test_content_disposition_extracts_quoted_filename() -> None:
    assert (
        filename_from_content_disposition('attachment; filename="quarter; final.pdf"')
        == "quarter; final.pdf"
    )


def test_content_disposition_prefers_valid_extended_filename() -> None:
    header = "attachment; filename=plain.txt; filename*=UTF-8''%E2%82%ACrates.txt"

    assert filename_from_content_disposition(header) == "€rates.txt"


def test_content_disposition_falls_back_when_extended_value_is_invalid() -> None:
    header = "attachment; filename=fallback.txt; filename*=UTF-8''bad%ZZname.txt"

    assert filename_from_content_disposition(header) == "fallback.txt"


@pytest.mark.parametrize(
    "header", [None, "", "attachment", "attachment; filename=x\r\nInjected: y"]
)
def test_content_disposition_without_safe_filename_returns_none(header: str | None) -> None:
    assert filename_from_content_disposition(header) is None


def test_filename_from_url_decodes_only_the_last_path_component() -> None:
    assert filename_from_url("https://example.test/path/report%20final.pdf?token=secret") == (
        "report final.pdf"
    )
    assert filename_from_url("https://example.test/path/") is None
    assert filename_from_url("ftp://example.test/file.zip") is None


def test_resolve_filename_uses_header_then_url_then_fallback() -> None:
    url = "https://example.test/url-name.zip"

    assert resolve_filename(url, content_disposition="attachment; filename=header-name.zip") == (
        "header-name.zip"
    )
    assert resolve_filename(url, content_disposition="attachment") == "url-name.zip"
    assert resolve_filename("https://example.test/", fallback="safe-download") == "safe-download"


@pytest.mark.parametrize(
    "unsafe_name",
    [
        "../../etc/passwd",
        "..\\..\\Windows\\system.ini",
        "C:\\Windows\\system32\\cmd.exe",
        "\\\\server\\share\\payload.exe",
        "folder/file.txt",
        "name\x00with\x1fcontrol.txt",
        '<bad>:"name"|?*.txt',
    ],
)
def test_sanitize_filename_neutralizes_paths_and_invalid_characters(unsafe_name: str) -> None:
    result = sanitize_filename(unsafe_name)

    assert result
    assert len(result) <= 180
    assert "/" not in result
    assert "\\" not in result
    assert ":" not in result
    assert PurePath(result).name == result
    assert is_safe_filename(result)


@pytest.mark.parametrize(
    ("unsafe_name", "expected"),
    [
        ("CON", "_CON"),
        ("prn.txt", "_prn.txt"),
        ("LPT9.log", "_LPT9.log"),
        ("nul .txt", "_nul .txt"),
    ],
)
def test_windows_reserved_names_are_neutralized(unsafe_name: str, expected: str) -> None:
    assert sanitize_filename(unsafe_name) == expected


@pytest.mark.parametrize("empty_name", [None, "", "   ", ".", "..", "... "])
def test_empty_or_dot_filename_uses_safe_fallback(empty_name: str | None) -> None:
    assert sanitize_filename(empty_name) == "download"


def test_unicode_is_normalized_to_nfkc() -> None:
    assert sanitize_filename("\uff32\uff25\uff30\uff2f\uff32\uff34.txt") == "REPORT.txt"


def test_maximum_length_preserves_multi_part_extension() -> None:
    result = sanitize_filename(f"{'a' * 200}.tar.gz", maximum_length=40)

    assert len(result) == 40
    assert result.endswith(".tar.gz")
    assert is_safe_filename(result, maximum_length=40)


def test_maximum_length_counts_astral_unicode_as_two_windows_units() -> None:
    rocket = "\U0001f680"
    result = sanitize_filename(f"{rocket * 100}.txt", maximum_length=40)

    assert len(result.encode("utf-16-le")) // 2 <= 40
    assert result.endswith(".txt")


@pytest.mark.parametrize("maximum_length", [0, 7, 241, True])
def test_invalid_maximum_length_is_rejected(maximum_length: int) -> None:
    with pytest.raises(ValueError, match="maximum_length"):
        sanitize_filename("file.txt", maximum_length=maximum_length)


def test_collision_filename_is_deterministic_and_preserves_extension() -> None:
    assert collision_filename("archive.tar.gz", 1) == "archive (1).tar.gz"
    assert collision_filename("archive.tar.gz", 2) == "archive (2).tar.gz"


def test_collision_filename_respects_maximum_length() -> None:
    result = collision_filename(f"{'a' * 100}.zip", 12, maximum_length=32)

    assert len(result) == 32
    assert result.endswith(" (12).zip")
    assert is_safe_filename(result, maximum_length=32)


@pytest.mark.parametrize("collision_index", [0, -1, True, 1.5])
def test_collision_index_must_be_a_positive_integer(collision_index: object) -> None:
    with pytest.raises(ValueError, match="collision_index"):
        collision_filename("file.txt", collision_index)  # type: ignore[arg-type]
