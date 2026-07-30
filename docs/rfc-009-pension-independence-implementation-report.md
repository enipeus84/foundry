# RFC-009 — Pension Independence Mission Implementation Report

Status: implementation complete on
`rfc-009-pension-independence-mission`; PR #22 remains open and unmerged.

## Transition and baseline

- PR #21, the Shared Mission Detail prerequisite, merged to `main` as
  `af5cbdcf7257cb5c0593ad1f5b6b3a2e8f12eaea` on
  2026-07-30 at 18:03:39 UTC.
- Updated `main` was merged into this branch as
  `aac2e85daeac881ad14db204f767bfc2fc051107`; published history was not
  rewritten.
- Pre-flight used Python 3.12.13 in an isolated `.[dev,web]` environment.
- Fresh baseline: Mission Control 84 passed; Core/Finance assessment 153
  passed; documentation governance 4 passed; security documentation
  validation COMPLETE; full suite 553 passed.
- PR #21 was merged before implementation began. PR #22 was not merged.

## Objective and scope

Implemented Pension Independence as the fourth Finance Mission Assessment,
strictly following the frozen RFC-009 architecture. The mission compares
observed DC pension wealth P1 with required real retirement wealth W*, while
keeping Current Funding Position, Expected Mission Outcome and Mission
Completion distinct.

The change adds no pension-specific route or layout. It uses the authenticated
generic Mission Detail route and the shared components merged by PR #21.
There is no decumulation, bridging-income, tax, annual-allowance, stochastic,
provider-selection, transfer, consolidation or regulated-advice logic.

## Architecture result

```text
Mission Definition
        ↓
PensionIndependenceAssessor
        ↓
FinancePensionMetricProvider + PensionEvidenceProjection
        ↓
MissionAssessment
        ↓
Shared Mission Detail renderer
```

- Finance owns the evidence envelope, seven metrics and all Pension policy.
- Core gains only D12's domain-neutral telemetry display-region contract.
- Mission Control gains only D12 region placement and D13's independent
  trajectory-judgement tile correction.
- No assessor references another assessor or the assessment registry.
- Completion is exactly observed `finance.pension_wealth >= W*`; no forecast
  assumption participates.
- Assessments and renders are read-only and deterministic.

## Implemented components

| Component | Ownership | Purpose | Current consumers |
|---|---|---|---|
| `PensionEvidenceProjection` / `record_pension_evidence` | Finance, mission-specific | Validate and replay attributed contribution, fee, DB and State Pension declarations; quarantine malformed envelopes. | Pension metrics and assessor |
| `FinancePensionMetricProvider` | Finance, mission-specific | Publish P1–P7 with `pension-metrics-v1`, provenance, staleness, disjointness and tax-year rules. | Pension Independence through `MetricRegistry` |
| `PensionIndependenceInputs` | Finance, mission-specific | Validate the complete declared policy surface without defaults. | Pension assessor |
| `PensionIndependenceAssessor` | Finance, mission-specific | Compose W*, forecast, milestones, trajectory, ETA, Delta-v, margin, confidence, telemetry and recommendation. | `finance.pension_independence.v1` |
| `TelemetryItem.display_region` / `display_group` | Core, shared | Declare hero, analysis or drill-down placement with validation and a four-item hero cap. | All Mission Assessment providers |
| Mission hero telemetry renderer | Mission Control, shared | Duplicate declared hero telemetry into the hero while retaining every item in Mission Data. | All live Finance missions |
| Flight Analysis telemetry renderer | Mission Control, shared | Group and render declared analysis telemetry with escaped headings. | All live Finance missions |
| Trajectory judgement tile | Mission Control, shared | Render `trajectory_state` independently from observed-history availability. | All live Finance missions |

No pension-specific UI component, conditional route, mission-name branch or
new API contract was introduced.

## Evidence and metric behaviour

The closed evidence whitelist covers annual employee/employer/salary-sacrifice
rates, dated employee/employer payments, annual scheme fees, DB accrued income
and normal age, and State Pension amount, age and basis. Validation occurs
before append. Rate, fee, DB and State Pension fields supersede by effective
date and append order; payment fields accumulate.

The provider publishes:

