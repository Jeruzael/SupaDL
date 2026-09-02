# SupaDL Detailed Acceptance Criteria

**Source baseline:** `SupaDL_Codex_Master_Plan.md` and `SupaDL_Detailed_Development_Plan_Codex.pdf`  
**Criteria version:** 1.0  
**Prepared:** 2026-09-02  
**Primary delivery scope:** M0-M6, ending with the first Windows public beta  
**Deferred scope:** M7-M9 and other items explicitly listed as later scope

## 1. Request Understanding

SupaDL is to be delivered as a local-first, Windows-first desktop download manager whose reusable Python application and transfer engine are independent of its PySide6 interface. The first public beta must reliably download authorized HTTP/HTTPS resources, preserve and resume work across restarts, use segmented byte-range transfer only when safe, manage multiple queued downloads, verify optional checksums, expose useful progress and errors in a responsive desktop UI, and ship as a tested Windows package.

These criteria convert the product and engineering plans into observable conditions. They describe what must be true for the M0-M6 beta scope to be accepted; they do not authorize implementation of later browser, plugin, media, daemon, or remote-control features.

## 2. Users, Actors, and System Triggers

### Primary actor

- **Desktop user:** adds an authorized direct HTTP/HTTPS URL, chooses a destination and transfer options, manages the download lifecycle, and reviews status or errors.

### Supporting actors and triggers

- **SupaDL desktop application:** validates user actions, displays persisted task state, and delegates work to the application layer.
- **Application/download manager service:** owns use cases, legal state transitions, scheduling, and events without depending on Qt.
- **Transfer engine:** probes sources, downloads bytes, validates responses, retries eligible failures, and emits progress.
- **Queue manager:** starts eligible work subject to ordering and concurrency rules.
- **Persistence service:** transactionally stores tasks, segments, settings, errors, and checkpoints.
- **Local fixture HTTP server:** deterministically simulates normal, partial, slow, redirected, malformed, and failing HTTP behavior for tests.
- **Remote HTTP/HTTPS origin:** supplies the user-authorized resource and its metadata.
- **Operating system/filesystem:** supplies safe application paths, destination access, atomic move capability, and disk errors.
- **Application startup:** triggers migration checks and recovery of interrupted tasks.
- **Application shutdown:** stops new scheduling, closes resources, and leaves active work recoverable.

## 3. Business Goal

The beta succeeds when a non-technical Windows user can trust SupaDL to manage direct downloads without silent corruption, unsafe filenames, lost queue state, leaked credentials, a frozen interface, or accidental execution/overwrite of downloaded content. The architecture must also allow future GUI, CLI, browser, resolver, and media integrations to reuse the same application boundary without rewriting the core downloader.

## 4. Scope and Affected Areas

### 4.1 In-scope beta capabilities

- Direct HTTP and HTTPS URL entry and metadata probing.
- Safe filename and destination resolution.
- Single-stream transfer and real byte-range capability detection.
- Segmented transfers for eligible resources.
- Start, queue, pause, resume, retry, cancel, and remove/history actions.
- Persistent tasks, segments, settings, state transitions, and recovery.
- Bounded automatic retry with backoff, jitter, and `Retry-After` support.
- Priority/order-aware queue with global, per-download, and per-host limits.
- Progress, smoothed speed, ETA, and aggregate activity metrics.
- Optional user-supplied SHA-256 or SHA-512 verification.
- PySide6 main window, views, details, add-download flow, and basic settings.
- Structured and secret-safe logs plus typed errors.
- Deterministic unit, integration, end-to-end, and packaging checks.
- Windows executable/package and supporting documentation.

### 4.2 Explicitly deferred

- Browser extension, context-menu capture, and loopback/native bridge.
- Browser cookies, referrer, or user-agent forwarding.
- Generic HTML link extraction or link grabber.
- Third-party plugin installation, plugin marketplace, and host-specific resolvers.
- HLS/DASH processing and FFmpeg remuxing.
- Scheduling, bandwidth limiting, proxy profiles, and authentication profiles.
- CLI/headless daemon, remote API, and remote management.
- Auto-update delivery.
- Linux and macOS packaging certification.

The M0-M6 implementation must not expose incomplete controls or public APIs for deferred features.

### 4.3 Explicit non-goals

- DRM, paywall, authentication, access-control, CAPTCHA, or anti-bot circumvention.
- Credential theft or scraping browser cookie databases.
- Torrent functionality or cloud-storage-service cloning.
- Downloading protected content without authorization.
- Automatic execution of downloaded files.

### 4.4 Affected technical areas

- **Frontend:** PySide6 application shell, download table, filtered views, add dialog, details, settings, lifecycle actions, status area, loading/empty/error feedback.
- **Backend/application:** use cases, state transitions, scheduling, retry classification, recovery, events, and configuration.
- **Transfer infrastructure:** HTTP client lifecycle, probes, streaming, ranges, segmentation, cancellation, checksums, and response validation.
- **Database:** SQLite bootstrap, migrations, downloads, segments, settings, and schema version.
- **Filesystem:** safe application directories, partial data, segment files, collision handling, merge/finalization, and cleanup.
- **Authentication/authorization:** no product accounts in beta; URL and content access remain the user's responsibility. Security enforcement still applies to secrets, URLs, paths, and future integration boundaries.
- **Integrations:** HTTP/HTTPS origin and local test fixture server only for beta.
- **Notifications/jobs:** in-process application events and queue workers; no external notification service or independent scheduler.
- **Tests/CI:** lint, formatting, typing, unit, integration, E2E, dependency audit, build, and clean-machine smoke checks.
- **Documentation:** setup, usage, architecture, security, limitations, protected-content policy, dependencies/licenses, change history, and decisions.

## 5. Confirmed Requirements

- Python 3.14.x is the target runtime; dependency versions are resolved and locked during implementation.
- The core/domain layer has no PySide6, HTTPX, SQLite, or concrete filesystem dependencies.
- Qt widgets do not own transfer or business logic.
- HTTP clients and asynchronous tasks have explicit lifecycle ownership and clean shutdown.
- TLS certificate verification is enabled by default and is not bypassed as an error workaround.
- Incomplete data is stored separately from the final destination and is finalized only after transfer validation.
- Server-provided names are treated as untrusted input and can never escape the chosen destination.
- State transitions are centralized and persisted transactionally.
- Resume validates source identity and byte ranges before appending or assembling data.
- Segmentation is conditional on known length and demonstrated `206 Partial Content` behavior.
- Network and worker concurrency is bounded.
- Automated network tests use a local deterministic fixture server rather than depending on public internet sites.
- Browser, resolver/plugin, and media functionality is not part of the first beta.

## 6. Assumptions

