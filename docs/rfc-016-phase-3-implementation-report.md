# RFC-016 Phase 3 — Mission Target Management Implementation Report

**Status:** Implementation candidate ready for TELMU / SAFE. Merge not
authorised.

**Frozen authority:** `b7957d63524e49bedcf60273ff5634ebaf8861e3`

**Architecture parent / canonical baseline:**
`b35328e3b8e5df5106cfa7abb68e89a0177f4726`

**Candidate branch:** `rfc-016-phase-3-mission-target-management`

**Candidate SHA:** recorded in the BOOSTER return because this report is itself
part of that commit.

## 1. Payoff

An authorised operator can now manage the complete existing RFC-016 Mission
Target lifecycle under `/missions`: make a first declaration, replace the
in-force declaration by immutable supersession, and withdraw it. The surface
does not create Missions. An empty canonical world stays empty and rendering
writes nothing.

## 2. Architecture boundary

The implementation has exactly the six frozen handlers in the new
`src/foundry/mission_targets_web.py`. That module shares only Mission Control's
shell helpers and imports neither `operations_web.py` nor `acquisition_web.py`.
The Operations acquisition stack, Capture Contracts, Capture Target Registry,
Finance acquisition and all protected Core contracts are unchanged. No
telemetry stream, AssetRegistration, manual Finance draft, capture target,
Mission or household is created for this capability.

The only production changes are the four frozen surfaces:

| File | Change |
|---|---|
| `src/foundry/mission_targets_web.py` | new six-route operator surface, exact form parsing, review, stale-state refusal and lifecycle calls |
| `src/foundry/finance/mission_targets.py` | Finance-owned deterministic horizon mapping for the four locked metrics |
| `src/foundry/mission_control.py` | target projection added to `Console`; old `/missions` placeholder removed |
| `src/foundry/web.py` | projection composition and dedicated router registration |

## 3. Lifecycle evidence

First declaration calls the existing `MissionTargetProjection.declare()` with
no predecessor. Replacement reloads the projection, independently resolves the
current in-force target and passes that id as `supersedes`. Withdrawal reloads
and verifies that the reviewed target is still current before calling the
existing `withdraw()` gate. Tests assert the exact event sequence and payload:
declaration and replacement write `core.mission_target.declared`; withdrawal
writes generic `core.mission_target.closed` with `entity_id` and reason only.
The predecessor remains resolvable and replay returns the successor.

No mutable update event, payload extension or vocabulary value was added.

## 4. Review and staleness

Review is a dry run through the existing declaration validator and appends
nothing. It emits only operator inputs, Mission identity, a fresh declaration
CSRF token and `reviewed_in_force`: the id reviewed or literal `none`.

Approval rebuilds current canonical state, resolves the current predecessor
without consulting that assertion, and compares the two. Mismatch refuses with
no append. Only after a match does it re-normalise operator inputs, recompute
`effective_from`, revalidate and append. The assertion never enters an event
payload and never selects `supersedes`, metric semantics or horizon semantics.

Named tests separately cover double-submit/stale-`none`, concurrent tab
declaration, intervening withdrawal, intervening supersession, Mission closure
and target conflict. Another test proves that a fresh review after refusal can
successfully replace the new current target. Withdrawal approval has its own
intervening-withdrawal refusal case.

## 5. Authority and CSRF

All six routes require the existing signed session and configured allowed-email
equality. Household authority is the current server-derived active household;
it is never accepted from a form. Mission identity is resolved against current
canonical state, and declaration and withdrawal require `mission.status ==
"active"` at the POST boundary. A Mission already bound to another household
is neither offered nor disclosed.

The POST purposes are distinct: `rfc016-target-review`,
`rfc016-target-declare` and `rfc016-target-withdraw`. Form bodies must be
`application/x-www-form-urlencoded`, parse strictly, contain one value per key
and match the horizon-specific exact field set. Missing, expired and
cross-purpose tokens refuse. RFC-011, RFC-012 and RFC-013 tokens cannot cross
into approval.

## 6. Derived-state protection

The client can supply only Mission id, destination value, an applicable horizon
date, optional basis, withdrawal reason, CSRF and the non-authoritative
staleness assertion. Household, metric id, destination unit, dimension,
direction, horizon kind, `horizon_at`, approval-time `effective_from`,
`supersedes` and target entity id are derived by the server. Unexpected fields,
including every forged derived field in the TELMU matrix, refuse before any
append.

Finance owns the frozen mapping:

| Metric | Horizon |
|---|---|
| `finance.liquidity_runway` | `none` |
| `finance.accessible_assets` | `by_date` |
| `finance.pension_wealth` | `derived` |
| `finance.mortgage_balance` | `by_date` |

`horizon_at` is present only for `by_date`. `MetricDescriptor` and Core are
unchanged.

## 7. Basis

Basis remains optional, escaped at render, never parsed and bounded by the
existing 500-Unicode-character contract. The entry form and approval page both
state that approval creates permanent append-only canonical history and that
basis cannot be edited or redacted through this surface.

## 8. Empty and hostile worlds

No household, no Mission, no described metric and no horizon mapping each
produce an honest read-only state. Tests compare the event-log bytes before and
after render and assert that no Mission Target or Mission is fabricated.

Duplicate active targets, forked lineage, cycles and a prohibited updated event
render a conflict and make every write against that Mission refuse. Quiet is
never shown for conflicted canonical state.

## 9. Protected files and event boundary

Every file in frozen §12 remains absent from the diff. In particular,
`src/foundry/core/mission_targets.py` remains byte-identical with SHA-256:

`90cc500b3859bc47ef5ffb4813d4f513274eeb038aad8ccba481ca55101325a0`

The exhaustive canonical event boundary remains:
`core.mission_target.declared` and `core.mission_target.closed`.

## 10. Validation

Pre-flight reproduced the frozen baseline: **802 passed**, one pre-existing
FastAPI/TestClient deprecation warning, and clean `git diff --check`.

Candidate validation:

- focused Phase 3 plus touched web suites: **163 passed**;
- full repository suite: **872 passed**;
- warnings: the same single pre-existing FastAPI/TestClient deprecation warning;
- `git diff --check`: **clean**;
- protected-file identity and prohibited-import scans: **clean**.

## 11. Technical debt

`DEBT-016-P3-01` is recorded and unresolved. The active-Mission guard is a
surface mitigation only; the Core projection was not changed. The obligation
travels with the first production assessment, decisioning, recommendation or
Flight Deck consumer of `in_force` state, irrespective of future phase number.

`DEBT-016-P3-02` records that Finance horizon admissibility constrains this
writer rather than the canonical projection. Tolerance and backdated
`effective_from` remain explicit deferrals, not operator inputs.

## 12. SAFE handoff

SAFE should adversarially inspect the plain match-only staleness assertion,
especially the S11 prohibition against event-payload or supersession influence;
purpose separation across all three CSRF credentials; strict parsing and
hidden-field manipulation; last-active-household authority now gating a write;
cross-household non-disclosure; Mission-active rechecks; hostile conflict
behavior; basis permanence wording and escaping; the absence of acquisition
imports; the two-event boundary; and byte identity for every protected file.

## 13. Verdict

**CANDIDATE READY FOR TELMU / SAFE.** Merge remains unauthorised.
