# RFC-016 — `DEBT-016-P3-01` Dormancy Remediation Implementation Report

**Candidate branch:** `rfc-016-dormancy-remediation-candidate`
**Frozen architecture parent:** `5ca521b3b1155dad71b1f4a775bd6e1e37659307`
**Classification:** focused implementation; independent TELMU and SAFE review pending.

## Payoff

`MissionTargetProjection.in_force(mission_id, as_of)` now returns no target at
or after the Mission's earliest valid applicable canonical closure, while
continuing to return the historical target before that closure.

## Implementation boundary

The only production change is `src/foundry/core/mission_targets.py`. During its
existing deterministic rebuild, the projection scans canonical log order for
exact `core.mission.declared` and `core.mission.closed` kinds. A closure is
retained only when its non-empty string `entity_id` was declared earlier in
that replay; the first such closure timestamp for each Mission is retained.
`in_force` then returns `None` when `as_of >= closure_timestamp`, before
applying the unchanged target effective-time, withdrawal, supersession and
conflict rules.

No latest `Mission.status` is consulted. No closure timestamp is added to the
Mission dataclass. The projection writes no event and adds no consumer-side
filtering or explanation path.

## Frozen replay evidence

The focused matrix covers active targets; pre-boundary, exact-boundary and
post-boundary answers; fresh historical replay; withdrawal; supersession;
Mission isolation; hostile redeclaration; duplicate applicable closures;
pre-declaration closure; malformed, unrelated and wrong-kind Mission history;
and deterministic fresh replay. Existing Phase 3 target-management regression
is run unmodified alongside the focused cases.

Results: focused RFC-016 run `85 passed, 1 warning`; full repository suite
`877 passed, 1 warning`. The warning is the pre-existing FastAPI/TestClient
`httpx` deprecation warning. `git diff --check` is clean.

## Scope and debt

No new canonical event, migration, Mission lifecycle change, Mission Assessment,
Phase 3 UX change, Finance change, Mission dataclass change, or RFC-017 change
is included. `DEBT-016-P3-01` remains **OPEN** until independent review and
governed completion; this candidate does not close it.