- “First public beta” means completion of M0 through M6. The earlier `v0.1-v0.4` wording is treated as an umbrella for incremental internal releases, not permission to omit an M0-M6 beta gate.
- The beta is a single-user local desktop application; it has no product login, multi-user tenancy, RBAC, or cloud synchronization.
- A supplied checksum applies to the final downloaded file, not individual segments.
- SHA-256 and SHA-512 are the only required checksum algorithms for beta.
- Unknown-length responses can be downloaded as a single indeterminate stream but are not segmented.
- If a reliable source validator is unavailable, resume uses the conservative policy documented in Section 11 and must restart rather than risk appending uncertain bytes.
- Removal from history and cancellation of network activity are separate concepts; whether partial data is retained or deleted is governed by an explicit user-visible cleanup policy.
- Existing destination files are preserved by default. Automatic renaming is the assumed default until the collision policy decision is recorded.
- Separate per-segment temporary files are the assumed initial implementation because the source plan prefers them for correctness and diagnosis.
- Settings changes affect future work unless a setting is explicitly documented as safe to apply to active work.
- The packaged application may perform a user-authorized public direct-download smoke test manually, but the repeatable automated suite remains local-only.

## 7. Open Questions and Required Decisions

These do not prevent the AC document from being approved, but each must be resolved before the named implementation area is considered complete.

| ID | Decision needed | Required by | Acceptance impact |
|---|---|---|---|
| OQ-01 | Confirm public version numbering and whether all M0-M6 work ships as `v0.1 beta`. | Release planning | Determines release labels, metadata, and changelog. |
| OQ-02 | Choose the default collision action: auto-rename, prompt, fail, or opt-in overwrite. | SUP-406/UI | Silent overwrite remains prohibited under every choice. |
| OQ-03 | Define cancel behavior for partial data: retain for possible restart, delete, or prompt. | SUP-106/SUP-401/UI | State, cleanup, and UI wording must agree. |
| OQ-04 | Define startup recovery policy for stale `DOWNLOADING`, `PAUSING`, and `VERIFYING` states: `PAUSED` or eligible `QUEUED`. | SUP-207 | Recovery tests must assert the chosen deterministic state. |
| OQ-05 | Confirm separate segment files versus random-access writes for the first beta. | ADR-005/SUP-305 | Controls storage layout, merge behavior, and disk-space tests. |
| OQ-06 | Set concrete redirect, timeout, retry-count, backoff, jitter, checkpoint, and filename-length defaults. | M1-M4 | Boundary and timing tests require exact values. |
| OQ-07 | Define URL query redaction policy: known-sensitive keys only or redact all query values by default. | SUP-004/security | Log snapshots must match the chosen policy. |
| OQ-08 | Define whether `Remove` deletes only history, partial files, completed files, or presents explicit options. | SUP-401/UI | Prevents accidental data loss. |
| OQ-09 | Choose pyright or mypy and the required strictness level. | SUP-002 | Establishes the CI pass/fail command. |
| OQ-10 | Choose the license and supported Windows versions/architectures. | SUP-001/SUP-605/SUP-607 | Required for public distribution and clean-machine test matrix. |
| OQ-11 | Define accessibility baseline: keyboard shortcuts, minimum contrast target, screen-reader labels, and supported DPI scaling. | M5/M6 | Makes UI accessibility objectively testable. |
| OQ-12 | Define whether tray behavior ships in beta or remains disabled until its exit/minimize behavior is approved. | SUP-508 | Affects shutdown and recoverability tests. |

## 8. Functional Requirements

### 8.1 Foundation, packaging metadata, and architecture

- **FR-001:** A fresh supported Python 3.14.x environment can install the project from the repository using the documented command.
- **FR-002:** `import supadl` succeeds after installation without performing network access, opening a database unexpectedly, or starting background workers.
- **FR-003:** A documented module entry point or CLI help smoke path exits successfully even though a full headless CLI is deferred.
- **FR-004:** The repository contains the documented `src/`, test, documentation, tooling, and later-integration boundaries without requiring placeholder implementations of future features.
- **FR-005:** Domain modules import and execute without importing PySide6, HTTPX, SQLite implementations, browser code, or concrete filesystem writers.
- **FR-006:** Application commands depend on interfaces/ports and can be exercised in tests without constructing the Qt application.
- **FR-007:** Every owned HTTP client, file handle, database connection, and asynchronous worker can be closed through an explicit lifecycle path.

### 8.2 Settings and application paths

- **FR-010:** The application resolves config, data, cache/temp, database, log, and default download locations using platform-aware APIs rather than hard-coded user paths.
- **FR-011:** First launch creates only the application-owned directories it needs and never creates a path outside the resolved or user-selected location.
- **FR-012:** Typed defaults exist for active downloads, per-download connections, per-host connections, network timeouts, redirect limit, retries/backoff, checkpointing, destination, and filename/collision behavior.
- **FR-013:** Default concurrency values are three active downloads, four connections per download, and eight connections per host unless OQ-06 changes them before implementation.
- **FR-014:** Invalid persisted settings are rejected with a typed, actionable error or replaced by documented safe defaults; they do not crash the app at import time.
- **FR-015:** Settings serialize and deserialize without losing supported values.
- **FR-016:** Persisted settings are reloaded after process restart and apply according to the documented active-versus-future-job policy.

### 8.3 Structured logging and observability

- **FR-020:** Logging can be initialized repeatedly without duplicate handlers or duplicate log lines.
- **FR-021:** Structured records include useful context such as timestamp, severity, event/error category, and download ID when applicable.
- **FR-022:** `Authorization`, `Proxy-Authorization`, `Cookie`, `Set-Cookie`, tokens, credentials, and signed query secrets are absent from emitted normal log text.
- **FR-023:** Logged URLs follow the policy resolved in OQ-07 and never expose secrets through fragments, user-info, or known token query parameters.
- **FR-024:** User-visible and stored error messages are sanitized while retaining enough category/context for remediation.
- **FR-025:** Lifecycle state changes, terminal failures, retries, recovery decisions, and finalization outcomes produce diagnostic events without logging byte payloads or secrets.

### 8.4 Domain model and lifecycle

- **FR-030:** The domain defines serializable models for download task, segment, source, progress, checksum, retry policy, and settings.
- **FR-031:** The task state set includes `CREATED`, `PROBING`, `QUEUED`, `DOWNLOADING`, `PAUSING`, `PAUSED`, `VERIFYING`, `COMPLETED`, `FAILED`, and `CANCELLED`.
- **FR-032:** Segment states are explicitly modeled and cannot be confused with top-level task states.
- **FR-033:** One transition policy/service defines all legal task transitions; workers and widgets cannot directly assign arbitrary states.
- **FR-034:** A valid transition updates persistent state and its relevant timestamp atomically.
- **FR-035:** An invalid transition leaves persisted and in-memory state unchanged and returns a typed error.
- **FR-036:** `COMPLETED` cannot transition back into transfer states; history removal is an explicit separate action.
- **FR-037:** Cancellation prevents new network work from being scheduled before any approved partial-data cleanup occurs.
- **FR-038:** Pause reaches a stable `PAUSED` state only after active workers have stopped at safe checkpoints and resources are closed.

