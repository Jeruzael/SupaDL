# SupaDL - Detailed Development Plan for Codex

**Project:** SupaDL  
**Purpose:** Cross-platform, modular download manager inspired by the useful architectural ideas behind IDM and JDownloader, without copying proprietary code, branding, or protected behavior.  
**Primary implementation:** Python 3.14.x  
**Desktop UI:** PySide6 / Qt  
**Networking:** HTTPX + asyncio  
**Persistence:** SQLite  
**Packaging target:** Windows first, then Linux and macOS  
**Document version:** 1.0  
**Date:** 2026-09-02

## 1. Executive Summary

SupaDL is a local-first desktop download manager designed around a reusable download engine rather than a GUI-centric architecture. The first release will focus on reliable HTTP/HTTPS file downloading, pause/resume, segmented range downloads, queues, retry policies, persistent state, checksums, and a clean desktop UI. Later releases can add browser integration, generic link extraction, a plugin system, HLS/DASH media handling through standards-compliant tooling, headless/CLI operation, scheduling, bandwidth controls, and optional remote management.

The project must be built incrementally. Each milestone must leave the repository runnable, testable, and documented. Codex should not jump directly to browser interception or host-specific extraction before the core transfer engine is proven.

## 2. Product Principles

1. **Reliability before speed.** A slower correct downloader is more useful than a fast corrupt one.
2. **Core independent of UI.** GUI, CLI, and browser extension must call the same application/service layer.
3. **Persistent by default.** Interrupted downloads and queued tasks survive process restarts.
4. **Host-friendly concurrency.** Respect server capabilities, connection limits, Retry-After, and backoff.
5. **Security by default.** No TLS verification disabling, unsafe filename trust, arbitrary shell execution, credential logging, or silent executable launching.
6. **Plugin isolation.** Site/host logic must not infect the generic transfer engine.
7. **Observable behavior.** Structured logs, task state transitions, transfer metrics, and useful error categories.
8. **Testable architecture.** Network behavior must be testable against a local fixture server.
9. **Legal/ethical boundaries.** Do not bypass DRM, authentication, paywalls, access controls, anti-bot protections, or platform restrictions. Support downloads the user is authorized to access.
10. **No premature native rewrite.** Stay pure Python until profiling demonstrates a real bottleneck.

## 3. Scope

### MVP / v0.1-v0.4
- Direct HTTP/HTTPS download
- Metadata probing
- Safe filename and destination selection
- Single-stream transfer
- HTTP range detection
- Segmented transfer
- Pause/resume/cancel
- Automatic retries with exponential backoff
- Persistent SQLite state
- Download queue
- Progress, speed, ETA
- Checksum verification when user supplies a hash
- Desktop UI with active/queued/completed/failed views
- Basic settings
- Structured logs
- Unit, integration, and local-network tests
- Windows packaging

### Later scope
- Browser extension + localhost/native bridge
- Context-menu download action
- Cookie/referrer/user-agent forwarding with explicit controls
- Plugin SDK and host plugins
- Link grabber / generic HTML extraction
- HLS/DASH manifest handling for non-DRM sources
- FFmpeg integration for remuxing
- Scheduler
- Bandwidth limiting
- Proxy support
- Authentication profiles
- CLI/headless daemon mode
- Remote API
- Auto-update mechanism

### Explicit non-goals for early releases
- DRM circumvention
- CAPTCHA bypass
- Credential theft or browser cookie database scraping
- Circumvention of paywalls/access controls
- Torrent client functionality
- Cloud storage service cloning
- Downloading protected media without authorization
- Automatic execution of downloaded binaries

## 4. Recommended Technology Stack