1. `finance.pension_wealth`
2. `finance.pension_contributions_annual`
3. `finance.state_pension_income_annual`
4. `finance.defined_benefit_income_annual`
5. `finance.retirement_income_required`
6. `finance.retirement_wealth_required`
7. `finance.pension_contributions_tax_year`

P1 remains disjoint from accessible assets. P2 annual rates and P7 dated
payments never combine. A DB/DC conflict excludes the affected account from
both P1 and P4. Mixed household tax-year boundaries make P7 unsupported rather
than selecting one silently.

## Mission behaviour and demonstration

The synthetic Morgan household supplies attributable proof evidence:

- observed pension wealth: £62,000;
- required retirement income: £40,000/year;
- State Pension: £10,600/year;
- W*: £735,000;
- Expected pension at the planning point: approximately £785,000;
- Expected retirement income: approximately £42,000/year;
- current tax-year dated payments: £11,500.

The resulting mission is incomplete, in the Dependent band and on a Nominal
Expected path. This intentionally proves that forecast success cannot complete
an observed mission. Conservative/Expected/Optimistic paths are deterministic
sensitivities and are never presented as probabilities.

## Behaviour-preservation evidence

- Financial Independence and Financial Resilience route goldens remain
  unchanged after Pension registration.
- D13 changes only Financial Resilience's previously incorrect trajectory
  tile; its old and corrected strings are separately pinned.
- Mortgage Freedom values and calculations remain unchanged. Its golden
  reflects four additional household tax-residency provenance references
  created for P7; the displayed provenance cardinality is the only
  cross-mission body difference.
- The homepage change is limited to Pension Independence moving through the
  existing definition-association path from planned to live.
- All four live missions use the same hero, Flight Analysis, Mission Data and
  summary structure. Pension declares four hero items; all telemetry remains
  available in Mission Data.

## Security considerations

- Authentication, session validation, route protection and the single-account
  authorisation boundary are unchanged.
- No connector, credential, token, external request, write route or sensitive
  logging was added.
- Hostile structured display text is escaped; malformed direct-log pension
  envelopes are quarantined; raw entity ids and assumption keys do not render.
- Future evidence is excluded with a visible limitation. Stale and
  contradictory evidence cannot silently improve confidence.
- Pension values, contributions, dates, ages and projections remain in the
  Event Log or ephemeral read models and are classified as
  personal-confidential or derived-sensitive.

## Four-assessor performance envelope

Measured locally on Python 3.12.13 against the fixed synthetic household at
`as_of=1_750_000_000`, a 596-event log, four registered assessors, 30 warmed
assessment samples and 20 warmed HTTP samples per route:

| Operation | Median | p95 |
|---|---:|---:|
| Build projections and assess all four missions | 50.494 ms | 51.957 ms |
| Homepage render | 68.878 ms | 74.571 ms |
| Financial Resilience detail | 37.945 ms | 44.654 ms |
| Financial Independence detail | 32.639 ms | 38.672 ms |
| Pension Independence detail | 35.037 ms | 35.798 ms |
| Mortgage Freedom detail | 20.807 ms | 21.148 ms |

This is a measurement, not a service-level objective. No pre-emptive
optimisation was added.

## Validation

- Focused Pension evidence, metric and assessment suite: **32 passed**.
- Focused Core Mission Assessment and Mission Control suite: **132 passed**.
- Full suite: **592 passed**.
- Documentation governance: **4 passed**.
- Security documentation validation: repository structure **COMPLETE**;
  documentation **COMPLETE**.
- `git diff --check`: clean.
- Existing Starlette TestClient deprecation warning is unchanged.

## Known technical debt

The complete register is
[`rfc-009-technical-debt.md`](rfc-009-technical-debt.md). Principal items are
authenticated pension ingestion, bounded envelope text, governed age-at-date
evidence, historical trajectory reconstruction, DB/State Pension revaluation,
decumulation and tax successor work, narrower cross-mission provenance and the
Core zero-destination milestone representation.

## Architecture deviation

No domain or renderer architecture deviation was introduced. The zero-W*
milestone compatibility encoding and generic household age representation are
recorded explicitly as debt rather than hidden as new semantics.