### 8.5 URL input and HTTP probing

- **FR-040:** The add-download flow accepts only syntactically valid `http` or `https` URLs for beta.
- **FR-041:** Embedded URL credentials, unsupported schemes, malformed hosts, and missing URLs are rejected before a transfer task starts.
- **FR-042:** Probe requests use the configured HTTP client, explicit connect/read/write/pool timeouts, a bounded redirect limit, a declared user agent, and TLS verification.
- **FR-043:** The probe attempts `HEAD` but falls back to a minimal `GET`, preferably `Range: bytes=0-0`, when `HEAD` is rejected, unsupported, or inconclusive.
- **FR-044:** Redirects are followed only up to the configured cap; redirect loops or overflow produce a typed failure.
- **FR-045:** A successful probe records the original URL, final URL, status, content length when known, MIME type when supplied, `Content-Disposition`, ETag, Last-Modified, and observed range behavior.
- **FR-046:** Range support is considered proven only after a correctly formed `206` response with a valid `Content-Range`; `Accept-Ranges` alone is not sufficient.
- **FR-047:** Probe responses do not download or retain the full resource body.
- **FR-048:** If length or optional metadata is absent, the source remains eligible for a safe single-stream download unless another validation rule fails.

### 8.6 Filename and destination safety

- **FR-050:** Filename resolution considers standards-compliant `Content-Disposition`/`filename*`, then URL path, then a deterministic safe fallback.
- **FR-051:** The resulting filename is a basename only and contains no effective absolute path, drive prefix, parent traversal, separator, NUL, or control character.
- **FR-052:** `.` and `..`, empty names, trailing dot/space issues, and Windows reserved device names are neutralized.
- **FR-053:** Names are constrained to the documented maximum without losing the extension unnecessarily and without producing an empty name.
- **FR-054:** Destination containment is checked after normalization/resolution; final and temporary paths remain inside the selected destination or application-owned temp root.
- **FR-055:** Existing files are never overwritten without an explicit approved policy and, if overwrite is supported, an unambiguous user action.
- **FR-056:** Auto-rename behavior, when selected, produces deterministic `name (n).ext` results and handles races at finalization without overwriting.
- **FR-057:** Downloaded content is never automatically executed or trusted solely because of its MIME type or extension.

### 8.7 Single-stream transfer

- **FR-060:** A valid direct source can be streamed in bounded chunks to a partial file without buffering the entire response in memory.
- **FR-061:** The final destination filename is not exposed as a complete file while transfer or verification remains incomplete.
- **FR-062:** Progress events report monotonic downloaded-byte totals that never exceed known content length.
- **FR-063:** Network and file resources close predictably on completion, pause, cancellation, retryable failure, terminal failure, and shutdown.
- **FR-064:** Successful transfer of a known fixture produces a file with exactly the expected length and SHA-256.
- **FR-065:** A response ending before the declared length fails as incomplete and is never finalized as `COMPLETED`.
- **FR-066:** A server returning more bytes than the validated expected representation does not silently write corrupt output.

### 8.8 Persistence, checkpointing, and migrations

- **FR-070:** A fresh application database initializes transactionally with `downloads`, `segments`, `settings`, and queryable `schema_version` storage.
- **FR-071:** Reopening an initialized database is idempotent and does not duplicate or erase records.
- **FR-072:** Migrations execute in order, update the schema version only after success, and roll back on failure.
- **FR-073:** Repository operations round-trip every required task and segment field without data loss or type drift.
- **FR-074:** Multi-record lifecycle operations use a transaction so task state and associated segment/checkpoint data cannot be partially committed.
- **FR-075:** Progress checkpoints occur on configured time/byte thresholds rather than for every received network chunk.
- **FR-076:** Checkpointing is frequent enough that a forced process termination loses no more progress than the documented threshold, subject to OS buffering.
- **FR-077:** WAL mode is enabled when supported; unsupported WAL mode falls back safely and is observable rather than preventing all startup.
- **FR-078:** Application/repository consumers do not embed ad hoc raw SQL outside the persistence implementation boundary.

### 8.9 Pause, resume, and crash recovery

- **FR-080:** Pausing an active single-stream or segmented download stops network work promptly at a safe checkpoint and preserves internally consistent partial state.
- **FR-081:** Resuming always re-probes the source before requesting missing bytes.
- **FR-082:** Resume prefers a strong ETag; otherwise it applies the approved conservative Last-Modified-plus-length policy.
- **FR-083:** Resume sends a byte-range request from the first missing byte and uses `If-Range` when appropriate.
- **FR-084:** Resume validates `206` and `Content-Range` before appending or accepting resumed bytes.
- **FR-085:** A changed validator or incompatible representation produces `SOURCE_CHANGED` and requires a clean restart; existing partial data is not silently combined with new content.
- **FR-086:** An incompatible `200` response to a resume request never causes append corruption; the task either restarts safely from byte zero under explicit policy or fails with an actionable status.
- **FR-087:** On startup, stale active states are converted transactionally to the deterministic recovery state resolved in OQ-04.
- **FR-088:** A pause, process exit, reopen, and resume sequence for a fixture finishes with the exact expected checksum.
- **FR-089:** Missing, truncated, oversized, or externally modified partial files are detected before resume and never trusted solely from database counters.

### 8.10 Segmentation and assembly

- **FR-100:** Segmentation is used only when length is known, byte ranges are demonstrated, the file meets the configured minimum, requested count is greater than one, and offsets remain valid for the representation.
- **FR-101:** The initial adaptive maximum is one segment below 8 MiB, two from 8-64 MiB, four from 64-512 MiB, and eight above 512 MiB, subject to global/per-download/per-host caps.
- **FR-102:** For every positive file size, planned inclusive ranges have no gaps, no overlaps, no negative offsets, and their union is exactly `[0, size-1]`.
- **FR-103:** Each segment persists index, inclusive start/end, next byte, downloaded count, state, and retry count.
- **FR-104:** A segment requests only `bytes=<next>-<end>` and validates status `206`, `Content-Range` unit, boundaries, total length when present, and returned byte count.
- **FR-105:** A segment writes only to its assigned segment file or byte range and cannot overwrite another segment's ownership.
- **FR-106:** A fatal source identity/range error stops sibling workers and prevents final assembly.
- **FR-107:** The coordinator never exceeds the effective per-download or per-host limit and propagates pause/cancel to all workers.
- **FR-108:** If a server stops honoring ranges, SupaDL discards/isolates incompatible segmented output and restarts single-stream only under the approved safe fallback policy.
- **FR-109:** Assembly begins only after every segment has been validated complete.
- **FR-110:** Assembly orders bytes exactly, closes and flushes the result, and verifies expected total length before finalization.
- **FR-111:** A successful segmented fixture produces the exact expected checksum and removes obsolete segment temp files.
- **FR-112:** Pausing, restarting the process, and resuming a segmented fixture requests only missing ranges and produces the exact final checksum.