| Area | Choice | Reason |
|---|---|---|
| Runtime | Python 3.14.x | Stable current feature series; mature asyncio ecosystem |
| Package manager | uv or pip + venv | Reproducible local environments |
| HTTP | httpx[http2] | Async streaming, timeouts, redirects, HTTP/2 support |
| Async runtime | asyncio | Standard library, sufficient for I/O workloads |
| Desktop UI | PySide6 | Mature Qt desktop toolkit and cross-platform support |
| Database | SQLite | Local-first, transactional, zero-admin persistence |
| DB access | aiosqlite or repository wrapper | Keeps persistence async-friendly |
| Validation/config | pydantic-settings or dataclasses | Typed settings and validation |
| Logging | stdlib logging + JSON formatter | Structured diagnostics without needless dependency |
| Tests | pytest, pytest-asyncio | Unit/integration async testing |
| HTTP test server | aiohttp or FastAPI fixture server | Deterministic range/redirect/failure simulation |
| Formatting/lint | ruff | Fast lint + formatting workflow |
| Type checking | pyright or mypy | Catch interface/state errors |
| Packaging | PyInstaller initially | Straightforward desktop bundle |
| Media later | FFmpeg subprocess wrapper | Do not reinvent codecs/muxing |
| Extension later | WebExtensions JS/TS | Chrome/Firefox-compatible browser integration |

Use version ranges or a lockfile. Do not hard-code this document's library versions into architecture; resolve compatible stable versions during implementation.

## 5. High-Level Architecture

```text
+----------------------+       +----------------------+
| PySide6 Desktop GUI  |       | CLI / Headless       |
+----------+-----------+       +----------+-----------+
           |                              |
           +--------------+---------------+
                          v
                 +------------------+
                 | Application API  |
                 | / Use Cases      |
                 +---------+--------+
                           |
        +------------------+------------------+
        |                  |                  |
        v                  v                  v
+---------------+  +---------------+  +---------------+
| Download      |  | Queue /       |  | Resolver /    |
| Manager       |  | Scheduler     |  | Plugin Manager|
+-------+-------+  +---------------+  +---------------+
        |
        v
+-------------------------+
| Transfer Engine         |
| probe/range/retry/write |
+-----------+-------------+
            |
       +----+-----+
       | HTTPX    |
       +----------+

Persistence and observability are cross-cutting:
SQLite repositories <-> Application/Core
Logging/metrics     <-> All layers
```

## 6. Architectural Layers

### 6.1 Domain
Pure models and state rules. No Qt, HTTPX, SQLite, filesystem implementation, or browser code.

Key entities:
- DownloadTask
- DownloadSegment
- DownloadSource
- DownloadProgress
- ChecksumSpec
- RetryPolicy
- DownloadSettings
- DownloadStatus enum
- SegmentStatus enum

Suggested DownloadStatus values:
`CREATED, PROBING, QUEUED, DOWNLOADING, PAUSING, PAUSED, VERIFYING, COMPLETED, FAILED, CANCELLED`

### 6.2 Application
Coordinates use cases:
- AddDownload
- ProbeDownload
- StartDownload
- PauseDownload
- ResumeDownload
- CancelDownload
- RetryDownload
- RemoveDownload
- VerifyDownload
- ReorderQueue
- RecoverInterruptedDownloads

### 6.3 Infrastructure
Implementations for:
- HTTP transport
- File writer / temp storage
- SQLite repositories
- checksum calculator
- clock
- logging
- OS paths

### 6.4 Presentation
PySide6 views/view-models or controllers. Presentation must not own download logic.

### 6.5 Integrations
Later:
- browser bridge
- plugin SDK
- media pipeline
- external FFmpeg

## 7. Repository Layout

