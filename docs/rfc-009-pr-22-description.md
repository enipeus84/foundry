# RFC-009 — Pension Independence Mission

## Objective and scope

This pull request contains the approved RFC-009 architecture and its
implementation as the fourth Finance Mission Assessment. It compares observed
DC pension wealth with required real retirement wealth W*, while keeping
Current Funding Position, Expected Mission Outcome and Mission Completion
separate.

It includes:

- the frozen RFC-009 architecture;
- the Pension evidence projection, seven Finance metrics and deterministic
  Pension Independence assessor;
- D12's additive Core telemetry `display_region` / `display_group` contract;
- shared Mission Detail hero, Flight Analysis and Mission Data integration;
- the approved D13 Financial Resilience trajectory-tile correction;
- synthetic proof data, regression tests, implementation reporting and the
  RFC-009 technical-debt register.

There is no new route, dashboard, Pension-specific renderer branch, stochastic
or probabilistic claim, decumulation, tax, product-selection, transfer,
consolidation or regulated-advice logic.

## Architecture

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

Finance owns the evidence, calculations and policy. Core receives only D12's
domain-neutral telemetry placement amendment. Mission Control receives only
domain-neutral placement plus D13's approved renderer correction. Completion
remains exactly observed `finance.pension_wealth >= W*`; forecast assumptions
cannot complete the mission.

## SAFE remediation

The independent SAFE review findings were addressed as follows:

- **F1:** Flight Analysis group headings use a semantic shared class with
  explicit Foundry typography, colour and spacing.
- **F2:** route regressions now require exactly one Mission Data telemetry grid
  and exactly one Flight Analysis grid per declared display group.
- **F3:** this description replaces the stale architecture-only text.
- **F4/F5:** `FinanceAggregationService` is now the supported Finance-internal
  ownership and observed-FX seam used by `FinanceMetricProvider` and both
  Pension providers; no Pension code calls sibling private helpers.
- **F6:** W*=0 emits one honest, already-achieved terminal milestone. It
  remains immediately complete, keeps the W* derivation visible, and renders
  no negative boundary or `£-0`.

The remediation adds no new Pension semantics, changes no Finance policy and
does not alter the ordinary W*>0 output values.

## Behaviour-preservation evidence

- Financial Independence and Mortgage Freedom values and calculations remain
  unchanged.
- Financial Resilience changes only through the already-approved D13
  trajectory judgement correction.
- All four missions use the same Mission Detail shell and escaped telemetry
  rendering contract.
- The only normalized golden changes from remediation are the shared inert CSS
  rules on all pages and the Pension Flight Analysis heading class; the exact
  before/after hashes are recorded in
  `docs/rfc-009-pension-independence-implementation-report.md`.
- Focused regressions cover Mission Data cardinality, group-to-grid
  cardinality, trusted-fragment escaping, supported Finance aggregation and
  the complete zero-W* route.

## Validation

Supported local environment: Python 3.12.13.

- Focused Pension evidence, metrics and assessment: **33 passed**.
- Focused shared Mission Assessment and Mission Detail: **175 passed**.
- Security regressions: **34 passed**.
- Documentation governance: **4 passed**.
- Security documentation validation: repository structure **COMPLETE**;
  documentation **COMPLETE**.
- Full suite: **594 passed**, with the existing Starlette TestClient
  deprecation warning.
- `git diff --check`: clean.
- `validate.sh`: security validation complete and **594 passed**; deterministic
  architecture exercise complete with mocks. Exit 1 is the script's deliberate
  no-real-model verdict because no external model API keys were present.
- No separate lint or static type-check command is declared by project config.

## Security considerations

- **Authentication and authorisation:** unchanged; Mission Detail remains
  behind the existing session and single-account household boundary.
- **Sensitive data and secrets:** no connector, credential, token, outbound
  request, new log sink or sensitive snapshot was added.
- **Auditability:** evidence and assumption provenance remain immutable and
  inspectable; assessment and rendering remain deterministic and read-only.
- **Untrusted text:** provider labels, display groups, values and supporting
  text remain escaped; only internally produced trusted HTML fragments bypass
  escaping.
- **Failure and abuse:** malformed Pension evidence is quarantined, future
  evidence is excluded, duplicate active missions fail closed, and zero W* no
  longer fabricates negative milestone data.

## Known technical debt

The governed register is `docs/rfc-009-technical-debt.md`. Remaining items
include authenticated Pension ingestion, bounded envelope text, governed
age-at-date evidence, historical trajectory reconstruction, DB/State Pension
revaluation, decumulation and tax successor work, narrower cross-mission
provenance, cache invalidation and web projection rebuild cost.

The private Pension helper coupling and negative-epsilon zero-W* encoding are
closed in this PR.

## Review state

This PR remains unmerged and is ready for independent Governor, Architecture
and Security review, subject to green GitHub Actions. The architecture remains
frozen; PR #21 is already merged.