### 8.11 Queue and concurrency

- **FR-120:** Adding with “queue” creates a persisted `QUEUED` task without starting it while adding with “start now” makes it eligible immediately, subject to available capacity.
- **FR-121:** The queue starts no more than the configured number of active downloads.
- **FR-122:** Total connections for one download and one origin host never exceed their configured limits, including retries and probe traffic where the documented policy applies.
- **FR-123:** Ordering and explicit priority/reorder actions are deterministic and durable across restart.
- **FR-124:** A released slot starts the next eligible task without requiring an application restart or manual refresh.
- **FR-125:** The scheduling policy prevents indefinite starvation; its fairness rule is documented and covered by a deterministic test.
- **FR-126:** Pause, cancellation, terminal failure, and completion release their concurrency capacity exactly once.
- **FR-127:** Shutdown prevents new work from being scheduled before active workers and persistence resources are closed.

### 8.12 Retry and typed error behavior

- **FR-130:** Failures are mapped to typed categories including network unavailable, DNS failure, connect/read timeout, TLS error, 4xx/5xx HTTP errors, unauthorized, forbidden, not found, rate limited, range unsupported, source changed, disk full, permission denied, file conflict, checksum mismatch, and user cancellation.
- **FR-131:** DNS, connect, and read transient failures retry only up to the configured bound using exponential backoff plus jitter.
- **FR-132:** HTTP `429` honors a valid `Retry-After` within the documented cap and remains bounded.
- **FR-133:** HTTP `500`, `502`, `503`, and `504` follow the bounded retry policy.
- **FR-134:** HTTP `401`, `403`, and `404` are not blindly retried.
- **FR-135:** TLS validation failures never trigger a retry with certificate verification disabled.
- **FR-136:** Disk-full and permission failures stop writes, preserve a consistent recoverable/failed state, and tell the user what action is needed.
- **FR-137:** Retry timing tests use injectable clock and random sources and therefore run deterministically without real backoff delays.
- **FR-138:** A user-requested retry follows a legal lifecycle transition and does not reset verified partial progress unless source/file validation requires it.

### 8.13 Checksums, progress, speed, and ETA

- **FR-140:** The add flow accepts an optional checksum algorithm and digest and validates its format before starting.
- **FR-141:** SHA-256 and SHA-512 are calculated by streaming the completed partial file without loading it fully into memory.
- **FR-142:** A supplied checksum moves the task through `VERIFYING`; only a match can lead to `COMPLETED`.
- **FR-143:** A mismatch records expected and actual values, produces `CHECKSUM_MISMATCH`, and never exposes the file as a successful completion.
- **FR-144:** Without a supplied checksum, successful completion still validates all available length, range, and assembly invariants.
- **FR-145:** Instantaneous/displayed speed uses a documented short rolling window or EWMA and does not oscillate from single-packet samples.
- **FR-146:** ETA is shown only when remaining size and sufficiently stable positive speed are available; otherwise it displays an explicit unknown state.
- **FR-147:** Unknown total length uses indeterminate progress and never displays a fabricated percent or ETA.
- **FR-148:** Zero-speed, stalled, resumed, and completed states do not produce negative, infinite, or nonsensical visible metrics.
- **FR-149:** Aggregate active speed and active count agree with the active task set within the documented UI refresh interval.

### 8.14 Desktop UI

- **FR-150:** The packaged and development applications open a PySide6 main window with Add URL, Start, Pause, Resume, Cancel, Remove, and Settings actions.
- **FR-151:** The UI provides All, Active, Queued, Completed, and Failed views derived from one underlying task model without duplicating task state.
- **FR-152:** The download list exposes Name, Status, Progress, Size, Speed, ETA, Connections, and Destination, with an explicit placeholder for unavailable values.
- **FR-153:** The status area displays total active speed and active count.
- **FR-154:** The Add Download dialog validates URL input, probes asynchronously, displays resolved name/metadata, allows destination choice, supports start-now versus queue, and accepts an optional checksum.
- **FR-155:** Any advanced per-download connection/header controls included in beta accept only documented safe values and do not allow secret leakage or unrestricted request mutation.
- **FR-156:** The details view shows original/final URL, MIME/size, ETag/Last-Modified, segment progress, timestamps, and sanitized failure reason.
- **FR-157:** Start, Pause, Resume, Cancel, Retry, and Remove actions call application commands rather than manipulating workers or persisted state directly.
- **FR-158:** Lifecycle controls are enabled only for legal actions in the selected task state; invoking a stale/invalid action still fails safely in the application layer.
- **FR-159:** Slow probes, active transfers, hashing, database writes, and file I/O do not block the Qt UI thread.
- **FR-160:** Application events update the visible model without requiring manual refresh and without unsafe cross-thread widget access.
- **FR-161:** Settings include at minimum default destination, active-download limit, connection limits, and retry policy; invalid entries receive field-specific feedback.
- **FR-162:** Empty views state what they contain and, where relevant, provide an Add URL action.
- **FR-163:** Closing/exiting follows the documented shutdown/tray policy, clearly distinguishes minimize from exit if tray behavior ships, and leaves active work recoverable.

### 8.15 Finalization, cleanup, and removal

- **FR-170:** Finalization occurs only after transfer/assembly and required checksum validation have succeeded.
- **FR-171:** SupaDL uses an atomic same-filesystem rename/move when possible; otherwise it uses a documented safe copy/replace sequence that cannot present a partial file as completed.
- **FR-172:** A finalization race or destination conflict never overwrites an unrelated file and leaves the task recoverable or failed with a typed conflict.
- **FR-173:** Successful finalization updates status, timestamps, actual checksum when calculated, and final path transactionally enough to recover from a crash between filesystem and database operations.
- **FR-174:** Successful completion removes only obsolete application-owned partial/segment artifacts and retains the final file.
- **FR-175:** Cancel/remove cleanup follows OQ-03/OQ-08, names exactly what will be deleted, and never deletes a final or unrelated user file without explicit confirmation.
- **FR-176:** Cleanup failures are visible and logged safely; they do not falsely report that data was deleted.

### 8.16 Windows packaging and release documentation

