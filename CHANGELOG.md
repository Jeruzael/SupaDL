# Changelog

All notable changes to SupaDL will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
intends to use [Semantic Versioning](https://semver.org/) once public release versioning is
approved.

## [Unreleased]

### Added

- M0 package skeleton and command-line smoke entry point.
- Typed settings, platform-aware application paths, and atomic JSON persistence helpers.
- Structured JSON logging with header, URL, context, message, and exception redaction.
- Ruff, mypy, pytest, and pytest-asyncio development configuration.
- Architecture, security, state-machine, contribution, and acceptance-criteria documents.
- Immutable domain enums, task/source/segment/progress/checksum/retry/error models, and typed
  validation errors.
- Central legal-state transition policy with UTC lifecycle timestamp handling.
- RFC 5987-aware Content-Disposition filename extraction, URL fallback, Windows-safe
  sanitization, length enforcement, and deterministic collision naming.
- Explicitly owned HTTPX client construction with HTTP/2, TLS verification, bounded
  redirects, four-way timeouts, identity encoding, and outbound URL validation.
- Streamed metadata probing with `HEAD` and minimal `GET` fallbacks, demonstrated range
  support, typed HTTP/transport failures, and safe filename resolution.
- A deterministic local HTTP fixture matrix covering redirects, rejected `HEAD`, rejected or
  misleading ranges, unknown length, lifecycle closure, status mapping, and URL revalidation.
- Contained exclusive partial-file writing and a bounded raw single-stream worker with
  incremental SHA-256, durable flush, source-validator checks, and exact length enforcement.
- Single-stream fixture coverage for exact bytes/hash, unknown and zero lengths, early EOF,
  excess data, transformed or changed sources, conflicts, containment, and failure cleanup.
