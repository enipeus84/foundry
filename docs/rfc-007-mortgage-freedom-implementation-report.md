# RFC-007 — Mortgage Freedom Mission Implementation Report

Status: implementation complete; draft PR #17 open.

## Scope

Implemented Mortgage Freedom only as the second production Mission Assessment
provider. Financial Resilience and Pension Independence remain metadata-only
planned definitions. Children remains outside the hierarchy. No connector,
optimisation engine, persisted assessment or action workflow was added.

## Repository and baseline

- Canonical repository: `/Users/chrisparker-brads/Projects/foundry`
- Base commit: `3a7b929baad10f4860110c90116407fe33def949`
- Branch: `rfc-007-mortgage-freedom-mission`
- Declared environment: `.[dev,web]`
- Baseline: **393 collected, 393 passed**

## Architecture result

- Finance owns the evidence adapter, assessment policy, amortisation,
  milestones, margin, confidence, telemetry and recommendation.
- Core gains only optional, domain-neutral delta-v period and reference
  schedule presentation metadata. Provider-envelope validation fails closed
  for non-finite, calendar-unrepresentable or unpaired values. Routing and
  vocabularies are unchanged.
- Mission Control has no Mortgage Freedom branch or Finance import.
- The existing authenticated `/missions/{slug}` route renders the mission.
- Financial Independence remains on its existing provider and regression
  suite.
- Unimplemented missions retain no policy id, target, thresholds or status.

## Evidence and calculation

The demo event stream records every supplied mortgage/property value through a
manual evidence envelope with effective date, confidence, source and lineage.
It distinguishes the £450,000 purchase price from the £436,638.42 HPI dated
valuation reference for March 2025. The latter preserves its HPI provenance
and effective month and is not described as live or current valuation
evidence.
It also records the original 300-month term separately from the current
201-month remaining term. The original term and 1 July 2025 first payment
produce a contractual destination of 1 July 2050.
Low/expected/high paths are deterministic rate sensitivities, observations
remain separate from projections, and exact zero is the only completion state.

The expected payoff is 29 April 2043 for the correction-review evidence.
Delta-v reports **2,619.586 model days / 86 model months gained** against the
original contractual destination, and trajectory is **Accelerated**.
The two historical £30,000 overpayments are reflected only through the
observed balance and are never treated as recurring inputs.

The single recommendation reports a declared monthly overpayment,
expected payoff acceleration and projected interest avoided. It is suppressed
when liquidity evidence is absent or below the declared resilience floor.
Recommendation availability does not alter the achieved trajectory.

Mission Control now obtains current-value labels and formats from provider
telemetry, removes Scenario ids and adjustment keys from prose, and renders
defined label and schedule lanes at desktop and mobile widths. The shared
schedule lane is conditional on explicit provider metadata; Financial
Independence does not acquire Mortgage schedule semantics.

## Security by Design

The completed checklist is in
[`rfc-007-mortgage-freedom-architecture.md`](rfc-007-mortgage-freedom-architecture.md).
The assurance register and threat model are updated for manual mortgage
evidence, scope checks and hostile-envelope behavior.

## Compatibility

RFC-006 compatibility fields and its deprecated legacy scalar adapter are
unchanged and gain no new consumer. The RFC-007 manual evidence writer is a
deprecated migration adapter. Historical evidence events must continue to
replay after the writer is removed. Exact removal criteria are in
[`rfc-007-technical-debt.md`](rfc-007-technical-debt.md).

## Verification

- Focused Core contract/Mortgage evidence/assessment/definition/Mission
  Control suite: **159 passed**
- Full suite: **453 collected, 453 passed**, with the existing Starlette
  TestClient deprecation warning
- `./validate.sh`: security documentation COMPLETE; repository documentation
  COMPLETE; 453 tests passed; deterministic replay/model replacement exercised
  with repository mocks. With no provider keys present, the harness correctly
  reported “architecture exercised — not real-model V1.0 validation” and
  returned its documented non-zero mock-only verdict.
- `git diff --check`: clean
- Static Mission Control preview reviewed at desktop/tablet and 374px mobile
  widths: no horizontal overflow, out-of-bounds labels or measured text
  intersections; the schedule lane remains inside the hero at both widths
- Architecture Gate: **APPROVE (Beta)** — 0 open Critical, High, Medium or Low
  findings; the correction review's shared schedule semantics, provider
  presentation formatting and provider-envelope validation findings were
  corrected before commit
- Security Gate: **APPROVE** — 0 open Critical, High, Medium or Low findings
  after exact destination matching, raw-id removal, hostile-unit escaping and
  calendar-unrepresentable timestamp isolation were verified

The pull request must remain draft and must not be merged by the
implementation agent.
