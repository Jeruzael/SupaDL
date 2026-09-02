# SupaDL

SupaDL is a local-first, Windows-first download manager built around a reusable Python
application and transfer engine. The project prioritizes correctness, safe resumability,
bounded concurrency, observable behavior, and a responsive desktop interface.

## Current status

Milestone M0 and the first four M1 slices are implemented. This repository
contains:

- the installable `src/` package and command-line smoke entry point;
- typed settings and safe platform-specific application paths;
- structured JSON logging with centralized secret redaction;
- immutable domain models, typed errors, and a centralized lifecycle transition policy;
- safe filename extraction, sanitization, truncation, and collision-name generation;
- an explicitly owned asynchronous HTTP client with bounded redirects, four-way timeouts,
  HTTP/2 support, TLS verification, and redirect URL validation;
- a streamed metadata probe with `HEAD` fallback, real byte-range verification, typed
  failures, and safe filename resolution;
- Ruff, mypy, pytest, and pytest-asyncio configuration; and
- the product plan, security baseline, architecture, and detailed acceptance criteria.

The transfer worker, partial-file writer, SQLite persistence, queue, and PySide6 interface
are not implemented yet.

## Requirements

- CPython 3.14.x
- `pip` and `venv`

SupaDL uses HTTPX with HTTP/2 support for asynchronous HTTP transport. Development tools are
declared in the `dev` optional dependency group.

## Set up on Windows

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Run

```powershell
python -m supadl
supadl --version
```

The M0 entry point intentionally prints help only; download commands arrive in later
milestones.

## Quality checks

Run all configured checks:

```powershell
.\tools\check.ps1
```

Or run them separately:

```powershell
python -m ruff format --check .
python -m ruff check .
python -m mypy
python -m pytest
```

## Application data

Application paths are resolved at runtime and are never created during import. On Windows,
SupaDL uses `%LOCALAPPDATA%\SupaDL` when available. Linux follows the XDG base-directory
variables, and macOS uses the standard `~/Library` locations. Callers must explicitly invoke
directory creation.

Settings are JSON-serializable and can be saved atomically. The current defaults are
documented in `src/supadl/config/settings.py` and validated before use.

Domain task, source, progress, segment, checksum, retry, and error models serialize to
storage-friendly primitives. Filename resolution prefers a valid Content-Disposition
`filename*`/`filename`, then the URL path, then a safe fallback. It never treats the result
as a destination path.

HTTP clients are created with `supadl.transfer.create_http_client`; the caller owns the
client and must close it or use it as an async context manager. `ProbeService` accepts that
client through its constructor and returns serializable source metadata without buffering a
response body.

## Security and content policy

SupaDL is for files the user is authorized to download. It will not implement DRM,
paywall, CAPTCHA, anti-bot, or access-control circumvention. Downloaded files will never be
executed automatically. TLS verification, safe filenames, path containment, and secret-safe
logs are project requirements.

See [Security](docs/security.md) and the
[detailed acceptance criteria](docs/SupaDL_Acceptance_Criteria.md).

## Known limitations

- Probing is implemented, but there is no byte-transfer worker, database, queue, desktop UI,
  or browser integration yet.
- Probe results are serialization-ready but will not survive process restart until SUP-201
  introduces SQLite persistence.
- The public product license is not selected; the repository is currently all rights
  reserved.
- Windows packaging and clean-machine verification are scheduled for M6.