- **FR-180:** PyInstaller produces a versioned Windows artifact using a repeatable documented command.
- **FR-181:** The package contains required Qt resources and application metadata and launches on each supported clean Windows target from OQ-10.
- **FR-182:** The packaged application can complete the approved smoke download and retains/resumes state across process restart.
- **FR-183:** Release artifact naming includes product, version, platform, and architecture.
- **FR-184:** Dependency locks, dependency/license inventory, chosen product license, and third-party notices are included or linked from the release.
- **FR-185:** README documents installation, basic use, storage locations, limitations, protected-content policy, troubleshooting, and how to report a sanitized issue.
- **FR-186:** Architecture, state-machine, security, and relevant ADR documents reflect the implemented behavior rather than aspirational alternatives.
- **FR-187:** No future browser, plugin, media, daemon, or update component is silently bundled as an unsupported beta feature.

## 9. Non-Functional Requirements

### 9.1 Reliability and data integrity

- **NFR-001:** No tested server behavior, retry, pause, crash, resume, range fallback, or destination conflict may produce a silently corrupted file marked `COMPLETED`.
- **NFR-002:** Every accepted completed fixture file matches expected length and digest.
- **NFR-003:** State and checkpoints remain recoverable after forced termination at representative lifecycle boundaries.
- **NFR-004:** Repeated startup, shutdown, pause, resume, and retry actions are idempotent where documented or return a typed invalid-action result.

### 9.2 Performance and resource use

- **NFR-010:** Response bodies and checksum input are streamed; memory use does not scale linearly with total file size.
- **NFR-011:** Concurrency, event emission, and database writes are bounded; the implementation does not create one unbounded task per queued download or received chunk.
- **NFR-012:** UI input and window interaction remain responsive during the local slow/large-transfer test; no network or disk operation executes on the Qt UI thread.
- **NFR-013:** Progress checkpoint and UI refresh rates are configurable or documented and avoid per-packet persistence/rendering.
- **NFR-014:** Optimization work follows measured profiling; a native rewrite is not an acceptance condition for beta.

### 9.3 Security and privacy

- **NFR-020:** TLS verification is on for production transfers and no casual “ignore certificate” control is exposed.
- **NFR-021:** Secrets are redacted from application logs, persisted errors, diagnostics, screenshots generated by tests, and user-visible details.
- **NFR-022:** Untrusted filenames and paths cannot escape approved roots or target Windows devices/reserved semantics.
- **NFR-023:** Downloaded content is never executed automatically and external commands are not invoked through `shell=True`.
- **NFR-024:** Only minimum metadata needed for recovery and diagnosis is persisted; future durable credentials require an OS credential store and are out of beta scope.
- **NFR-025:** Locked dependencies are scanned in CI where practical, with critical findings resolved or explicitly risk-accepted before beta.

### 9.4 Usability and accessibility

- **NFR-030:** Every long-running action has visible progress or an indeterminate busy state and remains cancellable when cancellation is safe.
- **NFR-031:** Failures state the problem category and an actionable next step without exposing sensitive details.
- **NFR-032:** The main workflow is operable by keyboard, has logical focus order, and exposes accessible names for interactive controls, subject to the detailed baseline in OQ-11.
- **NFR-033:** Text and controls remain usable at supported Windows scaling settings and at the documented minimum window size.
- **NFR-034:** Status is not communicated by color alone.

### 9.5 Maintainability and testability

- **NFR-040:** Domain, application, infrastructure, presentation, and future integration boundaries remain separately testable.
- **NFR-041:** Clock, randomness, HTTP transport, repositories, and filesystem boundaries are injectable where deterministic behavior requires it.
- **NFR-042:** Public behavior and persisted-schema changes include tests and documentation in the same change.
- **NFR-043:** Every delivered SUP task leaves formatting, linting, typing, unit, and relevant integration checks passing.

### 9.6 Compatibility

- **NFR-050:** Development and packaged builds support the Python and Windows matrix approved through OQ-10.
- **NFR-051:** Once beta data exists, schema changes preserve compatible data through versioned migrations.
- **NFR-052:** Linux/macOS architectural portability is preserved where reasonable, but release certification is not required for beta.

## 10. Data Requirements and Integrity Rules

### 10.1 Download task data

Required once a task is accepted:

- Unique text/UUID `id`.
- Original `source_url`.
- Safe `filename` and selected `destination_path`.
- Application-owned `temp_path`.
- Valid `status` and `priority/order`.
- `created_at` and `updated_at`.
- Monotonic non-negative `bytes_downloaded`.

Conditionally required after probe/start:

- Final resolved URL.
- Content length and MIME type when supplied/known.
- ETag and Last-Modified when supplied.
- Start/completion timestamps appropriate to state.
- Checksum algorithm/expected/actual values when requested/calculated.
- Typed error code and sanitized message for failures.

Integrity rules:

- `0 <= bytes_downloaded <= content_length` when length is known.
- `completed_at` is populated only for accepted completion and is not earlier than creation/start.
- `COMPLETED` requires a valid final path and no unresolved checksum mismatch.
- Error details do not contain unredacted secrets.
- URLs and paths stored for resume are the validated values used by the application, not arbitrary widget state.

### 10.2 Segment data

- Unique segment ID, parent download ID, zero-based segment index, inclusive start/end, next byte, downloaded count, state, and retry count.
- Every segment references an existing download through an enforced relationship.
- Segment index is unique within one download.
- `start_byte <= next_byte <= end_byte + 1`.
- `bytes_downloaded == next_byte - start_byte` unless a documented durable-write reconciliation step is in progress.
- Completed segments have `next_byte == end_byte + 1` and exact expected length.
- Segments for a task cover the resource exactly without gaps or overlaps.
- Deleting history/partials follows the approved cascade/cleanup policy and cannot delete unrelated files.

### 10.3 Settings and schema data

- Settings keys are typed or validated through a typed model; unknown/deprecated keys follow a documented compatibility rule.
- Concurrency counts and thresholds are positive and within safe maximums.
- Timeout/retry values are non-negative and bounded.
- `schema_version` identifies exactly which migrations have committed.
- Database timestamps use one documented timezone representation, preferably UTC, and UI localization does not alter stored values.

### 10.4 Migration impact

- Initial beta creates the baseline schema without importing legacy data.
- Every post-beta persisted-data change requires a forward migration, rollback/recovery notes, and fixtures representing the previous schema.
- A failed migration preserves the last usable database or creates a recoverable backup according to the documented migration policy.

## 11. Validation Rules

