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

The first M1 slice adds pure domain models and lifecycle policy under `supadl.domain`, plus
safe filename utilities under `supadl.storage`. Domain code imports neither storage nor any
HTTP, Qt, or database implementation. Filename extraction is also independent of network and
filesystem mutation so the future probe service can supply untrusted metadata safely.

## Dependency lifecycle

Future HTTP clients, database connections, file handles, and asynchronous workers must have
an explicit owner and clean close path. Global clients and network access during import are
prohibited.

## Planned decisions

Architecture decision records listed in the master plan will be added when their respective
implementation boundary is reached. ADR-001 through ADR-004 should be resolved before the
corresponding M1/M2 work is accepted.