```text
supadl/
├─ pyproject.toml
├─ README.md
├─ LICENSE
├─ CHANGELOG.md
├─ CONTRIBUTING.md
├─ docs/
│  ├─ architecture.md
│  ├─ state-machine.md
│  ├─ security.md
│  ├─ plugin-sdk.md
│  └─ adr/
├─ src/supadl/
│  ├─ __init__.py
│  ├─ app.py
│  ├─ domain/
│  │  ├─ models.py
│  │  ├─ enums.py
│  │  ├─ errors.py
│  │  └─ policies.py
│  ├─ application/
│  │  ├─ services.py
│  │  ├─ commands.py
│  │  ├─ events.py
│  │  └─ dto.py
│  ├─ transfer/
│  │  ├─ probe.py
│  │  ├─ engine.py
│  │  ├─ segmenter.py
│  │  ├─ worker.py
│  │  ├─ retry.py
│  │  ├─ throttling.py
│  │  └─ validation.py
│  ├─ persistence/
│  │  ├─ db.py
│  │  ├─ schema.py
│  │  ├─ migrations.py
│  │  └─ repositories.py
│  ├─ storage/
│  │  ├─ paths.py
│  │  ├─ writer.py
│  │  └─ filenames.py
│  ├─ security/
│  │  ├─ url_policy.py
│  │  ├─ secret_store.py
│  │  └─ sanitization.py
│  ├─ plugins/
│  │  ├─ api.py
│  │  ├─ manager.py
│  │  └─ builtin/
│  ├─ media/
│  │  ├─ manifests.py
│  │  └─ ffmpeg.py
│  ├─ browser/
│  │  ├─ bridge.py
│  │  └─ auth.py
│  ├─ ui/
│  │  ├─ main_window.py
│  │  ├─ models.py
│  │  ├─ dialogs.py
│  │  └─ resources/
│  ├─ cli/
│  │  └─ main.py
│  ├─ config/
│  │  └─ settings.py
│  └─ observability/
│     └─ logging.py
├─ tests/
│  ├─ unit/
│  ├─ integration/
│  ├─ fixtures/
│  └─ e2e/
├─ tools/
│  └─ dev_server/
└─ extension/          # later milestone
```

## 8. Download State Machine

```text
CREATED
  -> PROBING
  -> QUEUED
  -> DOWNLOADING
       -> PAUSING -> PAUSED -> QUEUED/DOWNLOADING
       -> VERIFYING -> COMPLETED
       -> FAILED -> QUEUED/DOWNLOADING (retry)
       -> CANCELLED
```

Rules:
- State transitions happen in one service, never ad hoc in widgets/workers.
- Every transition is persisted transactionally.
- A process crash while DOWNLOADING must recover as PAUSED/QUEUED according to policy.
- COMPLETED is immutable except removal/history actions.
- CANCELLED must stop scheduling new network work before deleting temporary data.

## 9. HTTP Probe Strategy

Do not trust HEAD alone. Some servers reject or lie on HEAD.

Algorithm:
1. Validate URL scheme (http/https for initial releases).
2. Follow redirects within configured maximum.
3. Attempt HEAD.
4. If HEAD is unsupported/inconclusive, issue a minimal GET, preferably `Range: bytes=0-0`.
5. Capture final URL, status code, Content-Length, Content-Type, Content-Disposition, ETag, Last-Modified, Accept-Ranges.
6. Determine range support from actual 206 behavior, not header alone.
7. Derive a safe filename.
8. Store validators (ETag/Last-Modified) for safe resume.

## 10. Segmented Download Algorithm

Use segmented downloading only when:
- content length is known,
- server demonstrates byte-range support,
- file is above configurable minimum size,
- segment count > 1,
- response is not dynamically transformed in a way that invalidates byte offsets.

Initial segment policy:
- < 8 MiB: 1 segment
- 8-64 MiB: up to 2
- 64-512 MiB: up to 4
- > 512 MiB: up to 8
- Cap per host globally.

Each segment stores:
- start byte
- end byte inclusive
- next byte to request
- downloaded count
- status
- retries

Request:
`Range: bytes=<next>-<end>`

Validation:
- segmented response must be 206
- validate Content-Range boundaries
- detect server falling back to 200 and restart safely as single stream
- use If-Range with ETag or Last-Modified when resuming where appropriate

Writing strategy for first stable version:
- use one preallocated `.supadl.part` destination with random-access writes guarded by clear ownership of non-overlapping ranges, OR individual segment files with a deterministic merge phase.
- Prefer individual segment files for the earliest prototype because correctness/debugging is easier; migrate to random access after tests pass if desired.

## 11. Resume Safety

Resume must never silently append bytes from a changed resource.

