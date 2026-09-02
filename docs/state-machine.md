# Download State Machine

The pure transition policy is implemented in `supadl.domain.policies` so future workers,
persistence, and UI code share one lifecycle contract.

```text
CREATED -> PROBING -> QUEUED -> DOWNLOADING
   |          |         |          |
   |          |         |          +-> PAUSING -> PAUSED -> QUEUED/DOWNLOADING
   |          |         |          +-> VERIFYING -> COMPLETED
   |          |         |          +-> COMPLETED (when no checksum is required)
   |          |         |          +-> FAILED -> QUEUED/DOWNLOADING
   |          |         +-> PAUSED
   +----------+---------+----------+-> CANCELLED
```

## Invariants

- One domain/application service owns legal state transitions.
- Widgets and workers cannot assign lifecycle state directly.
- Every transition is persisted transactionally once persistence exists.
- A stale active state after a crash becomes a deterministic recoverable state.
- `COMPLETED` is immutable except for an explicit history-removal action.
- `CANCELLED` is terminal in the transfer lifecycle.
- Cancellation stops new scheduling before approved temporary-data cleanup is performed.
- Transition timestamps are timezone-aware, monotonic, and normalized to UTC.

The crash-recovery and cancelled-partial cleanup policies remain explicit pre-M2 decisions
in the detailed acceptance criteria.
