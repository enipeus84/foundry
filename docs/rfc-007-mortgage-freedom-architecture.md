# RFC-007 — Mortgage Freedom Mission

Status: implemented for draft review.

## Decision

Mortgage Freedom is the second production `MissionAssessmentProvider` and the
first proof implementation of the RFC-006 framework. The implementation adds
Finance-owned evidence selection, mortgage policy, deterministic projections,
milestones, margin, confidence, telemetry and one scenario-modelled
recommendation. It does not add a second assessment engine.

Core, generic routing and Mission Control remain domain-neutral. Mortgage
Freedom is discovered from its `MissionDefinition`, associated with an active
Mission by stable policy id and rendered from the same contract as Financial
Independence. Searches of the shared renderer contain no defined Finance
mission name.

Financial Resilience and Pension Independence remain metadata-only planned
definitions. Children remains outside the fixed Finance hierarchy. No other
mission assessment, connector, optimisation or write workflow is implemented.

## Identity and destination

- Definition: `mortgage-freedom`, canonical Finance order 4.
- Policy: `finance.mortgage_freedom.v1`.
- Target metric: `finance.mortgage_balance`.
- Destination: exactly GBP 0, with `lower_is_better` direction.
- Scope: one active household, its active members, one active mortgage
  obligation and one member-owned property secured by that obligation.
- Completion: only an observed zero balance marks the mission complete.

The policy supports a capital-repayment mortgage with a declared fixed-rate
period. Unsupported products fail closed; no repayment policy is inferred.

## Manual evidence adapter

`finance.mortgage_evidence.recorded` is a narrow Finance event envelope. Each
item preserves:

- the obligation id and governed field;
- the supplied value and optional unit;
- effective date;
- asserted confidence;
- source;
- lineage; and
- event id.

`MortgageEvidenceProjection` is a deletable, deterministic fold. Unsupported,
malformed, non-finite or hostile envelopes are retained as invalid event ids
and make Mortgage Freedom not evaluable only when they can apply to the
selected obligation at the assessment time. Future or unrelated malformed
records do not poison the assessment; an envelope whose obligation or time
cannot be placed safely is conservatively global. Payload and exception text
are never exposed. Validation occurs before a supported writer appends, so
rejected input does not partially mutate the log.

The synthetic proof data records every value in the approved brief. The
£450,000 figure is the purchase price. The separate £436,638.42 figure is an
HPI dated valuation reference for March 2025, with HPI provenance and that
effective month preserved; it is not live or current valuation evidence.
Where the brief supplies only a month, lineage records that precision. Where
an overpayment occurrence date is absent, the evidence is recorded as known
at the assessment date; no occurrence date is invented.

This is a deprecated migration adapter, not a new integration layer. Its
removal criteria are in
[`rfc-007-technical-debt.md`](rfc-007-technical-debt.md).

## Deterministic assessment

The projection is a monthly capital-repayment model:

1. observed current balance is the starting point;
2. the declared current rate applies through the fixed-rate expiry;
3. declared low, expected and high post-fix rates generate ordered sensitivity
   paths;
4. the declared monthly payment reduces interest plus capital;
5. a path stops at zero and never becomes negative; and
6. forecast points never become observations.

The supplied assumptions are explicit data, not hidden policy:

- low post-fix rate 3.33%;
- expected post-fix rate 4.33%;
- high post-fix rate 5.33%;
- 480-month maximum forecast horizon;
- balance stale after 120 days;
- property valuation stale after 365 days; and
- no acceleration recommendation below 12 months of liquidity runway.

The sensitivity envelope is not a probability distribution. The user-facing
contract calls the middle path expected; Core retains the domain-neutral
`ForecastPoint.base` field.

## Milestones and ETA

Milestones are Finance policy expressed in Core contracts:

1. Repayment Underway — above 75% of original advance.
2. Building Equity — above 25% and at or below 75%.
3. Final Approach — above zero and at or below 25%.
4. Mortgage Free — observed balance exactly zero; completion.

