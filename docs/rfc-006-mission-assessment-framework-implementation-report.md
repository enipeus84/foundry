# RFC-006 — Mission Assessment Framework Implementation Report

Status: merged in PR #16.

## Scope

Implemented the shared framework and migrated Financial Independence only.
No Financial Resilience, Pension Independence, Mortgage Freedom or Children
assessment, target, threshold, evidence rule or provider was added.

## Repository and baseline

- Canonical repository: `~/Projects/foundry`
- Base commit: `452fa3fc1ec6da4f0bb484fb30b76a340b336783`
- Branch: `rfc-006-mission-assessment-framework`
- Declared environment: `.[dev,web]`
- Baseline: **345 collected, 345 passed**

## Architecture mapping

| Approved decision | Repository result |
|---|---|
| Definition discovery/order | Core `MissionDefinition` registry plus Finance's four ordered definitions |
| Domain-neutral milestone/direction | Core `MissionMilestone` with explicit destination direction/value |
| Closed Core vocabularies | Core trajectory, margin and confidence vocabularies with exact approved labels; trajectory tone is explicit presentation metadata, never inferred |
| Presentation metadata | `TelemetryItem` supplies label, format and qualifier |
| Generic route | Authenticated `/missions/{slug}` resolved from definitions |
| Provider isolation | Registry validates identity, scope, type and availability/value consistency, then returns a generic unavailable envelope on provider failure |
| FI migration | Existing calculations retained; new trajectory/margin/confidence/milestone/telemetry fields added |
| Shared-renderer cleanup | Removed fixed lanes, mission-name classifier, fixed FI route/title/definition, FI link branch, metric-label override and RFC-005 phase/flight terminology |

## Behavioural equivalence

FI retains the accessible-assets policy, threshold boundaries, schedule
status rules, ETA, low/base/high sensitivity calculations, trajectory,
delta-v precision, recommendation ranking/amount/impact, provenance,
read-only operation and deterministic replay. Regression tests cover those
outputs. The intended user-visible vocabulary change is `Ahead` to
`Accelerated`.

## Compatibility

Historical events require no migration. One documented deprecated scalar
adapter remains for Missions without assessment policy. RFC-005 aliases and
fields remain temporarily for source compatibility; new consumers use the
RFC-006 contract. Exact removal criteria are in
[`rfc-006-technical-debt.md`](rfc-006-technical-debt.md).

## Security by Design

The completed checklist and threat assessment are in
[`rfc-006-mission-assessment-framework.md`](rfc-006-mission-assessment-framework.md).
Automated evidence includes household/cross-scope envelope handling,
malformed-provider isolation, unsafe/unsupported definitions, stale and
absent evidence, separate observations/forecasts, no invented policy,
deterministic output and safe generic routes.

## Verification

- Final focused Core/Finance/Mission Control suite: **136 passed**
- Full suite: **393 collected, 393 passed** with the existing Starlette
  TestClient deprecation warning
- `./validate.sh`: security documentation COMPLETE; repository documentation
  COMPLETE; 393 tests passed; deterministic replay/model replacement exercised
  with repository mocks. With no provider keys present, the harness correctly
  reported “architecture exercised — not real-model V1.0 validation” and
  returned its documented non-zero mock-only verdict.
- Architecture Gate: **APPROVE (Beta)** — 0 Critical, High, Medium or Low
  findings after temporal-boundary, explicit-tone and availability/value
  remediation
- Security Gate: **APPROVE** — 0 Critical, High, Medium or Low findings

This report records the final pre-merge evidence accepted for PR #16.
