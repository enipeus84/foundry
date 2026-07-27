# RFC Index

Every RFC that has shipped, with links to its spec, architecture/decision
doc, implementation report(s), technical-debt register, merged PR, and
release tag — wherever each of those exists. All linked documents remain
at their original paths; this page only indexes them.

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
