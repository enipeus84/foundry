# RFC-015 Phase 2A — Bootstrap Failure Isolation

## Outcome

Phase 2A implements the RFC-015 runtime bootstrap from frozen main while
isolating the SAFE F1 and F3 failure modes. It preserves the Capture Target
Registry projection, Finance-owned canonical discovery, UUIDv5 stream identity,
append-only Core declarations, RFC-011 acquisition and SAFE-012-01.

## F1: startup availability

The web composition boundary attempts bootstrap once after the existing startup
seed hook. A `CaptureTargetBootstrapError` is caught there, recorded on app
state, and logged without financial values. The web process continues to start.
Authenticated Operations renders a truthful notice naming the affected canonical
entity and validation category, reason for the stop, and the fact that no new
targets were created. Request-time console reconstruction remains read-only.

## F3: no partial declaration history

`FinanceCaptureTargetBootstrap.plan()` replays canonical Core and Finance
projections, discovers every candidate, and validates every required asset and
telemetry declaration before its caller appends anything. This includes later
candidate conflicts, household mismatch, incompatible declaration fields and
primary-residence ambiguity. A validation error returns before the first
`core.asset_registry.declared` or `core.telemetry_stream.declared` event. A
successful plan then emits deterministic missing declarations only; a repeat is
a no-op.

## Validation

Focused tests prove malformed ordinary household state cannot prevent startup;
diagnostics are visible in authenticated Operations; validation failure leaves
the event history unchanged even where an earlier pension candidate would
otherwise be declared; competing streams cannot produce partial assets;
successful bootstrap remains idempotent; primary residence discovery, cash
eligibility, stream retirement and display-name-independent identity remain
intact.

`git diff --check` passed. Full regression: **683 passed, 1 upstream
FastAPI/Starlette deprecation warning**.

## Deployment preview

This environment has no production `FOUNDRY_DATA_PATH` or OAuth configuration.
The normal authenticated deployment preview was therefore unavailable; no
authentication bypass was used. The branch is returned to CAPCOM for fresh SAFE
review and Governor disposition.
