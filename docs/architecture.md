# SupaDL Architecture

## Direction

SupaDL is organized around a reusable application layer and transfer engine. Presentation,
CLI, browser, and future remote integrations must call the same use cases rather than own
download behavior.

```text
Presentation / CLI / future integrations
                  |
            Application API
                  |
      Domain policies and services
                  |
 Infrastructure ports and implementations
```

## Layer boundaries

- **Domain:** pure models, states, typed errors, and policies. No Qt, HTTPX, SQLite, concrete
  filesystem, or browser imports.
- **Application:** use cases, lifecycle coordination, scheduling, and events. It depends on
  domain types and infrastructure interfaces.
- **Infrastructure:** HTTP transport, files, persistence, checksum, clock, and logging
  implementations.
- **Presentation:** PySide6 models, views, controllers, and application bootstrap. It does
  not own transfer logic.
- **Integrations:** browser, resolver/plugin, and media boundaries. These are deferred.

## Implemented foundation

M0 contains only package bootstrapping, the CLI smoke entry point, typed configuration,
path resolution, and structured logging. It has no network, database, background-worker, or
GUI side effects at import time.

The first M1 slices add pure domain models and lifecycle policy under `supadl.domain`, plus
safe filename utilities under `supadl.storage`. Domain code imports neither storage nor any
HTTP, Qt, or database implementation. Filename extraction is also independent of network and
filesystem mutation so the probe service can supply untrusted metadata safely.

`supadl.transfer` owns HTTP infrastructure. Its factory creates configured `httpx.AsyncClient`
instances, while the caller owns their lifetime. The probe service receives a client through
constructor injection, streams only response headers, validates every outbound redirect URL,
and returns immutable serialization-ready metadata. No client or network task is created at
module import time.

The single-stream worker receives the same owned client plus a `PartialFileWriter`. The
writer constrains new `.part` files to one existing application-owned root and opens them
exclusively. The worker consumes raw response bytes in bounded chunks, validates the final
URL, validators, content encoding, and known length, then durably flushes the partial file.
It deliberately does not finalize, persist, retry, emit UI progress, or own cancellation yet.

## Dependency lifecycle

HTTP clients, future database connections, file handles, and asynchronous workers must have
an explicit owner and clean close path. Global clients and network access during import are
prohibited. HTTPX's connection limit is a defensive global bound; per-host scheduling remains
the responsibility of the future queue/coordinator in SUP-403.

## Planned decisions

ADR-003 records the accepted HTTPX transport and lifecycle boundary. Other planned records
will be added when their implementation boundaries are reached.