Store:
- original URL
- final resolved URL
- content length
- ETag
- Last-Modified
- per-segment progress
- temp paths

On resume:
1. Re-probe source.
2. Compare strong ETag when available.
3. Otherwise compare Last-Modified + length with conservative rules.
4. If source identity changed, mark `SOURCE_CHANGED` and require restart rather than corrupting the file.
5. Send a range request from the first missing byte.
6. Validate Content-Range.

## 12. Persistence Schema

Suggested tables:

### downloads
- id UUID/text primary key
- source_url
- final_url
- filename
- destination_path
- temp_path
- content_length
- mime_type
- etag
- last_modified
- status
- priority
- created_at
- updated_at
- started_at
- completed_at
- bytes_downloaded
- checksum_algorithm nullable
- checksum_expected nullable
- checksum_actual nullable
- error_code nullable
- error_message nullable sanitized

### segments
- id
- download_id FK
- segment_index
- start_byte
- end_byte
- next_byte
- bytes_downloaded
- status
- retry_count

### settings
key/value or typed settings table.

### schema_version
migration tracking.

Use WAL mode where appropriate. Use transactions for state changes and segment checkpoint batches.

## 13. File and Filename Safety

- Parse Content-Disposition carefully; support filename* where reasonable.
- Strip path separators and control characters.
- Block `.` and `..` path semantics.
- Normalize reserved Windows names (CON, PRN, AUX, NUL, COM1, etc.).
- Enforce maximum filename length conservatively.
- Resolve collisions with `name (1).ext` style behavior.
- Write to `.supadl.part` or a private temp directory until completion.
- Atomically rename/move when possible.
- Never execute downloaded content automatically.
- Do not trust MIME type to determine executability.

## 14. Retry and Error Model

Define typed errors such as:
- NetworkUnavailable
- DnsFailure
- ConnectTimeout
- ReadTimeout
- TlsError
- HttpClientError
- HttpServerError
- Unauthorized
- Forbidden
- NotFound
- RateLimited
- RangeUnsupported
- SourceChanged
- DiskFull
- PermissionDenied
- FileConflict
- ChecksumMismatch
- CancelledByUser

Retry defaults:
- DNS/connect/read transient failures: yes with bounded exponential backoff + jitter
- 429: honor Retry-After
- 500/502/503/504: retry bounded
- 401/403/404: do not blindly retry
- TLS validation failure: do not bypass verification
- disk full/permission: pause/fail until user action

## 15. Queue and Concurrency

Global settings:
- max active downloads: default 3
- max connections per download: default 4
- max connections per host: default 8
- configurable later

Queue manager responsibilities:
- respect priority/order
- avoid starvation
- stop scheduling when app is shutting down
- pause cleanly
- coordinate per-host semaphore
- expose aggregate speed

## 16. Progress and Speed Calculation

Track monotonic byte counters.
- instantaneous speed: short rolling window
- displayed speed: EWMA/rolling average to prevent visual jitter
- ETA = remaining / smoothed speed when stable
- progress = downloaded / content_length when known
- unknown length uses indeterminate progress

Do not persist progress every packet. Checkpoint on a time/byte threshold, e.g. every 1-2 seconds or several MiB.

## 17. UI Specification

Main window:
- toolbar: Add URL, Start, Pause, Resume, Cancel, Remove, Settings
- sidebar/tabs: All, Active, Queued, Completed, Failed
- table columns: Name, Status, Progress, Size, Speed, ETA, Connections, Destination
- bottom/status area: total active speed, active count

Add Download dialog:
- URL
- resolved filename after probe
- destination folder
- start now / queue
- optional checksum
- advanced: connections override, headers only where safe/appropriate

Details panel:
- source/final URL
- MIME/size
- ETag/Last-Modified
- segment progress
- timestamps
- sanitized failure reason

UI rules:
- never block Qt UI thread with network/disk work
- communicate with engine through signals/events/application service
- no business logic in button handlers
- disable invalid actions based on state

## 18. Browser Integration - Later Milestone

Architecture:
Browser extension -> authenticated localhost/native bridge -> SupaDL application service.

