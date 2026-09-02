"""Typed configuration and application-path helpers."""

from supadl.config.settings import (
    ApplicationPaths,
    DownloadSettings,
    SettingsError,
    load_settings,
    resolve_application_paths,
    save_settings,
)

__all__ = [
    "ApplicationPaths",
    "DownloadSettings",
    "SettingsError",
    "load_settings",
    "resolve_application_paths",
    "save_settings",
]
