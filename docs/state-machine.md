# Download State Machine

The transfer lifecycle is planned for M1 and later. M0 defines this contract so future
workers, persistence, and UI code share one transition policy.

```text
CREATED -> PROBING -> QUEUED -> DOWNLOADING
                                  |
                                  +-> PAUSING -> PAUSED -> QUEUED/DOWNLOADING
                                  +-> VERIFYING -> COMPLETED
                                  +-> FAILED -> QUEUED/DOWNLOADING (explicit or policy retry)
                                  +-> CANCELLED
```

## Invariants

- One domain/application service owns legal state transitions.
- Widgets and workers cannot assign lifecycle state directly.
- Every transition is persisted transactionally once persistence exists.
- A stale active state after a crash becomes a deterministic recoverable state.
- `COMPLETED` is immutable except for an explicit history-removal action.
- Cancellation stops new scheduling before approved temporary-data cleanup is performed.

The crash-recovery and cancelled-partial cleanup policies remain explicit pre-M2 decisions
in the detailed acceptance criteria.
