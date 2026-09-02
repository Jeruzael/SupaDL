"""Typed settings, platform paths, validation, and JSON persistence."""

from __future__ import annotations

import json
import os
import platform
import tempfile
from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Any, Final, Self

_APP_NAME: Final = "SupaDL"
_MAX_APP_NAME_LENGTH: Final = 64
_WINDOWS_INVALID_APP_NAME_CHARACTERS: Final = frozenset('<>:"/\\|?*')


class SettingsError(ValueError):
    """Raised when settings or application paths are invalid."""


def _require_absolute(path: Path, *, label: str) -> Path:
    expanded = path.expanduser()
    if not expanded.is_absolute():
        raise SettingsError(f"{label} must be an absolute path")
    return Path(os.path.abspath(expanded))


def _validate_app_name(app_name: str) -> str:
    if not app_name or len(app_name) > _MAX_APP_NAME_LENGTH:
        raise SettingsError("application name must contain between 1 and 64 characters")
    if app_name in {".", ".."}:
        raise SettingsError("application name cannot use relative path semantics")
    if app_name != app_name.strip(" ."):
        raise SettingsError("application name cannot start or end with spaces or dots")
    if any(ord(character) < 32 or ord(character) == 127 for character in app_name):
        raise SettingsError("application name cannot contain control characters")
    if any(character in _WINDOWS_INVALID_APP_NAME_CHARACTERS for character in app_name):
        raise SettingsError("application name cannot contain path or device separators")
    return app_name


def _environment_path(
    environment: Mapping[str, str],
    key: str,
    fallback: Path,
) -> Path:
    value = environment.get(key)
    return _require_absolute(Path(value), label=key) if value else fallback


@dataclass(frozen=True, slots=True)
class ApplicationPaths:
    """Resolved application-owned and user-facing paths."""

    config_dir: Path
    data_dir: Path
    cache_dir: Path
    log_dir: Path
    database_path: Path
    settings_path: Path
    default_download_dir: Path

    def __post_init__(self) -> None:
        path_names = (
            "config_dir",
            "data_dir",
            "cache_dir",
            "log_dir",
            "database_path",
            "settings_path",
            "default_download_dir",
        )
        for path_name in path_names:
            normalized = _require_absolute(getattr(self, path_name), label=path_name)
            object.__setattr__(self, path_name, normalized)

        self._require_contained(self.database_path, self.data_dir, label="database_path")
        self._require_contained(self.log_dir, self.data_dir, label="log_dir")
        self._require_contained(self.settings_path, self.config_dir, label="settings_path")

    @staticmethod
    def _require_contained(path: Path, parent: Path, *, label: str) -> None:
        if not path.is_relative_to(parent):
            raise SettingsError(f"{label} must stay within {parent}")

    @property
    def application_directories(self) -> tuple[Path, ...]:
        """Return only directories owned by SupaDL."""
        return tuple(dict.fromkeys((self.config_dir, self.data_dir, self.cache_dir, self.log_dir)))

    def ensure_application_directories(self) -> None:
        """Create application-owned directories without creating the download directory."""
        for directory in self.application_directories:
            directory.mkdir(parents=True, exist_ok=True)


