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
FinanceAggregationService
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
| `FinanceAggregationService` | Finance, shared internal service | Provide the supported Party-scope, ownership-share and observed FX-conversion seam without exposing Finance rules to Core. | `FinanceMetricProvider`, `FinancePensionMetricProvider`, `PensionIndependenceAssessor` |
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

## Independent-review remediation

The SAFE review of PR #22 was remediated without changing Pension policy,
completion semantics, projections or API contracts:

- Flight Analysis group headings now use a shared semantic heading class with
  explicit Foundry typography, colour and spacing. The selector is
  domain-neutral and no Pension string or branch appears in Mission Control.
- Route regression coverage distinguishes exactly one Mission Data telemetry
  grid from the number of Flight Analysis grids implied by declared groups.
- `FinanceAggregationService` is the supported Finance-internal ownership and
  currency seam. Pension providers no longer instantiate
  `FinanceMetricProvider` or call its underscore-prefixed helpers.
- A zero W* is represented as the single already-achieved
  `Pension Independent` destination. There are no invented negative bands;
  completion remains exactly `P1 >= W*`, and the W* derivation remains
  visible.

The repository's authenticated static review renderer produced Pension
Independence and all three existing mission pages for desktop and responsive
review. The agent browser was prevented from opening the local-only server by
enterprise network policy, so interactive browser inspection is not claimed;
the local preview command and URLs are recorded in the PR remediation report.

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

### PR #22 SAFE-remediation validation

- Focused Pension evidence, metrics and assessment:
  `pytest tests/test_pension_assessment.py tests/test_pension_metrics.py
  tests/test_pension_evidence.py -q` — **33 passed**.
- Focused shared Mission Assessment and Mission Detail:
  `pytest tests/test_mission_control.py
  tests/test_core_mission_assessment.py
  tests/test_finance_mission_assessment.py -q` — **175 passed**, one existing
  Starlette deprecation warning.
- Security regressions:
  `pytest tests/test_webauth.py tests/test_web.py tests/test_eventlog.py
  tests/test_pension_evidence.py -q` — **34 passed**, the same warning.
- Documentation governance: **4 passed**; security documentation validation
  reports repository structure and documentation **COMPLETE**.
- Full suite: **594 passed**, the same warning.
- `validate.sh` completed security validation and the same **594 passed** full
  suite, then exercised deterministic replay with mock models. It returned 1
  by design because no external model API keys were available and therefore
  did not claim real-model V1 validation.
- `git diff --check`: clean. The project config declares no separate lint,
  static type-check or formatter command.

All six normalized route goldens changed because the shared stylesheet gained
the domain-neutral Flight Analysis group rules; Pension additionally gained
the semantic heading class. No displayed values or policy outputs changed in
the ordinary W*>0 fixture:

| Render | Previous hash | Remediated hash |
|---|---|---|
| Mission Control home | `1be46f20518c5bc502a286131eacab3978e091f7784fbb572cd02d2393bd4fd5` | `8c89b1fbba97598b2fa28cc24207d58cdd871be66d4132a62bed3afd6a90526c` |
| Financial Resilience | `c7dc0a728c9522e317e1bbf73b299a7db1e63dd831628463f5f8a281c4a8ac8e` | `7906d20f014876f8183ab8edf51bbcee029a0c909ecf372fd570464dd2bdf623` |
| Financial Resilience with pre-D13 tile | `bef8ece53695980d321230da1eb9f566c528b9e6aef98658cec6cb0cdbb74f80` | `96510b24c43f38d22a6e935ea65ae6007ed5713bb910c93c55f9ca73614acf15` |
| Financial Independence | `3ceb7a5cfaec019ddecd24195d48cb60eab8958a62dea4386f2c1ee8b8d7b04d` | `586b255faf03b3512cb87487c902371886577d4de298f75d53a733053bdfef12` |
| Mortgage Freedom | `315c684064a01f2ebaf57e9b2460e249e28283335664d41ec5a026063e384d74` | `b3fc0e6fef1a612bf06ccff025216502529c97feda1cd79597c31c8ad47ea20c` |
| Pension Independence | `be6b46805efffb7ffe6e654de30c0192b0b768674a9e162b3745f04c5c043826` | `84f3b148a00cb6f0e8f8e79df0c6fa8b556a9bfd4fefcc9ad472c5f1cd6a2fde` |

## Known technical debt

The complete register is
[`rfc-009-technical-debt.md`](rfc-009-technical-debt.md). Principal items are
authenticated pension ingestion, bounded envelope text, governed age-at-date
evidence, historical trajectory reconstruction, DB/State Pension revaluation,
decumulation and tax successor work, narrower cross-mission provenance and the
web projection rebuild cost.

## Architecture deviation

No Pension mission semantic or shared-renderer architecture deviation was
introduced. For the degenerate W*=0 case, A23's explicit honesty requirement
governs the literal five-band wording in A22: a zero-width hierarchy collapses
to the completing destination because intermediate wealth bands do not exist.
The generic household age representation remains recorded explicitly as debt
rather than hidden as a new identity contract.
