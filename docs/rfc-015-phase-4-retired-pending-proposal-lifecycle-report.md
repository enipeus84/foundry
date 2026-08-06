# RFC-015 Phase 4 — Retired Pending Proposal Lifecycle

## Outcome

Retiring a Capture Target now deterministically rejects every pending proposal
for that household and stream. The terminal state reuses the existing
`core.observation_proposal.updated` lifecycle event with `resolution: rejected`;
no canonical event kind or payload is added.

## Lifecycle

`CaptureTargetRegistry.retire()` appends the immutable retirement event first,
then folds the proposal inbox and appends one rejection for each matching
pending proposal in proposal-ID order. The rejection reason identifies the
retired stream and the actor is the retirement actor. Confirmed, rejected and
superseded proposals remain unchanged. A repeated retirement is a no-op, so it
cannot append duplicate lifecycle events.

## History and replay

Streams, proposals, envelopes, evidence and provenance remain in the log.
Replay folds the ordinary proposal lifecycle and reproduces the rejected state
without a clock or side store. The transition is household-scoped through the
retirement command and proposal household match.

## Validation

Focused regression: **59 passed, 1 upstream FastAPI/Starlette deprecation
warning**. Coverage includes no-pending retirement, one and multiple pending
proposals, completed and rejected proposals, deterministic replay and repeated
retirement. Full regression: **695 passed, 1 upstream FastAPI/Starlette
deprecation warning**.
