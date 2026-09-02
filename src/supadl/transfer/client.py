"""Owned HTTPX client construction for transfer infrastructure."""

from __future__ import annotations

from typing import Final

import httpx

from supadl import __version__
from supadl.config import DownloadSettings
from supadl.domain import DownloadSource

DEFAULT_USER_AGENT: Final = f"SupaDL/{__version__}"


async def _validate_outbound_url(request: httpx.Request) -> None:
    """Reject unsupported or credential-bearing initial and redirect URLs before sending."""
    DownloadSource(original_url=str(request.url))


def _validate_user_agent(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("user_agent cannot be empty")
    if "\r" in value or "\n" in value:
        raise ValueError("user_agent cannot contain line breaks")
    return value.strip()


def create_http_client(
    settings: DownloadSettings,
    *,
    user_agent: str = DEFAULT_USER_AGENT,
    transport: httpx.AsyncBaseTransport | None = None,
) -> httpx.AsyncClient:
    """Create a secure asynchronous client whose caller owns and must close it."""
    if not isinstance(settings, DownloadSettings):
        raise TypeError("settings must be DownloadSettings")

    timeout = httpx.Timeout(
        connect=settings.connect_timeout_seconds,
        read=settings.read_timeout_seconds,
        write=settings.write_timeout_seconds,
        pool=settings.pool_timeout_seconds,
    )
    maximum_connections = max(
        settings.max_connections_per_host,
        settings.max_active_downloads * settings.max_connections_per_download,
    )
    limits = httpx.Limits(
        max_connections=maximum_connections,
        max_keepalive_connections=min(
            maximum_connections,
            settings.max_connections_per_host,
        ),
    )
    return httpx.AsyncClient(
        headers={
            "User-Agent": _validate_user_agent(user_agent),
            "Accept": "*/*",
            "Accept-Encoding": "identity",
        },
        timeout=timeout,
        limits=limits,
        follow_redirects=True,
        max_redirects=settings.max_redirects,
        verify=True,
        trust_env=False,
        http2=True,
        event_hooks={"request": [_validate_outbound_url]},
        transport=transport,
    )
