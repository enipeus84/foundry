# RFC-015 Phase 3 — Retired Capture Target Telemetry Suppression

## Outcome

Phase 3 makes retirement operationally terminal without altering canonical
history. Retired streams remain declared, queryable and replayable, but no
longer produce stale telemetry, overdue capture prompts, pending-review queue
entries or subject-level unknown-material actions when no active target remains.

## Boundary

No event kind, payload or retirement rule changes. `core.telemetry_stream.retired`
continues to be the sole lifecycle fact. `TelemetryStreamRegistry.is_active()`
is the shared read-side lifecycle predicate used by Operations, acquisition
queue rendering and confirmation. Historical envelopes, proposals, evidence,
provenance and the retired stream declaration remain available.

## Determinism

Suppression is a pure projection of the existing retired-stream set. The same
event log and evaluation time produce the same queue, terminal state and
retired-stream count. A retired stream cannot be captured or confirmed, and
Phase 2 bootstrap remains unchanged: its existing retirement-aware no-resurrection
behaviour continues to apply.

## Deferred lifecycle item

**M1 — retired pending-proposal disposition** is deferred to RFC-015 Phase 4.
Phase 3 suppresses these proposals from operational action and preserves them
as immutable history; it introduces no invented resolution or lifecycle event.

## Validation

Focused regression: **55 passed, 1 upstream FastAPI/Starlette deprecation
warning**. Coverage includes retired stale and overdue suppression, pending
action queue suppression, mixed active/retired streams, confirmation refusal
after retirement, historical evidence retention and replay equivalence. Full
regression: **693 passed, 1 upstream FastAPI/Starlette deprecation warning**.
