from __future__ import annotations

import json
from pathlib import Path

import pytest

from supadl.config import (
    ApplicationPaths,
    DownloadSettings,
    SettingsError,
    load_settings,
    resolve_application_paths,
    save_settings,
)


def test_windows_paths_use_local_app_data_without_creating_directories(tmp_path: Path) -> None:
    home = tmp_path / "home"
    local_app_data = tmp_path / "local"

    paths = resolve_application_paths(
        system="Windows",
        environment={"LOCALAPPDATA": str(local_app_data)},
        home=home,
    )

    assert paths.data_dir == local_app_data / "SupaDL"
    assert paths.config_dir == paths.data_dir
    assert paths.cache_dir == paths.data_dir / "cache"
    assert paths.log_dir == paths.data_dir / "logs"
    assert paths.database_path == paths.data_dir / "supadl.sqlite3"
    assert paths.settings_path == paths.config_dir / "settings.json"
    assert paths.default_download_dir == home / "Downloads"
    assert not local_app_data.exists()
    assert not home.exists()


def test_linux_paths_follow_xdg_variables(tmp_path: Path) -> None:
    paths = resolve_application_paths(
        system="Linux",
        environment={
            "XDG_DATA_HOME": str(tmp_path / "data"),
            "XDG_CONFIG_HOME": str(tmp_path / "config"),
            "XDG_CACHE_HOME": str(tmp_path / "cache"),
        },
        home=tmp_path / "home",
    )

    assert paths.data_dir == tmp_path / "data" / "SupaDL"
    assert paths.config_dir == tmp_path / "config" / "SupaDL"
    assert paths.cache_dir == tmp_path / "cache" / "SupaDL"


def test_macos_paths_use_library_locations(tmp_path: Path) -> None:
    home = tmp_path / "home"

    paths = resolve_application_paths(system="Darwin", environment={}, home=home)

    assert paths.data_dir == home / "Library" / "Application Support" / "SupaDL"
    assert paths.cache_dir == home / "Library" / "Caches" / "SupaDL"


def test_creating_application_directories_excludes_download_destination(tmp_path: Path) -> None:
    paths = resolve_application_paths(system="Windows", environment={}, home=tmp_path)

    paths.ensure_application_directories()

    assert all(directory.is_dir() for directory in paths.application_directories)
    assert not paths.default_download_dir.exists()


def test_application_paths_reject_relative_or_uncontained_storage(tmp_path: Path) -> None:
    with pytest.raises(SettingsError, match="config_dir must be an absolute path"):
        ApplicationPaths(
            config_dir=Path("relative"),
            data_dir=tmp_path / "data",
            cache_dir=tmp_path / "cache",
            log_dir=tmp_path / "data" / "logs",
            database_path=tmp_path / "data" / "supadl.sqlite3",
            settings_path=tmp_path / "config" / "settings.json",
            default_download_dir=tmp_path / "downloads",
        )

    with pytest.raises(SettingsError, match="database_path must stay within"):
        ApplicationPaths(
            config_dir=tmp_path / "config",
            data_dir=tmp_path / "data",
            cache_dir=tmp_path / "cache",
            log_dir=tmp_path / "data" / "logs",
            database_path=tmp_path / "outside.sqlite3",
            settings_path=tmp_path / "config" / "settings.json",
            default_download_dir=tmp_path / "downloads",
        )


@pytest.mark.parametrize(
    "app_name",
    [
        "",
        ".",
        "..",
        "../escape",
        "bad/name",
        "bad\\name",
        "bad\x00name",
        " SupaDL",
        "SupaDL.",
        "SupaDL ",
    ],
)
def test_application_name_rejects_path_semantics(tmp_path: Path, app_name: str) -> None:
    with pytest.raises(SettingsError):
        resolve_application_paths(
            app_name=app_name,
            system="Windows",
            environment={},
            home=tmp_path,
        )


def test_relative_environment_path_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(SettingsError, match="LOCALAPPDATA must be an absolute path"):
        resolve_application_paths(
            system="Windows",
            environment={"LOCALAPPDATA": "relative/path"},
            home=tmp_path,
        )


def test_unsupported_operating_system_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(SettingsError, match="unsupported operating system"):
        resolve_application_paths(system="Plan9", environment={}, home=tmp_path)


def test_default_settings_match_documented_concurrency(tmp_path: Path) -> None:
    paths = resolve_application_paths(system="Windows", environment={}, home=tmp_path)

    settings = DownloadSettings.defaults(paths)

    assert settings.default_destination == tmp_path / "Downloads"
    assert settings.max_active_downloads == 3
    assert settings.max_connections_per_download == 4
    assert settings.max_connections_per_host == 8


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("max_active_downloads", 0),
        ("max_connections_per_download", 33),
        ("max_connections_per_host", True),
        ("max_redirects", -1),
        ("max_retries", 21),
        ("checkpoint_bytes", 0),
        ("maximum_filename_length", 31),
        ("connect_timeout_seconds", 0),
        ("read_timeout_seconds", 3601),
    ],
)
def test_invalid_setting_boundaries_are_rejected(tmp_path: Path, name: str, value: object) -> None:
    settings = DownloadSettings(default_destination=tmp_path)

    with pytest.raises(SettingsError):
        settings.with_updates(**{name: value})


def test_backoff_base_cannot_exceed_maximum(tmp_path: Path) -> None:
    with pytest.raises(SettingsError, match="cannot exceed"):
        DownloadSettings(
            default_destination=tmp_path,
            backoff_base_seconds=31,
            backoff_max_seconds=30,
        )


def test_settings_require_an_absolute_destination() -> None:
    with pytest.raises(SettingsError, match="absolute path"):
        DownloadSettings(default_destination=Path("relative"))


def test_settings_normalize_parent_path_segments(tmp_path: Path) -> None:
    settings = DownloadSettings(default_destination=tmp_path / "nested" / "..")

    assert settings.default_destination == tmp_path


def test_settings_round_trip_through_dict(tmp_path: Path) -> None:
    original = DownloadSettings(default_destination=tmp_path, max_retries=7)

    restored = DownloadSettings.from_dict(original.to_dict())

    assert restored == original


def test_unknown_setting_is_rejected(tmp_path: Path) -> None:
    values = DownloadSettings(default_destination=tmp_path).to_dict()
    values["surprise"] = True

    with pytest.raises(SettingsError, match="unknown settings: surprise"):
        DownloadSettings.from_dict(values)


def test_missing_settings_file_returns_explicit_defaults(tmp_path: Path) -> None:
    defaults = DownloadSettings(default_destination=tmp_path / "downloads")

    loaded = load_settings(tmp_path / "missing.json", defaults=defaults)

    assert loaded is defaults


def test_settings_save_and_load_atomically(tmp_path: Path) -> None:
    settings_path = tmp_path / "config" / "settings.json"
    original = DownloadSettings(default_destination=tmp_path / "downloads", max_retries=7)

    save_settings(original, settings_path)
    loaded = load_settings(settings_path)

    assert loaded == original
    assert json.loads(settings_path.read_text(encoding="utf-8")) == original.to_dict()
    assert not list(settings_path.parent.glob("*.tmp"))


def test_invalid_json_is_reported_without_falling_back(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("not-json", encoding="utf-8")

    with pytest.raises(SettingsError, match="could not read settings"):
        load_settings(settings_path)