- URL is required, trimmed according to documented rules, and limited to HTTP/HTTPS.
- URL credentials and unsupported schemes are rejected; redirects are revalidated rather than trusted from the original scheme alone.
- Destination must exist or be safely creatable and must be writable before transfer begins.
- Resolved final/temp paths must remain within approved roots after normalization, symlink/junction considerations, and filename sanitization.
- Filename must be non-empty, within the chosen maximum, non-reserved, and a basename.
- Content length, counters, offsets, connection limits, retry values, and timeout values cannot be negative.
- Start byte cannot exceed end byte for a non-empty segment; all boundaries use inclusive semantics consistently.
- `Content-Range` must match the requested interval and validated representation.
- User-supplied checksum algorithm must be supported and digest length/characters must match that algorithm.
- State-dependent commands are validated both in the UI and in the application service.
- Duplicate task URLs are allowed unless a future decision prohibits them; destination collision rules still apply independently.
- Headers, if beta exposes them, must reject control characters and must not allow UI/log leakage of secrets.
- Settings that exceed documented safety caps fail field validation rather than being silently truncated, unless clamping is explicitly documented.

## 12. Permission and Security Enforcement Rules

The beta has no multi-user authorization model, but it still enforces capability boundaries:

- Only an explicit desktop-user action or documented recovery/queue policy can add or start a download.
- The application writes only to application-owned storage and a user-selected destination that passed path checks.
- Server metadata cannot choose an absolute destination or override the selected folder.
- UI action availability is advisory; the application layer independently enforces legal state transitions.
- HTTP responses cannot cause TLS disabling, command execution, arbitrary header reuse, or path traversal.
- Logs and persisted errors pass through centralized redaction/sanitization before storage or display.
- Future loopback endpoints, plugins, browser data, credentials, media tools, and remote APIs are absent or inaccessible in M0-M6.
- No user-facing workflow suggests that SupaDL bypasses rights, protected-content restrictions, or source access controls.

## 13. Success States

- **Probe success:** resolved metadata is displayed, the safe filename/destination can be reviewed, and no full download has occurred.
- **Queued success:** the task is persisted as `QUEUED`, visible immediately, and starts only when policy makes it eligible.
- **Pause success:** all workers stop safely, a durable checkpoint exists, state is `PAUSED`, and Resume becomes legal.
- **Resume success:** source identity/range validation passes, only missing bytes are accepted, and progress continues monotonically.
- **Cancel success:** network work stops, state is `CANCELLED`, and partial-data handling matches the approved policy.
- **Retry success:** the task follows a legal retry transition and resumes/restarts according to source and partial-file validation.
- **Download success:** exact expected bytes are present, required checksum matches, finalization succeeds without overwrite, state is `COMPLETED`, and the UI shows the final path.
- **Recovery success:** reopening after a forced interruption produces a consistent recoverable task that can complete with the exact expected checksum.
- **Packaging success:** the clean supported Windows environment launches the artifact and completes the smoke workflow.

## 14. Loading, Empty, Error, and Interrupted States

### Loading/busy

- During probe, the dialog shows a non-blocking loading state, disables duplicate submission, and permits safe cancellation/close.
- During starting/pausing/verifying/finalizing, the selected task shows its current transitional state and disables incompatible actions.
- Unknown-length transfers show indeterminate progress while still showing transferred bytes and speed when measurable.

### Empty

- First launch and an empty All view explain that no downloads exist and provide a clear Add URL entry point.
- Filtered views distinguish “no tasks in this category” from a load failure.
- Missing optional metadata displays an explicit unknown/not provided value rather than blank misleading data.

### Errors

- Invalid fields show field-specific feedback without creating or starting an invalid task.
- Probe/network/server/TLS/range/source/checksum/disk/permission/collision/database errors map to typed categories and actionable sanitized text.
- Retryable failures show the pending attempt/backoff state and allow cancellation; exhausted retries become a stable failed state.
- Unauthorized/forbidden/not-found results do not enter automatic retry loops.
- Database startup or migration failure prevents unsafe operation and offers a documented recovery path without silently replacing user data.
- Cleanup failure identifies remaining application-owned artifacts without claiming success.

### Interrupted

- Closing during a probe or transfer never leaves a final file falsely marked complete.
- Session/process termination during transfer, checkpoint, assembly, verification, or finalization is reconciled on next startup.
- Network loss leaves a retrying or stable recoverable/failed state according to policy and does not freeze the UI.

## 15. Edge Cases

- Empty URL, whitespace-only URL, malformed host, unsupported scheme, URL user-info, internationalized host, long URL, fragment, and sensitive query string.
- Redirect loop, redirect cap exceeded, HTTP-to-HTTPS and HTTPS-to-HTTP redirect policy, and final URL changing between probes.
- `HEAD` rejected, incorrect `HEAD`, absent length, chunked transfer, compressed/transformed response, misleading `Accept-Ranges`, malformed or inconsistent `Content-Range`.
- Zero-byte resource, one-byte resource, exactly 8/64/512 MiB boundaries, sizes not divisible by segment count, and files larger than available disk space.
- Duplicate Content-Disposition parameters, encoded `filename*`, invalid encoding, empty filename, traversal, absolute/UNC/drive paths, reserved Windows devices, trailing dots/spaces, control characters, Unicode normalization, very long names, and extension-only names.
- Destination created/deleted/renamed during probe or transfer; destination permission changed; destination is a symlink/junction; final filename appears just before finalization.
- User double-clicks Add/Start/Pause/Resume/Cancel/Retry; clicks actions during state change; closes a dialog during a slow probe; closes app during merge or checksum.
- Session crash immediately before/after a checkpoint or transactional state update.
- Database claims more/less progress than durable partial files; segment file missing, oversized, truncated, or externally modified.
- ETag weak/strong transition, ETag removal, Last-Modified change, length change, and validator conflict.
- Resume request gets `200`, wrong `206`, wrong total, overlapping range, shorter range, extra bytes, or source change mid-segment.
- `429` with seconds/date/invalid/huge `Retry-After`; repeated `5xx`; transient DNS; connection reset; read stall; TLS failure.
- Zero/negative/stale speed samples, sleep/wake or clock adjustment, unknown size, completed zero-byte file, and aggregate rate changes as jobs start/stop.
- Checksum uppercase/lowercase, whitespace, wrong length, unsupported algorithm, match, mismatch, and cancellation during verification.
- Disk full during segment write or merge; permission error during final rename; non-atomic cross-volume destination; cleanup partially fails.
- First launch, corrupt/locked database, migration interruption, unsupported schema version, and settings with unknown or invalid values.
- High DPI, minimum supported window size, long filenames/error text, keyboard-only use, no selected row, and empty filter results.

## 16. Testing Checklist

### 16.1 Unit tests

