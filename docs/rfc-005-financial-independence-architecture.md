# RFC-005 — Financial Independence Mission Assessment

Status: implementation architecture

## Decision

Financial Independence extends Foundry's existing Core and Finance layers. It
does not introduce a separate Mission Engine.

Core already owns Mission identity, scope, metric dispatch, evidence, and the
Flight Deck composition contract. Finance already owns deterministic financial
calculations. The missing seam is a domain-neutral assessment result capable of
carrying richer mission state than a scalar `MetricResult`.

## Dependency direction

```text
Mission Control -> Core MissionAssessmentRegistry
                         |
                         v
                 MissionAssessmentProvider
                         |
              registered at the composition root
                         |
                         v
             Finance FinancialIndependenceAssessor
                         |
              MetricRegistry + Finance projections
```

`foundry.core` never imports Finance. `foundry.mission_control` never imports
Finance. `foundry.web` remains the one sanctioned composition root where the
Finance metric and assessment providers are registered.

## Contract

Core owns immutable request and result shapes:

- `MissionAssessmentRequest`
- `MissionAssessment`
- `MissionPhaseAssessment`
- `MissionMargin`
- `DeltaV`
- `TrajectoryPoint`
- `ForecastPoint`
- `RecommendationAssessment`
- `MissionAssessmentProvider`
- `MissionAssessmentRegistry`

The result preserves calculation version, metric lineage, assumption
references, evidence references, limitations, and all rendered mission state.
Presentation code maps the result to HTML and geometry; it does not calculate
status, phase, margin, ETA, forecasts, or recommendations.

The assessment also carries the complete ordered phase presentation (stable
phase id, label, bounds, unit/currency, current/completed state, mission
completion marker, and estimated milestone date) and structured
recommendation presentation (action type and label, numeric amount,
unit/currency, cadence, adjustment key, scenario id, modelled impact, and
lineage). These are domain-neutral fields: Core knows their shape but no
Finance policy or scenario semantics.

## Financial Independence policy

The production policy is versioned as
`finance.financial_independence.v1`. Its phase thresholds are independent,
configurable policy values:

| Phase | Range |
|---|---:|
| Building Capital | below £450,000 |
| Escape Velocity | £450,000–£750,000 |
| Independent | £750,000–£1,500,000 |
| Abundance | above £1,500,000 |

Entering `Independent` completes the Mission.

The default Assumption Set separately records desired annual spending and a
sustainable withdrawal-rate assumption. £30,000 / 4% happens to explain the
default £750,000 completion threshold, but it does not define or mutate the
permanent band structure. Changing either assumption leaves the configured
bands unchanged.

Mission value is `finance.accessible_assets`, not net worth. V1 includes
owned liquid and near-liquid Accounts and Assets and excludes pensions,
property, vehicles, and other illiquid holdings. The inclusion policy is
structural and tested at the threshold boundaries.

## Forecast semantics

Finance produces deterministic low, base, and high monthly projections from:

- the current accessible-assets metric;
- the Mission's explicit Assumption Set;
- the selected Scenario, if any.

The range is a sensitivity envelope, not a calibrated probability. No
unsupported confidence percentage is calculated or rendered. The envelope
widens naturally because each path compounds under a different declared real
return.

ETA is the first projected date on which the base path enters `Independent`.
Status is:

- green when the low path reaches the threshold by the target date;
- amber when the base path reaches it but the low path does not;
- red when the base path misses it;
- unavailable when the assessment cannot be supported.

Mission Margin is progress pace relative to the pace required to meet the
target date, with the base ETA schedule buffer retained for audit. Delta-v is
the change in base ETA between the current assessment and the declared
lookback assessment. Because V1 projects on a monthly grid, user-facing
delta-v is expressed as approximately whole months accelerated or delayed
(including an honest “less than one month” state). The raw day conversion is
retained only in the assessment/drill-down for deterministic audit and does
not imply day-level model precision.

## Recommendations

A recommendation is a read-only `RecommendationAssessment` derived from a
declared Finance Scenario. The amount comes from the same structured
`monthly_contribution_delta` adjustment passed into the projection; descriptive
Scenario prose is never parsed for calculation or presentation inputs. The
assessor reruns the same projection and reports the resulting ETA delta at
month-level presentation precision. The Scenario and Assumption Set event ids
are retained as lineage. Mission Control never performs scenario arithmetic,
imports Finance policy, or appends an event.

## Backwards compatibility

`Mission.assessment_policy_id` and `Mission.assumption_set_id` are optional.
Existing Mission events replay with both fields set to `None` and continue
through the existing scalar status path unchanged.

Assumption Set and Scenario are additive `finance.*` entity types. Existing
logs require no migration or rewrite. A Financial Independence detail route
without the required declarations renders an explicit unavailable state.

Structured Scenario presentation fields are additive and replay with `None`
for historical Scenario events. A historical Scenario without complete
structured fields remains auditable but is not promoted as a Next Burn:
the assessment returns an explicit unavailable recommendation rather than
inferring an amount from its name. New `MissionAssessment`,
`MissionPhaseAssessment`, `DeltaV`, and `RecommendationAssessment` fields all
have backward-compatible defaults.

## Vertical-slice boundary

RFC-005 implements only Financial Independence:

- the reusable Core assessment seam;
- Finance's accessible-assets metric and projection implementation;
- one authenticated mission-detail route;
- a link from the existing live Financial Independence lane;
- calculation, replay, security, routing, accessibility, and responsive tests.

Financial Resilience, Pension Independence, Mortgage Freedom, the complete
mission index, authoring controls, and generalized recommendation catalogues
remain deferred.