Security requirements:
- bind loopback only
- random per-install secret/token or native messaging
- validate Origin where applicable
- CSRF-resistant request design
- restrict accepted commands
- never expose arbitrary filesystem write endpoints
- never expose shell execution
- do not scrape browser cookie DBs
- cookies can be forwarded only by extension with explicit user/browser permission and must be stored minimally

Features:
- right-click Download with SupaDL
- optional capture of browser-initiated downloads after explicit user enablement
- transfer URL, referrer, user-agent, allowed cookies/headers

## 19. Plugin Architecture - Later Milestone

Plugin protocol should return normalized DownloadCandidate objects, not manipulate UI or database directly.

Conceptual interface:
```python
class ResolverPlugin(Protocol):
    name: str
    priority: int

    def can_handle(self, url: str) -> bool: ...
    async def resolve(self, context: ResolveContext) -> list[DownloadCandidate]: ...
```

Plugin restrictions:
- explicit capability model
- network access through provided client when feasible
- secrets through controlled context
- timeouts
- no arbitrary UI mutation
- plugin exceptions isolated
- plugins should declare supported domains/patterns

Start with built-ins only. Third-party plugin installation should not be implemented until signing/trust/isolation decisions exist.

## 20. Media Handling - Later Milestone

For user-authorized, non-DRM media:
- parse HLS `.m3u8`
- parse DASH `.mpd`
- select streams
- download segments
- verify expected ordering
- invoke FFmpeg for remux/merge

Do not implement DRM key extraction, Widevine/FairPlay/PlayReady circumvention, access-control bypass, or anti-bot evasion.

## 21. Security Baseline

- TLS verification always enabled by default; production UI should not provide a casual "ignore certificate errors" switch.
- redact Authorization, Cookie, Set-Cookie, tokens, signed query secrets from logs.
- sanitize URLs before logs by optionally redacting query parameters.
- loopback API authenticated.
- database contains minimal secrets; use OS credential store for durable credentials if feature is added.
- strict path sanitization.
- protect against zip-slip style problems if archive features ever exist.
- no command strings through `shell=True` for FFmpeg; pass argument arrays.
- dependency scanning in CI.
- lock dependencies.
- validate update packages/signatures before future auto-update.

## 22. Testing Strategy

### Unit
- segment boundaries
- state machine transitions
- filename sanitization
- retry policy
- Content-Disposition parsing
- speed/ETA calculations
- checksum validation
- URL/log redaction

### Integration with local fixture server
Server endpoints should simulate:
- ordinary 200 file
- working 206 ranges
- server advertises ranges but ignores them
- HEAD rejected but GET works
- redirects
- chunked/unknown content length
- disconnect after N bytes
- slow response
- 429 Retry-After
- 500 then recovery
- changed ETag
- changed Last-Modified
- invalid Content-Range
- auth-required fixture (later)

### End-to-end
- add URL -> complete file -> hash matches
- pause -> process restart -> resume -> hash matches
- segmented -> hash matches
- crash recovery
- cancel leaves expected cleanup state
- disk error surfaces useful status

Never rely on public internet sites for the main automated test suite.

## 23. CI Quality Gates

Every PR/build should run:
1. ruff check
2. formatter check
3. type checker
4. pytest unit
5. pytest integration
6. dependency vulnerability audit where practical
7. build smoke test

Target early coverage: meaningful critical-path coverage rather than gaming a percentage. Aim for >=80% of core transfer/domain code once stable.

## 24. Milestone Roadmap

### M0 - Repository/Foundation
Deliverable: clean runnable skeleton.

### M1 - Reliable Single-Stream Downloader
Deliverable: CLI/core can download a file reliably.

### M2 - Persistence and Resume
Deliverable: restart-safe pause/resume.

### M3 - Segmented Range Engine
Deliverable: safe multi-connection downloads.

### M4 - Queue/Policies/Verification
Deliverable: multiple managed downloads, retries, checksums.

### M5 - Desktop GUI
Deliverable: Windows desktop MVP.

