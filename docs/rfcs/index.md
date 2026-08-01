# RFC Index

Every RFC that has shipped, with links to its spec, architecture/decision
doc, implementation report(s), technical-debt register, merged PR, and
release tag — wherever each of those exists. All linked documents remain
at their original paths; this page only indexes them. RFCs whose
architecture is approved but not yet implemented are listed separately,
below the shipped table, so "Merged" never overstates what exists.

"No report published" means the RFC shipped but left no dedicated report
in `docs/` — the merged PR diff and the CHANGELOG entry are the record of
what happened. That is a documentation gap, not a claim that the work is
undocumented elsewhere.

## RFCs

| RFC | Title | Status | Spec | Architecture / decision doc | Implementation report(s) | Technical debt | PR | Tag / release |
|---|---|---|---|---|---|---|---|---|
| RFC-001 | Core Domain | Merged | [`000-core-domain-model.md`](../specifications/000-core-domain-model.md) (Revision 2, Adopted) | — | *No report published* — see PR and [CHANGELOG § v1.2-core](../../CHANGELOG.md) | — | [#3](https://github.com/enipeus84/foundry/pull/3) | `v1.2-core` |
| RFC-002 | Finance Domain (Part 1) | Merged, stops before Projections/Scenarios | [`001-finance-domain-model.md`](../specifications/001-finance-domain-model.md) (Draft v5, Amendment 4) | — | [`rfc-002-implementation-report.md`](../rfc-002-implementation-report.md) | — | [#4](https://github.com/enipeus84/foundry/pull/4) | `v1.3-finance-core` |
| RFC-003 | Mission Control v0.1 | Merged | — | — | *No report published* — see PR and [CHANGELOG § v1.4-mission-control](../../CHANGELOG.md) | — | [#5](https://github.com/enipeus84/foundry/pull/5) | `v1.4-mission-control` |
| RFC-003.3 | Deployable Synthetic Demo Mode | Merged | — | — | *No report published* — operational behaviour documented in [root README § Demo mode](../../README.md#demo-mode); see [CHANGELOG § v1.4.1-demo-mode](../../CHANGELOG.md) | — | [#6](https://github.com/enipeus84/foundry/pull/6) | `v1.4.1-demo-mode` |
| RFC-004 | Flight Deck UI (foundation) | Merged | — | — | [`rfc-004-1-implementation-report.md`](../rfc-004-1-implementation-report.md) (RFC-004.1, Visual Recovery); pre-merge review pack: [`rfc-004-visual-review.md`](../rfc-004-visual-review.md) (RFC-004A) | — | [#7](https://github.com/enipeus84/foundry/pull/7) | `v1.5-flight-deck` |
| RFC-004.2 | Flight Deck Visual Refinement | Merged | — | — | [`rfc-004-2-implementation-report.md`](../rfc-004-2-implementation-report.md); release-blocker/pre-merge pass: [`rfc-004-2-release-blocker-fixes.md`](../rfc-004-2-release-blocker-fixes.md) (RFC-004B, information-honesty) | — | [#8](https://github.com/enipeus84/foundry/pull/8) | see [CHANGELOG § v1.5.1-information-honesty](../../CHANGELOG.md) *(no separate tag cut)* |
| RFC-005 | Financial Independence Mission Assessment | Merged | — | [`rfc-005-financial-independence-architecture.md`](../rfc-005-financial-independence-architecture.md) | [`rfc-005-financial-independence-implementation-report.md`](../rfc-005-financial-independence-implementation-report.md) | [`rfc-005-technical-debt.md`](../rfc-005-technical-debt.md) | [#9](https://github.com/enipeus84/foundry/pull/9) | **Gap: no CHANGELOG entry or version bump exists for this RFC** — `pyproject.toml` still reads `1.5.1`, unchanged since RFC-004.2 |
| RFC-006 | Mission Assessment Framework | Merged | — | [`rfc-006-mission-assessment-framework.md`](../rfc-006-mission-assessment-framework.md) | [`rfc-006-mission-assessment-framework-implementation-report.md`](../rfc-006-mission-assessment-framework-implementation-report.md) | [`rfc-006-technical-debt.md`](../rfc-006-technical-debt.md) | [#16](https://github.com/enipeus84/foundry/pull/16) | No release |
| RFC-007 | Mortgage Freedom Mission; Property Equity Amendment (Revision 2) | Merged mission; amendment merged via [#19](https://github.com/enipeus84/foundry/pull/19) | — | [`rfc-007-mortgage-freedom-architecture.md`](../rfc-007-mortgage-freedom-architecture.md) | [`rfc-007-mortgage-freedom-implementation-report.md`](../rfc-007-mortgage-freedom-implementation-report.md) | [`rfc-007-technical-debt.md`](../rfc-007-technical-debt.md) | [#17](https://github.com/enipeus84/foundry/pull/17) | Amendment unreleased |
| RFC-008 | Financial Resilience Mission | Merged | — | [`rfc-008-financial-resilience-architecture.md`](../rfc-008-financial-resilience-architecture.md) | [`rfc-008-financial-resilience-implementation-report.md`](../rfc-008-financial-resilience-implementation-report.md) | [`rfc-008-technical-debt.md`](../rfc-008-technical-debt.md) | [#18](https://github.com/enipeus84/foundry/pull/18) | `1.6.0`; no tag |
| RFC-009 | Pension Independence Mission | Merged | — | [`rfc-009-pension-independence-architecture.md`](../rfc-009-pension-independence-architecture.md) | [`rfc-009-pension-independence-implementation-report.md`](../rfc-009-pension-independence-implementation-report.md) | [`rfc-009-technical-debt.md`](../rfc-009-technical-debt.md) | [#22](https://github.com/enipeus84/foundry/pull/22) | `1.7.0`; no tag |

RFC-009 shipped with the shared Mission Detail component extraction that
preceded it ([#21](https://github.com/enipeus84/foundry/pull/21),
[`rfc-009-shared-mission-detail-refactor-implementation-report.md`](../rfc-009-shared-mission-detail-refactor-implementation-report.md)).
Its first post-merge `main` run failed on a wall-clock-dependent test fixture
and was repaired by [#23](https://github.com/enipeus84/foundry/pull/23); the
production behaviour was never affected.

## Implemented, not yet merged

*None.* Every RFC with a governed implementation has shipped.

## Proposed architecture, not yet implemented

Architecture is written and under Governor review; no implementation exists.

| RFC | Title | Status | Architecture / decision doc | Self-review | PR |
|---|---|---|---|---|---|
| RFC-010 | Mission Console UX Framework | **Approved — architecture frozen 2026-07-31; not implemented** | [`RFC-010-mission-console-ux-framework.md`](RFC-010-mission-console-ux-framework.md) | [`RFC-010-architecture-self-review.md`](../reviews/RFC-010-architecture-self-review.md) | [#24](https://github.com/enipeus84/foundry/pull/24) |
| RFC-011 | Asset & Telemetry Acquisition Framework | **Approved — architecture frozen 2026-07-31 (Revision 2); not implemented** | [`RFC-011-asset-telemetry-acquisition-framework.md`](RFC-011-asset-telemetry-acquisition-framework.md) | [`RFC-011-architecture-self-review.md`](../reviews/RFC-011-architecture-self-review.md) | [#26](https://github.com/enipeus84/foundry/pull/26) |

## Engineering governance

RFC-100 is not a product RFC. It governs how Foundry is engineered, not what
Foundry does, and is listed separately for that reason.

| RFC | Title | Status | Document | Self-review | PR |
|---|---|---|---|---|---|
| RFC-100 | Flight Operations Manual | **Revision 2 — Governor amendments applied; awaiting final architecture review and freeze** | [`RFC-100-flight-operations-manual.md`](RFC-100-flight-operations-manual.md) | [`RFC-100-architecture-self-review.md`](../reviews/RFC-100-architecture-self-review.md) | pending |

RFC-007 Revision 2 documents `initial_deposit`, optional
`acquisition_costs`, optional explicit `valuation_basis`, visible
acquisition-fact conflicts and explanatory (not validating) equity
attribution. Net Worth remains isolated. Property Valuation Canon is successor
work and a governed correction workflow remains deferred technical debt.

## Pre-RFC infrastructure

Merged before RFC numbering began; included for completeness.

| PR | Title | Notes |
|---|---|---|
| [#1](https://github.com/enipeus84/foundry/pull/1) | Add minimal production web interface | Part of the V1.0 line — see [`../history/final-review.md`](../history/final-review.md) |
| [#2](https://github.com/enipeus84/foundry/pull/2) | Add Google authentication | Part of the V1.0 line |

## Process changes (non-RFC)

Engineering-process work that doesn't carry an RFC number.

| PR | Title | Result |
|---|---|---|
| [#10](https://github.com/enipeus84/foundry/pull/10) | Add architecture and security review gates | [`../engineering/review-gates.md`](../engineering/review-gates.md) (initial version) |
| [#11](https://github.com/enipeus84/foundry/pull/11) | Add engineering review gates | [`../engineering/review-gates.md`](../engineering/review-gates.md) (current version) |

## Known gaps in this index

- **RFC-001, RFC-003, RFC-003.3** have no dedicated implementation report
  or architecture doc — unlike RFC-002/004/005, which follow the
  spec → architecture → implementation-report → technical-debt pattern.
  If these are written retroactively, add them here rather than
  reconstructing behaviour from memory.
- **RFC-005** shipped without a CHANGELOG entry or version bump. The next
  change to `CHANGELOG.md` should add the missing `v1.6.0` (or similar)
  entry before this gap compounds further.