- [ ] Legal and illegal lifecycle transitions, timestamps, and immutability rules.
- [ ] Segment planning property tests across boundary, tiny, prime, and random sizes.
- [ ] Filename parsing/sanitization matrix including traversal, reserved devices, Unicode, and length limits.
- [ ] Destination containment and collision naming, including finalization races.
- [ ] Retry classification, bounds, backoff, jitter, and `Retry-After` parsing with fake time/randomness.
- [ ] Content-Disposition and Content-Range parsing, including malformed input.
- [ ] Checksum known vectors, accepted input formats, and mismatch behavior.
- [ ] Progress monotonicity, smoothing, ETA unknown/stalled/reset conditions, and aggregate metrics.
- [ ] URL/header/error redaction proves representative literal secrets never appear in emitted output.
- [ ] Settings defaults, validation boundaries, serialization, and platform path selection.
- [ ] Domain dependency/import checks.

### 16.2 Fixture-server integration tests

- [ ] Ordinary known-length `200` download.
- [ ] Valid `206` probe and ranged downloads.
- [ ] Range advertised but ignored.
- [ ] `HEAD` rejected while minimal `GET` works.
- [ ] Redirect chain, loop, and cap.
- [ ] Chunked/unknown content length.
- [ ] Disconnect after a configured byte count.
- [ ] Slow response and cancellation.
- [ ] `429 Retry-After` variants.
- [ ] `500`/`502`/`503`/`504` recovery and exhaustion.
- [ ] `401`/`403`/`404` terminal behavior.
- [ ] Changed ETag, Last-Modified, or length.
- [ ] Invalid, mismatched, short, and oversized Content-Range responses.
- [ ] Per-host connection count instrumentation never exceeds the configured cap.
- [ ] Response bodies are streamed rather than fully buffered.

### 16.3 End-to-end tests

- [ ] Add URL -> probe -> start -> finalize -> exact hash.
- [ ] Add URL -> queue -> automatic slot start -> exact hash.
- [ ] Pause -> close process -> reopen -> resume -> exact hash.
- [ ] Segmented download -> merge -> exact hash and cleanup.
- [ ] Segmented pause/restart/resume -> exact hash.
- [ ] Forced crash at representative transfer/checkpoint/merge/verify/finalize points -> safe recovery.
- [ ] Misleading/broken ranges -> safe fallback/failure, never corrupted completion.
- [ ] Checksum match and mismatch visible outcomes.
- [ ] Cancel/remove behavior matches approved cleanup policy.
- [ ] Disk full, permission, and destination conflict surface correct state and message.
- [ ] UI remains interactive during slow transfer and checksum verification.
- [ ] Shutdown leaves no new workers and all active tasks recoverable.

### 16.4 CI and release tests

- [ ] `ruff check` passes.
- [ ] Ruff formatting check passes.
- [ ] Chosen type checker passes at the approved strictness.
- [ ] Unit and integration suites pass without public internet access.
- [ ] Core/domain critical-path coverage is at least 80% once stable, without excluding meaningful branches merely to raise the number.
- [ ] Dependency vulnerability audit has no unaccepted release-blocking finding.
- [ ] PyInstaller build smoke test passes.
- [ ] Packaged application launches on each supported clean Windows target.
- [ ] Packaged smoke download and restart/resume workflow pass.
- [ ] Release artifact, licenses/notices, README, changelog, security docs, and limitations are present and version-consistent.

## 17. Milestone and SUP Task Acceptance Matrix

All criteria in this matrix are cumulative with the cross-cutting validation, security, error-state, test, and Definition of Done requirements.

| Task | Pass/fail acceptance criteria |
|---|---|
| SUP-001 | Fresh install succeeds; `supadl` imports; entrypoint/help works; test command runs; repository baseline docs and metadata exist. |
| SUP-002 | Ruff, formatter, pytest/pytest-asyncio, and selected type checker run through documented deterministic commands and pass on the skeleton. |
| SUP-003 | Typed defaults validate; platform-aware paths contain no hard-coded user directory; invalid concurrency/timeouts fail safely; settings round-trip. |
| SUP-004 | Structured logging initializes once; context is present; test literals for auth/cookie/token/query secrets are absent from all emitted log text. |
| SUP-101 | Domain models/states/errors import without infrastructure or Qt; primitives serialize; invalid transitions are rejected without mutation. |
| SUP-102 | Filename/path attack matrix passes; every result is a safe basename; fallback and collision names are deterministic. |
| SUP-103 | Fixture HTTP calls honor explicit lifecycle/timeouts/redirect cap/user agent; client closes cleanly; TLS remains verified. |
| SUP-104 | `HEAD` rejection and redirects work; minimal probe avoids full download; misleading range headers are correctly classified; metadata persists. |
| SUP-105 | Fixture SHA-256/length match; response is streamed to partial storage; incomplete/extra data is not finalized; resources close on all paths. |
| SUP-106 | Cancellation stops promptly, schedules no new work, closes resources, and leaves partial state/cleanup exactly as approved. |
| SUP-107 | Test subscribers receive monotonic, bounded progress events independent of Qt; event rate does not equal packet/chunk rate. |
| SUP-201 | Fresh SQLite database initializes; reopen is idempotent; schema version is queryable; failed migration rolls back. |
| SUP-202 | All task/segment fields round-trip; relationships/invariants hold; multi-record updates are transactional; consumers use repository interfaces. |
| SUP-203 | Every valid transition is durable and atomic; invalid transitions preserve state; concurrent/stale commands cannot bypass policy. |
| SUP-204 | Checkpoints respect configured time/byte thresholds, avoid per-chunk writes, and reconcile with durable files after forced interruption. |
| SUP-205 | Pause/restart/resume exact-hash test passes; resumed range is validated; incompatible `200` cannot append corrupt bytes. |
| SUP-206 | Strong ETag and conservative fallback validation work; changed source becomes `SOURCE_CHANGED`; no unsafe append occurs. |
| SUP-207 | Stale active states recover to the approved deterministic state and can safely resume or restart after application crash. |
| SUP-301 | Property tests prove inclusive ranges exactly cover `[0,size-1]` with no gaps/overlaps across thresholds and non-divisible sizes. |
| SUP-302 | Actual valid `206` behavior enables segmentation; `Accept-Ranges` alone does not; transformed/unknown resources remain single-stream. |
| SUP-303 | Worker requests/writes only its range; valid slices match; invalid status/range/length fails safely and is never assembled. |
| SUP-304 | Coordinator respects per-download/per-host bounds, aggregates progress, and propagates pause/cancel/fatal source failure to all workers. |
| SUP-305 | Only complete validated segments assemble in exact order; final length/hash match; successful cleanup removes obsolete segment files. |
| SUP-306 | Segment offsets persist; pause/process restart/resume requests missing bytes only; final exact hash matches. |
| SUP-307 | Server range regression triggers approved single-stream fallback or typed failure; incompatible partial data is isolated; corruption cannot be completed. |
| SUP-401 | Add/start/pause/resume/cancel/retry/remove work through a Qt-independent service; commands enforce legal transitions and return typed errors. |
| SUP-402 | Priority/reorder is durable and deterministic; active count never exceeds limit; next eligible work starts on slot release; no starvation. |
| SUP-403 | Instrumented fixture concurrency never exceeds the configured host cap across tasks, segments, probes, and retries per documented counting policy. |
| SUP-404 | Transient and 429/5xx behaviors retry within bounds; `Retry-After` is honored; 401/403/404 and TLS failures are terminal as specified; tests use fake time. |
| SUP-405 | SHA-256/SHA-512 vectors pass; verification streams; match completes; mismatch records expected/actual and never reports `COMPLETED`. |
| SUP-406 | Collision policy is explicit and race-safe; unrelated existing files are not silently overwritten; successful finalization is atomic where possible. |
| SUP-407 | Per-task/aggregate byte counts, smoothed speed, and ETA pass known/unknown/zero/stalled/resume cases and never show invalid values. |
| SUP-501 | UI launches with injected services; base views/actions exist; core does not import PySide6; network/disk work cannot block the UI thread. |
| SUP-502 | One event-driven table model exposes required columns, updates safely, and does not duplicate domain state. |
| SUP-503 | Valid URL can be probed and queued/started; invalid fields/errors are actionable; slow probe leaves UI responsive and duplicate submit disabled. |
| SUP-504 | Lifecycle buttons call application commands, reflect event-driven state, and are enabled only for legal transitions; stale actions still fail safely. |
| SUP-505 | All/Active/Queued/Completed/Failed filters return the correct shared task set and show correct empty states. |
| SUP-506 | Details show source/final metadata, validators, segments, timestamps, and sanitized errors without exposing secrets. |
| SUP-507 | Required settings validate, persist, reload, and affect work according to the documented active/future policy. |
| SUP-508 | Tray is absent or its minimize/exit behavior is explicit, testable, and consistent with clean shutdown/recovery. |
| SUP-601 | Fixture server deterministically implements all documented normal/range/failure/validator scenarios and exposes expected size/hash/concurrency data. |
| SUP-602 | Crash/restart E2E tests cover transfer, checkpoint, merge, verify, and finalize boundaries and always recover without corrupted completion. |
| SUP-603 | Sparse/generated large-file tests prove streaming, bounded memory, checkpointing, and segmentation without committing giant fixtures. |
| SUP-604 | Windows path tests cover reserved names, length, traversal, drive/UNC, Unicode, collisions, and supported filesystem finalization behavior. |
| SUP-605 | Repeatable PyInstaller artifact launches and completes approved clean-machine smoke workflows with required Qt resources. |
| SUP-606 | Application/file metadata and artifact names carry one consistent approved version/platform/architecture. |
| SUP-607 | Locked dependency inventory, licenses/notices, and chosen product license are complete for distributed components. |
| SUP-608 | Threat model reviews URLs, redirects, TLS, filenames/paths, logs/secrets, database/temp storage, external commands, packaging, and deferred integration boundaries; release blockers are resolved. |