### M6 - Hardening and Packaging
Deliverable: distributable v0.1 beta.

### M7 - Browser Integration
Deliverable: opt-in browser handoff.

### M8 - Plugin/Link Resolver
Deliverable: extensible resolver SDK.

### M9 - Standards-based Media
Deliverable: HLS/DASH non-DRM workflow.

## 25. Atomic Codex Task Backlog

### M0 Foundation
**SUP-001** Initialize repository with `src/` layout, pyproject, README, tests.  
Acceptance: clean install; `python -m supadl` or CLI help works; tests run.

**SUP-002** Configure ruff, type checker, pytest, pytest-asyncio.  
Acceptance: one command runs quality checks locally.

**SUP-003** Add settings model and OS-specific application data paths.  
Acceptance: settings load defaults without creating unsafe paths.

**SUP-004** Add structured logging with secret/header redaction.  
Acceptance: tests prove Authorization/Cookie values are never emitted.

### M1 Single Stream
**SUP-101** Define domain enums/models/errors.  
Acceptance: no HTTPX/Qt imports in domain package.

**SUP-102** Implement safe filename resolver.  
Acceptance: traversal/reserved-name test matrix passes.

**SUP-103** Implement HTTP client factory with explicit connect/read/write/pool timeouts, redirect cap, user-agent, TLS validation.  
Acceptance: local server integration tests pass.

**SUP-104** Implement probe service using HEAD fallback to minimal GET.  
Acceptance: handles HEAD rejection and redirects.

**SUP-105** Implement single-stream worker to `.part` file.  
Acceptance: downloaded SHA-256 equals fixture.

**SUP-106** Implement cancellation token/control primitive.  
Acceptance: cancelled worker exits promptly and predictably.

**SUP-107** Emit progress events decoupled from UI.  
Acceptance: test subscriber receives monotonic updates.

### M2 Persistence/Resume
**SUP-201** Create SQLite schema and migration bootstrap.  
Acceptance: fresh DB + idempotent reopen.

**SUP-202** Implement download/segment repositories.  
Acceptance: round-trip tests for all persisted state.

**SUP-203** Persist task state transitions transactionally.  
Acceptance: invalid transitions rejected; valid transitions durable.

**SUP-204** Implement periodic checkpointing.  
Acceptance: progress persists without per-chunk DB writes.

**SUP-205** Implement single-stream HTTP Range resume.  
Acceptance: pause halfway, reopen, resume, hash exact.

**SUP-206** Implement source identity validation with ETag/Last-Modified/length.  
Acceptance: changed source refuses unsafe append.

**SUP-207** Implement startup recovery of interrupted tasks.  
Acceptance: DOWNLOADING tasks from crash become recoverable state.

### M3 Segmentation
**SUP-301** Implement segment planner.  
Acceptance: no gaps/overlap; inclusive ranges correct across edge sizes.

**SUP-302** Detect real range capability using 206 test.  
Acceptance: handles misleading Accept-Ranges.

**SUP-303** Implement segment worker and Content-Range validation.  
Acceptance: invalid range response aborts safely.

**SUP-304** Implement bounded concurrent segment coordinator.  
Acceptance: respects per-download/per-host limits.

**SUP-305** Implement segment-file merge or random-access assembler.  
Acceptance: output exact hash; temp cleanup after success.

**SUP-306** Implement segmented pause/resume.  
Acceptance: individual segment offsets persist and resume.

**SUP-307** Implement safe fallback when server stops honoring ranges.  
Acceptance: no duplicate/corrupt output.

### M4 Queue/Verification
**SUP-401** Implement download manager service.  
Acceptance: coordinates lifecycle without UI dependency.

**SUP-402** Implement priority queue and global active limit.  
Acceptance: deterministic ordering tests.

**SUP-403** Implement host concurrency limiter.  
Acceptance: fixture counts never exceed configured host cap.

**SUP-404** Implement retry policy/backoff/jitter/Retry-After.  
Acceptance: deterministic tests using injectable clock/random source.