Each milestone carries lower-is-better direction, value bounds, destination,
completion and expected-path ETA. The mission ETA is the expected-path payoff
date.

## Trajectory, margin and confidence

These dimensions are computed independently.

Trajectory compares low/expected/high payoff dates with the declared mission
target:

- Complete at observed zero;
- Accelerated when the high-rate path reaches the target;
- Nominal when the expected path reaches it;
- Constrained when only the low-rate path reaches it;
- Critical when the expected path has no payoff inside the horizon; and
- Divergent otherwise.

Presentation tone is returned explicitly by the policy. Mission Control does
not derive colour from trajectory.

Mission Margin measures resilience and operating buffer from four independent
signals: calculated LTV, liquidity runway, fixed-rate protection and recorded
overpayment flexibility. Versioned thresholds are in Finance policy code.
Affordability is explicitly unavailable because this Burn has no verified
income/expenditure contract evidence.

Mission Confidence measures the assessment evidence itself. Missing,
malformed or low-confidence required evidence is Insufficient and not
evaluable. Stale or lower-confidence manual evidence is Provisional. Fresh,
attributable manual evidence is Supported. The adapter never claims
Established. Confidence is not inferred from trajectory or margin.

## Delta-v and recommendation

Delta-v is payoff time saved. The expected payoff from the current observed
balance is compared with the expected contractual-payment path from original
advance and mortgage start.

One active structured Scenario may be surfaced. It states:

- the declared monthly overpayment;
- expected-path payoff acceleration; and
- expected-path projected interest avoided under the declared rate
  assumptions.

No recommendation is emitted when liquidity runway is absent, unevaluable or
below the explicit floor. Financial Resilience therefore takes precedence.
The implementation never recommends a maximum, never writes an action and
never persists an assessment.

## Security Considerations

- **Authentication:** No identity flow or public route changes. The generic
  mission route checks the session before definition lookup, including unknown
  slugs.
- **Authorisation:** Assessment accepts only an active household `Subject`.
  Borrowers and property owners must be active members of that household.
  Cross-household or member-scope reuse fails closed. This represents scope;
  it does not claim a multi-user authorisation model.
- **Sensitive data and secrets:** Mortgage observations become permanent
  Finance events. No credential, network destination or application log
  payload is added. The included values are marked synthetic demo data.
- **Auditability:** Manual evidence records source, lineage, effective date,
  asserted confidence and event id. Assessment and rendering are deterministic
  and read-only. Actor/source/confidence remain assertions, not authenticated
  attestations.

## Threat Assessment

- **Trust boundaries:** Adds a narrow manual in-process evidence envelope, but
  no external connector, credential, dependency or outbound destination.
  Provider output and route slug remain the RFC-006 untrusted envelopes.
- **Threat model:** T6 applies to household/member scope; T8 to hostile evidence
  envelopes; T10 to permanent manual-input mistakes. Existing residual risks
  remain visible and no new risk is silently accepted.
- **Failure and abuse:** Missing, future-only, stale, malformed, hostile,
  unsupported, repeated or cross-scope evidence is deterministic. Malformed
  evidence makes only Mortgage Freedom not evaluable. Existing events are
  preserved. Assessment performs no append and no partial write. The manual
  adapter inherits EventLog's documented single-writer constraint; concurrent
  general appends are not safe and RFC-007 does not claim otherwise.

## Validation

- **Evidence:** Contract registration/order, exact-zero/lower-is-better policy,
  ordered deterministic paths, ETA, delta-v, projected interest,
  recommendation precedence, household/member isolation, manual provenance,
  stale/absent/malformed/hostile evidence, provider isolation, authenticated
  generic routing, deterministic rendering and FI regression tests.
- **Deferred work:** Authoritative lender/property connectors, multiple
  mortgages, product variants, fees, early-repayment constraints,
  affordability, variable rates, exact lender day-count conventions and
  persisted actions are recorded in the technical-debt register.

This answers every question in the merged Security by Design checklist.
