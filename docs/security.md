# SupaDL Security Baseline

## Current foundation controls

- Application paths are platform-aware, validated, and created only through an explicit
  call.
- Settings validation rejects unsafe or nonsensical limits before use.
- Structured logs redact sensitive headers, credentials, URL query values, fragments,
  sensitive mapping keys, messages, and exception text.
- Content-Disposition and URL-derived filename candidates are normalized into Windows-safe
  basenames; separators, control characters, invalid characters, dot semantics, and reserved
  device names are neutralized.
- Filename length limits preserve extensions where possible, and deterministic collision
  names do not inspect or mutate the filesystem.
- No network, database, shell, or downloaded-file execution occurs in M0.
- The package has no third-party runtime dependencies in M0.

## Mandatory future controls

- TLS verification remains enabled; certificate errors are never bypassed as a workaround.
- Server-provided filenames are untrusted basenames and cannot select a destination path.
- Existing user files are never silently overwritten.
- Authorization, cookies, tokens, signed query data, and credentials are never stored in
  normal logs.
- External programs use argument arrays and never `shell=True`.
- Concurrency and retries are bounded.
- Browser, plugin, media, and update features require their planned threat-model decisions
  before implementation.

## Protected-content policy

SupaDL supports only downloads the user is authorized to access. It will not bypass DRM,
authentication, paywalls, access controls, CAPTCHA, or anti-bot protections, and it will not
scrape browser credential or cookie databases.

## Reporting diagnostics

Before sharing diagnostics, users and developers should still review them for private file
paths or business-sensitive metadata. Redaction is a defense-in-depth control, not permission
to publish logs without review.