**SUP-405** Implement checksum service SHA-256/SHA-512 at minimum.  
Acceptance: match and mismatch cases.

**SUP-406** Implement collision policy and atomic completion move.  
Acceptance: existing destination is not silently overwritten unless policy permits.

**SUP-407** Implement aggregate metrics, rolling speed, ETA.  
Acceptance: tests for zero/unknown/stalled cases.

### M5 GUI
**SUP-501** Bootstrap PySide6 app and main window shell.  
Acceptance: launches with engine service injected.

**SUP-502** Implement downloads table model.  
Acceptance: updates from events without blocking UI thread.

**SUP-503** Implement Add Download dialog and asynchronous probe.  
Acceptance: validation errors shown; UI remains responsive.

**SUP-504** Bind Start/Pause/Resume/Cancel actions to application commands.  
Acceptance: buttons enabled only for legal states.

**SUP-505** Add filters for All/Active/Queued/Completed/Failed.  
Acceptance: status filtering works without duplicating underlying state.

**SUP-506** Add detail panel with segments and error info.  
Acceptance: secrets redacted.

**SUP-507** Add settings dialog for destination, active downloads, connections, retry policy.  
Acceptance: persisted settings take effect on future jobs.

**SUP-508** Add tray behavior only after base window is stable.  
Acceptance: exit vs minimize behavior explicit.

### M6 Hardening/Packaging
**SUP-601** Add local fixture server comprehensive scenarios.  
**SUP-602** Add crash/restart E2E tests.  
**SUP-603** Add large sparse/file streaming tests without storing giant fixtures in Git.  
**SUP-604** Add Windows path/long filename tests.  
**SUP-605** Configure PyInstaller build.  
**SUP-606** Add version metadata and release artifact naming.  
**SUP-607** Add dependency/license inventory.  
**SUP-608** Conduct threat-model review before beta.

### M7 Browser Extension
**SUP-701** Define localhost bridge protocol and threat model before code.  
**SUP-702** Implement authenticated loopback bridge.  
**SUP-703** Build WebExtension context-menu handoff.  
**SUP-704** Pass URL/referrer/user-agent and explicitly permitted cookies.  
**SUP-705** Add replay/CSRF/origin defenses and integration tests.

### M8 Plugin/Resolver
**SUP-801** Finalize ResolverPlugin protocol.  
**SUP-802** Implement generic direct-HTTP resolver as reference plugin.  
**SUP-803** Implement plugin manager with deterministic ordering/timeouts.  
**SUP-804** Add plugin test harness.  
**SUP-805** Document plugin SDK.  
Do not add arbitrary third-party plugin installation yet.

### M9 Media
**SUP-901** Add HLS manifest parser path for non-DRM content.  
**SUP-902** Add DASH parser path for non-DRM content.  
**SUP-903** Add stream selection model.  
**SUP-904** Add segment download reuse through core scheduler where appropriate.  
**SUP-905** Add safe FFmpeg invocation without shell=True.  
**SUP-906** Detect encryption/DRM and fail with unsupported/protected status rather than attempting bypass.

## 26. Definition of Done for Every Codex Task

A task is not done merely because code compiles.

Codex must:
1. implement only the requested scope;
2. add/update tests;
3. run relevant tests;
4. run lint/type checks for affected code;
5. update docs when public behavior/API changes;
6. avoid unrelated refactors;
7. report files changed;
8. report commands/tests run and results;
9. list remaining known limitations;
10. keep repository runnable at the end.

## 27. Codex Working Rules

When feeding this plan to Codex, prepend/retain these rules:

- Read `README.md`, `docs/architecture.md`, `docs/security.md`, `pyproject.toml`, and relevant tests before editing.
- Work on one SUP task or a very small dependency group at a time.
- Do not implement future milestones unless necessary for the current task.
- Prefer small composable interfaces over god classes.
- Core/domain modules must not import PySide6.
- Do not perform network calls at import time.
- Do not create global HTTP clients without explicit lifecycle ownership.
- Every async client/session must be closed cleanly.
- Never disable TLS verification as a shortcut.
- Never log credentials/cookies/tokens.
- Never use `shell=True` for external tools.
- Never silently overwrite user files.
- Never trust server-provided filenames as paths.
- Handle cancellation explicitly rather than swallowing CancelledError.
- Use bounded concurrency, never unbounded `gather` over arbitrary jobs.
- Tests should use the local fixture server, not random public URLs.
- Preserve backward-compatible persisted data through migrations once beta users exist.