## 18. Definition of Done for Every SUP Task

A SUP task passes only when all applicable statements are true:

- [ ] Only the requested task or smallest necessary dependency group was implemented.
- [ ] The task-specific matrix criteria and all applicable cross-cutting criteria pass.
- [ ] Automated tests were added or updated for success, failure, and relevant edge cases.
- [ ] Relevant tests, lint, format, and type checks were run and pass.
- [ ] Public behavior, schema, setup, security, or API changes are documented.
- [ ] No unrelated refactor or deferred feature was introduced.
- [ ] Owned clients, workers, handles, and database resources close cleanly.
- [ ] Repository remains installable, runnable, and green.
- [ ] Changed files and commands/results are reported.
- [ ] Remaining limitations and deferred decisions relevant to the task are reported.

## 19. Final Beta Pass/Fail Acceptance Criteria

The first public beta is accepted only when every item below passes:

- [ ] OQ-01 through OQ-12 have documented decisions or an explicitly approved deferral that does not make another beta criterion untestable.
- [ ] M0-M6 and SUP-001 through SUP-608 meet their applicable matrix criteria and Definition of Done.
- [ ] A supported user can add, probe, start or queue, pause, close, reopen, resume, cancel, retry, inspect, and remove a direct HTTP/HTTPS download through the desktop UI.
- [ ] Direct, resumed, and segmented fixture downloads produce exact expected hashes.
- [ ] Broken/misleading range responses, changed sources, early EOF, retries, crashes, checksum mismatches, disk errors, and destination races never produce a silently corrupt `COMPLETED` file.
- [ ] Task, segment, setting, and schema state survive process restart and recover according to the approved policy.
- [ ] Global, per-download, and per-host concurrency never exceed configured bounds.
- [ ] Retry count/timing is bounded; valid `Retry-After` is honored; non-retryable HTTP/TLS errors are not blindly retried.
- [ ] Filename and destination attack matrices prove downloaded bytes cannot escape approved storage or silently overwrite an unrelated file.
- [ ] Normal logs, persisted errors, and UI details contain none of the representative credentials, authorization headers, cookies, tokens, or signed-query secrets used by security tests.
- [ ] The PySide6 UI remains responsive during probe, transfer, pause, resume, merge, checksum verification, and shutdown tests.
- [ ] Shutdown schedules no new work, closes owned resources, and leaves active work recoverable.
- [ ] Unit, integration, E2E, formatting, lint, typing, dependency-audit, coverage, and build gates pass in CI according to the approved configuration.
- [ ] The versioned Windows artifact launches and completes the approved smoke and restart/resume workflows on each supported clean environment.
- [ ] README, architecture, state-machine, security, ADRs, changelog, dependency/license notices, known limitations, and protected-content policy match the delivered build.
- [ ] Browser integration, third-party plugins/resolvers, HLS/DASH/FFmpeg, daemon/remote API, scheduling, bandwidth/proxy/auth profiles, and auto-update remain explicitly deferred and are not presented as supported beta functionality.

## 20. Traceability to Source Plan

- Sections 1-7 map product intent, actors, scope, architecture, assumptions, and unresolved choices from source Sections 1-7, 24, 30, and 32.
- FR-030 through FR-038 map the source state machine and application-use-case rules.
- FR-040 through FR-048 map the HTTP probe strategy.
- FR-050 through FR-057 map filename and destination safety.
- FR-060 through FR-112 map single-stream, persistence, resume, segmentation, and assembly requirements.
- FR-120 through FR-149 map queue, concurrency, retry, checksum, progress, speed, and ETA requirements.
- FR-150 through FR-187 map desktop UI, cleanup, packaging, documentation, and release requirements.
- NFR, data, validation, permission, state, edge-case, and test sections make the source security baseline, testing strategy, CI gates, working rules, and Definition of Done independently verifiable.
- The milestone matrix covers every M0-M6 task ID listed in the Markdown master plan, including IDs summarized rather than expanded in the PDF.