def resolve_application_paths(
    *,
    app_name: str = _APP_NAME,
    system: str | None = None,
    environment: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> ApplicationPaths:
    """Resolve safe paths without creating directories or touching the filesystem."""
    safe_app_name = _validate_app_name(app_name)
    operating_system = platform.system() if system is None else system
    variables = os.environ if environment is None else environment
    home_directory = _require_absolute(Path.home() if home is None else home, label="home")

    if operating_system == "Windows":
        local_base = _environment_path(
            variables,
            "LOCALAPPDATA",
            home_directory / "AppData" / "Local",
        )
        data_dir = local_base / safe_app_name
        config_dir = data_dir
        cache_dir = data_dir / "cache"
    elif operating_system == "Darwin":
        data_dir = home_directory / "Library" / "Application Support" / safe_app_name
        config_dir = data_dir
        cache_dir = home_directory / "Library" / "Caches" / safe_app_name
    elif operating_system == "Linux":
        data_base = _environment_path(
            variables,
            "XDG_DATA_HOME",
            home_directory / ".local" / "share",
        )
        config_base = _environment_path(
            variables,
            "XDG_CONFIG_HOME",
            home_directory / ".config",
        )
        cache_base = _environment_path(
            variables,
            "XDG_CACHE_HOME",
            home_directory / ".cache",
        )
        data_dir = data_base / safe_app_name
        config_dir = config_base / safe_app_name
        cache_dir = cache_base / safe_app_name
    else:
        raise SettingsError(f"unsupported operating system: {operating_system!r}")

    return ApplicationPaths(
        config_dir=config_dir,
        data_dir=data_dir,
        cache_dir=cache_dir,
        log_dir=data_dir / "logs",
        database_path=data_dir / "supadl.sqlite3",
        settings_path=config_dir / "settings.json",
        default_download_dir=home_directory / "Downloads",
    )


@dataclass(frozen=True, slots=True)
class DownloadSettings:
    """Validated M0 settings with conservative resource limits."""

    default_destination: Path
    max_active_downloads: int = 3
    max_connections_per_download: int = 4
    max_connections_per_host: int = 8
    connect_timeout_seconds: float = 10.0
    read_timeout_seconds: float = 30.0
    write_timeout_seconds: float = 30.0
    pool_timeout_seconds: float = 10.0
    max_redirects: int = 10
    max_retries: int = 5
    backoff_base_seconds: float = 0.5
    backoff_max_seconds: float = 30.0
    checkpoint_interval_seconds: float = 2.0
    checkpoint_bytes: int = 4 * 1024 * 1024
    maximum_filename_length: int = 180

    def __post_init__(self) -> None:
        destination = _require_absolute(self.default_destination, label="default destination")
        object.__setattr__(self, "default_destination", destination)

        self._validate_integer("max_active_downloads", self.max_active_downloads, 1, 32)
        self._validate_integer(
            "max_connections_per_download",
            self.max_connections_per_download,
            1,
            32,
        )
        self._validate_integer(
            "max_connections_per_host",
            self.max_connections_per_host,
            1,
            64,
        )
        self._validate_integer("max_redirects", self.max_redirects, 0, 50)
        self._validate_integer("max_retries", self.max_retries, 0, 20)
        self._validate_integer("checkpoint_bytes", self.checkpoint_bytes, 1, 1024**3)
        self._validate_integer(
            "maximum_filename_length",
            self.maximum_filename_length,
            32,
            240,
        )

        self._validate_seconds("connect_timeout_seconds", self.connect_timeout_seconds)
        self._validate_seconds("read_timeout_seconds", self.read_timeout_seconds)
        self._validate_seconds("write_timeout_seconds", self.write_timeout_seconds)
        self._validate_seconds("pool_timeout_seconds", self.pool_timeout_seconds)
        self._validate_seconds("backoff_base_seconds", self.backoff_base_seconds)
        self._validate_seconds("backoff_max_seconds", self.backoff_max_seconds)
        self._validate_seconds("checkpoint_interval_seconds", self.checkpoint_interval_seconds)
        if self.backoff_base_seconds > self.backoff_max_seconds:
            raise SettingsError("backoff_base_seconds cannot exceed backoff_max_seconds")

    @staticmethod
    def _validate_integer(name: str, value: int, minimum: int, maximum: int) -> None:
        if isinstance(value, bool) or not isinstance(value, int):
            raise SettingsError(f"{name} must be an integer")
        if not minimum <= value <= maximum:
            raise SettingsError(f"{name} must be between {minimum} and {maximum}")

    @staticmethod
    def _validate_seconds(name: str, value: float) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SettingsError(f"{name} must be numeric")
        if not 0 < float(value) <= 3600:
            raise SettingsError(f"{name} must be greater than 0 and at most 3600 seconds")

    @classmethod
    def defaults(cls, paths: ApplicationPaths | None = None) -> Self:
        """Create validated settings using the resolved default download directory."""
        resolved_paths = resolve_application_paths() if paths is None else paths
        return cls(default_destination=resolved_paths.default_download_dir)

    def with_updates(self, **changes: Any) -> Self:
        """Return a validated copy containing the requested changes."""
        return replace(self, **changes)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible representation."""
        values = asdict(self)
        values["default_destination"] = str(self.default_destination)
        return values

    @classmethod
    def from_dict(cls, values: Mapping[str, object]) -> Self:
        """Validate and construct settings from a mapping."""
        allowed_names = {item.name for item in fields(cls)}
        unknown_names = set(values) - allowed_names
        if unknown_names:
            joined = ", ".join(sorted(unknown_names))
            raise SettingsError(f"unknown settings: {joined}")
        if "default_destination" not in values:
            raise SettingsError("default_destination is required")

        converted = dict(values)
        destination = converted["default_destination"]
        if not isinstance(destination, (str, os.PathLike)):
            raise SettingsError("default_destination must be a path string")
        converted["default_destination"] = Path(destination)

        try:
            return cls(**converted)  # type: ignore[arg-type]
        except TypeError as error:
            raise SettingsError(f"invalid settings structure: {error}") from error


def load_settings(path: Path, *, defaults: DownloadSettings | None = None) -> DownloadSettings:
    """Load settings, returning supplied defaults only when the file is absent."""
    settings_path = _require_absolute(path, label="settings path")
    if not settings_path.exists():
        return DownloadSettings.defaults() if defaults is None else defaults

    try:
        raw_value = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SettingsError(f"could not read settings: {error}") from error
    if not isinstance(raw_value, dict):
        raise SettingsError("settings document must contain a JSON object")
    return DownloadSettings.from_dict(raw_value)


def save_settings(settings: DownloadSettings, path: Path) -> None:
    """Atomically persist validated settings as UTF-8 JSON."""
    settings_path = _require_absolute(path, label="settings path")
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(settings.to_dict(), indent=2, sort_keys=True) + "\n"
    temporary_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=settings_path.parent,
            prefix=f".{settings_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_file.write(serialized)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
            temporary_path = Path(temporary_file.name)
        os.replace(temporary_path, settings_path)
    except OSError as error:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise SettingsError(f"could not save settings: {error}") from error