## 28. Recommended First Codex Prompt

```text
You are implementing SupaDL, a modular Python download manager.

Read the supplied SupaDL master plan completely before changing code.
For this session implement ONLY milestone M0, tasks SUP-001 through SUP-004.

Constraints:
- Python 3.14.x target.
- Use a src/ layout.
- No GUI implementation yet.
- No browser integration, media downloading, plugin host logic, or segmented transfer yet.
- Keep architecture compatible with later async HTTPX and PySide6 layers.
- Configure ruff, pytest, pytest-asyncio, and one type checker.
- Add structured logging with tests proving secrets such as Authorization and Cookie values are redacted.
- Add typed settings and safe platform-specific app data/config paths.
- Keep dependencies minimal.

Before coding:
1. Inspect existing repository state.
2. State which files you plan to create/change.
3. Identify any conflict between the repository and master plan; prefer existing intentional project conventions unless they violate the security requirements.

After coding:
1. Run formatter/linter/type checker/tests.
2. Fix failures caused by your changes.
3. Provide a concise implementation summary.
4. List changed files.
5. List commands run and test results.
6. List remaining limitations relevant to M0 only.
Do not begin M1 automatically.
```

## 29. Subsequent Codex Prompt Template

```text
Continue SupaDL using the master plan.
Implement ONLY: <TASK IDS>.

First inspect the current repository, relevant architecture/security docs, and existing tests.
Do not redo completed tasks unless a failing test or architectural conflict requires a correction.

For each requested task:
- restate acceptance criteria in implementation terms;
- implement the smallest coherent change;
- add/update unit or integration tests;
- preserve security requirements;
- run relevant quality checks.

Do not implement later roadmap items opportunistically.
At the end report changed files, tests/commands run, results, and known limitations.
```

## 30. Release Criteria for First Public Beta

SupaDL v0.1 beta should not be released until:
- direct downloads pass deterministic fixture tests;
- pause/restart/resume produces exact checksum;
- segmented download produces exact checksum;
- misleading/broken range servers do not corrupt files;
- common retries and 429 behavior are bounded;
- destination collision policy is explicit;
- filenames cannot escape destination directory;
- no auth/cookie/token secrets are present in normal logs;
- UI stays responsive during active transfers;
- shutting down leaves recoverable state;
- Windows packaged build installs/runs on a clean test environment;
- license/dependency notices are documented;
- README clearly states limitations and protected-content policy.

## 31. Future Performance Strategy

Do not assume Python is too slow. Measure first.

Profile separately:
- network saturation
- CPU usage
- disk write throughput
- SQLite checkpoint overhead
- Qt event/update overhead
- hashing cost

Optimization order:
1. reduce excessive UI/progress events;
2. tune chunk size;
3. batch DB checkpoints;
4. optimize file writes;
5. tune connection concurrency;
6. evaluate HTTP/2 behavior;
7. only then consider native Rust/C extension for a proven hot path.

## 32. Architecture Decision Records to Create

- ADR-001: Python 3.14 + asyncio core
- ADR-002: Core/UI separation
- ADR-003: HTTPX transport abstraction
- ADR-004: SQLite persistence and migration strategy
- ADR-005: Segment-file vs random-access write strategy
- ADR-006: Browser bridge security model
- ADR-007: Plugin trust/isolation model
- ADR-008: FFmpeg integration boundary

## 33. Final Instruction to Codex

Treat this document as the product and engineering baseline, not permission to implement everything at once. Work milestone-by-milestone, preserve a green repository, and prefer correctness, resumability, source validation, security, and tests over feature count.
