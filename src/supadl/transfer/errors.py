"""Typed, sanitized mappings for HTTP transport and response failures."""

from __future__ import annotations

import socket
import ssl

import httpx

from supadl.domain import ErrorCode, SupaDLError


def _iter_exception_chain(error: BaseException) -> tuple[BaseException, ...]:
    chain: list[BaseException] = []
    current: BaseException | None = error
    while current is not None and current not in chain:
        chain.append(current)
        current = current.__cause__ or current.__context__
    return tuple(chain)


def map_transport_error(error: httpx.HTTPError) -> SupaDLError:
    """Convert HTTPX failures into stable errors without retaining sensitive URLs."""
    if isinstance(error, httpx.TooManyRedirects):
        return SupaDLError(
            "the server exceeded the configured redirect limit",
            code=ErrorCode.REDIRECT_LIMIT_EXCEEDED,
        )
    if isinstance(error, (httpx.ConnectTimeout, httpx.PoolTimeout)):
        return SupaDLError("the connection timed out", code=ErrorCode.CONNECT_TIMEOUT)
    if isinstance(error, httpx.ReadTimeout):
        return SupaDLError("the server response timed out", code=ErrorCode.READ_TIMEOUT)

    chain = _iter_exception_chain(error)
    if any(isinstance(item, ssl.SSLError) for item in chain):
        return SupaDLError("TLS certificate validation failed", code=ErrorCode.TLS_ERROR)
    if any(isinstance(item, socket.gaierror) for item in chain):
        return SupaDLError("the server name could not be resolved", code=ErrorCode.DNS_FAILURE)
    if isinstance(error, httpx.NetworkError):
        return SupaDLError("the server could not be reached", code=ErrorCode.NETWORK_UNAVAILABLE)
    return SupaDLError("the HTTP request failed", code=ErrorCode.HTTP_CLIENT_ERROR)


def http_status_error(status_code: int) -> SupaDLError:
    """Map an unsuccessful HTTP status without embedding the request URL."""
    if status_code == 401:
        return SupaDLError("the server requires authorization", code=ErrorCode.UNAUTHORIZED)
    if status_code == 403:
        return SupaDLError("the server denied access", code=ErrorCode.FORBIDDEN)
    if status_code == 404:
        return SupaDLError("the requested resource was not found", code=ErrorCode.NOT_FOUND)
    if status_code == 429:
        return SupaDLError("the server rate limit was reached", code=ErrorCode.RATE_LIMITED)
    if 500 <= status_code <= 599:
        return SupaDLError(
            "the server could not complete the request",
            code=ErrorCode.HTTP_SERVER_ERROR,
            context={"status_code": status_code},
        )
    return SupaDLError(
        "the server rejected the request",
        code=ErrorCode.HTTP_CLIENT_ERROR,
        context={"status_code": status_code},
    )
