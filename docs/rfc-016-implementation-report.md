# RFC-016 — Mission Target Framework: Implementation Closeout

**Status:** Complete — merged to `main` by [PR #44](https://github.com/enipeus84/foundry/pull/44).
**Merge commit:** `e0d500c37faa92e2ee8746333ee4825186a10395`.

RFC-016 delivers the frozen Phase 1 Core Mission Target contract and Phase 2
Finance metric-descriptor seam. The canonical event set is
`core.mission_target.declared` and `core.mission_target.closed`; the projection
refuses `core.mission_target.updated`. The implementation includes append-only
lifecycle handling, typed quantities, deterministic replay, as-of resolution,
supersession, withdrawal, conflict refusal, and the locked Finance descriptors.

Mission Assessment adoption, assessor changes, Mission instantiation, UI and
all Phase 3–5 work remain outside this release.

## Assurance trail

- [Frozen architecture](rfcs/RFC-016-mission-target-framework.md) and
  [freeze record](reviews/RFC-016-architecture-freeze-record.md)
- [SAFE review](reviews/RFC-016-safe-review.md) and
  [SAFE confirmation](reviews/RFC-016-safe-confirmation.md)
- [Governor merge authority](reviews/RFC-016-governor-merge-authority.md)
- [Accepted technical debt and observations](rfc-016-technical-debt.md)

## Final validation

Post-merge validation on `main`: **707 passed**. `git diff --check` is clean,
the working tree is clean, and local `main` equals `origin/main`.
