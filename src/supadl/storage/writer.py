"""Contained, exclusive partial-file creation and durable closure."""

from __future__ import annotations

import errno
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO

from supadl.domain import ErrorCode, SupaDLError


def _storage_error(error: OSError) -> SupaDLError:
    if error.errno in {errno.ENOSPC, getattr(errno, "EDQUOT", -1)} or getattr(
        error, "winerror", None
    ) in {39, 112}:
        return SupaDLError("partial storage is out of space", code=ErrorCode.DISK_FULL)
    if isinstance(error, PermissionError):
        return SupaDLError(
            "partial storage denied the write operation",
            code=ErrorCode.PERMISSION_DENIED,
        )
    return SupaDLError("partial storage could not be written", code=ErrorCode.FILE_WRITE_ERROR)


class PartialFileWriter:
    """Create new `.part` files only within one existing application-owned root."""

    def __init__(self, temporary_root: Path) -> None:
        if not isinstance(temporary_root, Path) or not temporary_root.is_absolute():
            raise ValueError("temporary_root must be an absolute path")
        try:
            resolved_root = temporary_root.resolve(strict=True)
        except OSError as error:
            raise ValueError("temporary_root must already exist") from error
        if not resolved_root.is_dir():
            raise ValueError("temporary_root must be a directory")
        self._temporary_root = resolved_root

    @property
    def temporary_root(self) -> Path:
        return self._temporary_root

    def validate_target(self, partial_path: Path) -> Path:
        """Return a contained canonical path without creating or replacing it."""
        if not isinstance(partial_path, Path) or not partial_path.is_absolute():
            raise ValueError("partial_path must be an absolute path")
        if partial_path.suffix.casefold() != ".part":
            raise ValueError("partial_path must use a .part suffix")
        try:
            resolved_parent = partial_path.parent.resolve(strict=True)
        except OSError as error:
            raise ValueError("partial_path parent must already exist") from error
        if not resolved_parent.is_relative_to(self._temporary_root):
            raise ValueError("partial_path must stay within temporary_root")
        resolved_path = resolved_parent / partial_path.name
        if resolved_path.exists():
            raise SupaDLError(
                "the partial file already exists",
                code=ErrorCode.FILE_CONFLICT,
            )
        return resolved_path

    @contextmanager
    def open_new(self, partial_path: Path) -> Iterator[BinaryIO]:
        """Exclusively create a new partial file and durably flush it on success."""
        resolved_path = self.validate_target(partial_path)
        try:
            with resolved_path.open("xb") as handle:
                yield handle
                handle.flush()
                os.fsync(handle.fileno())
        except FileExistsError as error:
            raise SupaDLError(
                "the partial file already exists",
                code=ErrorCode.FILE_CONFLICT,
            ) from error
        except OSError as error:
            raise _storage_error(error) from error
