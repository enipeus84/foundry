# RFC-015 Phase 2 — Runtime Bootstrap of Existing Household Capture Targets

## Outcome

Phase 2 implements the RFC-015 runtime bootstrap from canonical household
projections. It preserves the Capture Target Registry projection,
Finance-owned canonical discovery, UUIDv5 stream identity, append-only Core
declarations, RFC-011 acquisition and SAFE-012-01.

## SAFE Phase 2A remediation

The SAFE remediation burn fixes reporting rather than redesigning bootstrap.
Operations now derives its status from the registered-target count and the full
diagnostic set: it distinguishes successful bootstrap, no eligible entities,
partial completion, and failure; it never asserts that another target exists
without proving the count. Multiple diagnostics render as multiple concise
issues without exposing canonical UUIDs as user-facing labels.

The deterministic UUID stream identity is checked against every existing stream
before either paired registry append. A collision with incompatible stream
contents becomes a diagnostic and creates neither registration nor stream.

Tolerant projection construction now uses supported `EntityProjection.empty()`
and `FinanceEntityProjection.empty()` factories. These initialise the same
empty state as the normal constructors while deliberately leaving event replay
to bootstrap's per-event isolation loop.

The narrow event-authorisation record is
[`RFC-015 Phase 2A Diagnostic Event Amendment`](reviews/RFC-015-phase-2a-diagnostic-event-amendment.md).

## F1: startup availability

The web composition boundary attempts bootstrap once after the existing startup
seed hook. Discovery folds canonical events independently: a malformed event or
conflicting target produces a replayable
`core.capture_target_bootstrap.diagnostic` event and cannot stop the remaining
eligible targets. All applicable diagnostics are retained in the bootstrap
result and surfaced in Operations as a concise complete set; logging records
their count. Request-time console reconstruction remains read-only.

## F3: no partial declaration history

`FinanceCaptureTargetBootstrap` uses Finance's resolver-owned canonical
type/property table: pension, checking and savings accounts map to their
compatible properties without names, fixtures or seeded identities. A property
asset additionally requires canonical mortgage evidence proving it is the sole
primary residence. Each candidate is independently validated before its
registry declarations are appended. Existing matching active declarations emit
nothing; a repeated startup is a no-op, including for an already-recorded
diagnostic.

## Validation

Focused tests prove malformed ordinary household state cannot prevent startup;
diagnostics are appended and visible in authenticated Operations; a conflicting
target does not prevent another eligible target from being declared; successful
bootstrap remains idempotent; primary residence discovery, multiple cash
eligibility, stream retirement and display-name-independent identity remain
intact.

Focused RFC-015 regression: **21 passed, 1 upstream FastAPI/Starlette
deprecation warning**. Full regression: **689 passed, 1 upstream
FastAPI/Starlette deprecation warning**.

## Deployment preview

This environment has no production `FOUNDRY_DATA_PATH` or OAuth configuration.
The normal authenticated deployment preview was therefore unavailable; no
authentication bypass was used. The branch is returned to CAPCOM for fresh SAFE
review and Governor disposition.
