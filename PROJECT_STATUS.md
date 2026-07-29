# Project Foundry Status

## Executive Summary

Foundry is a durable, model-independent memory substrate — an append-only,
hash-chained event log with a deterministic projection layer (the Canon)
— now carrying two shipped product domains, Core and Finance, and a
single-page product surface, the Flight Deck. Seven major RFCs have
landed since the V1.0 substrate milestone. Each is built on the same three
substrate files (`eventlog.py`, `canon.py`, `kernel.py`) without ever
modifying them. RFC-006 generalised the domain-neutral Mission Assessment
seam with definition discovery, direction-aware milestones, isolated
providers and generic mission routes. RFC-007 proves that
seam by adding Mortgage Freedom as the second assessment wholly within
Finance and is the authoritative Mortgage Freedom implementation. Financial
Resilience and Pension Independence remain honest planned
metadata. Authentication,
review-gate process,
and CI are in place but scoped to a single named user and two of six
planned gates. Documentation was substantially reorganized in the
immediately preceding change (docs index, RFC index, versioned Design
Constitution) and one process gap it surfaced — RFC-005 shipping without
a CHANGELOG entry or version bump — remains open as
[issue #13](https://github.com/enipeus84/foundry/issues/13). Overall: an
architecturally disciplined, single-user beta with a production-grade
substrate and a documentation practice that is now current but still
incomplete in places.

---

## Current Release

- **Current version:** `1.5.1` ([`pyproject.toml`](pyproject.toml)) — unchanged since RFC-004.2; RFC-005 shipped without a version bump (see [Documentation Status](#documentation-status))
- **Latest merged RFC:** RFC-007 — Mortgage Freedom Mission ([PR #17](https://github.com/enipeus84/foundry/pull/17), merged 2026-07-29)
- **Latest release/tag:** `v1.5-flight-deck` (git tag) — no tag exists for RFC-004.2 or RFC-005; see [`docs/rfcs/index.md`](docs/rfcs/index.md)

---

## Architecture Status

| Component | Status | Maturity | Notes |
|---|---|---|---|
| **Core** | Stable substrate concepts since RFC-001; Party/Employer/Mission, Decision lifecycle, Metric Provider, Flight Deck and Mission Assessment contracts | Production substrate / Beta assessment contract | RFC-006 extends Core's public mission-assessment contracts without changing the event substrate — see [`docs/architecture.md`](docs/architecture.md) |
| **Finance** | 8 registered metrics (net worth, liquidity runway, cash flow, asset allocation, employer concentration, debt ratio, cash available, accessible assets) | Beta | Full Financial Projection engine (§16), tax calculation, and AI-assisted analysis remain explicitly out of scope — see [`docs/rfc-002-implementation-report.md`](docs/rfc-002-implementation-report.md) |
| **Mission Assessment** | Definition discovery, direction-aware milestones, closed trajectory/margin/confidence vocabularies and isolated provider dispatch; Financial Independence and Mortgage Freedom have providers | Beta | Financial Resilience and Pension Independence are definitions only; Children is outside the fixed hierarchy — see [`docs/rfc-006-mission-assessment-framework.md`](docs/rfc-006-mission-assessment-framework.md) and [`docs/rfc-007-mortgage-freedom-architecture.md`](docs/rfc-007-mortgage-freedom-architecture.md) |
| **Flight Deck** | Full homepage + generic authenticated `/missions/{slug}` route | Production (surface) | No authored `/missions` index or event-inspector page yet — see [`docs/design/design-constitution.md`](docs/design/design-constitution.md), [`docs/rfc-004-visual-review.md`](docs/rfc-004-visual-review.md) |
| **Authentication** | Google sign-in via Supabase; stateless HMAC-signed cookies; fails closed | Beta | Single allowed email only — no multi-user, roles, or household sharing — see [`README.md` § Authentication](README.md#authentication) |
| **Event sourcing** | Append-only, hash-chained JSONL; sole source of truth | Production | Truncation blindness and single-writer assumption are documented, accepted limitations |
| **Projection engine** | Canon and every domain projection are pure, rebuildable folds | Production (pattern) / Prototype (retrieval) | Retrieval is word-overlap scoring, explicitly a placeholder; semantic/embedding index is roadmap-only |

---

## Engineering Status

- **RFC process:** 7 major RFCs plus sub-RFCs (003.3, 004.1, 004.2, 004A, 004B) shipped via branch-per-RFC + PR. Depth is inconsistent — RFC-001/003/003.3 have no dedicated implementation report (see [`docs/rfcs/index.md`](docs/rfcs/index.md)).
- **Documentation:** reorganized into a cross-referenced tree (see [Documentation Status](#documentation-status)).
- **Testing:** RFC-007 baseline was 393 collected / 393 passing and the
  implementation finishes at 453 collected / 453 passing in the declared
  `.[dev,web]` environment.
- **Architecture Gate:** implemented (`adversarial-architect`); active.
- **Security Gate:** implemented (`security-reviewer`); active.
- **CI/CD:** GitHub Actions ([`.github/workflows/test.yml`](.github/workflows/test.yml)) runs the full suite on every push to `main` and every PR, across Python 3.10–3.13. Deployment to Render (`render.yaml`) is manual, not automated CD.
- **Coding standards:** [`CONTRIBUTING.md`](CONTRIBUTING.md) — stdlib-only core, tests named for the architectural claim they defend, ~15-line adapter ceiling.

---

## Documentation Status

- **Architecture:** canonical and current — [`docs/architecture.md`](docs/architecture.md) is the sole source for the constitutional invariants.
- **RFC index:** [`docs/rfcs/index.md`](docs/rfcs/index.md) — maps every RFC to its spec, architecture doc, implementation report, technical debt, PR, and tag; self-documents its own gaps.
- **Design Constitution:** versioned at [`docs/design/design-constitution.md`](docs/design/design-constitution.md) (migrated from Drive; no longer a single point of failure outside git).
- **Engineering standards:** [`docs/engineering/review-gates.md`](docs/engineering/review-gates.md) + `CONTRIBUTING.md`.
- **Historical archive:** [`docs/history/`](docs/history/) — three pre-RFC documents, preserved verbatim and clearly banner-marked.

**Open gaps:**
1. RFC-001, RFC-003, and RFC-003.3 have no dedicated implementation report.
2. RFC-005 shipped with no CHANGELOG entry or version bump — [issue #13](https://github.com/enipeus84/foundry/issues/13), open.
3. No document describes CI/CD (`test.yml` isn't referenced from any doc).

---

## Active Engineering Review Gates

Per [`docs/engineering/review-gates.md`](docs/engineering/review-gates.md):

| Gate | Purpose | Status | Merge policy |
|---|---|---|---|
| **Architecture Gate** | Architectural boundaries, domain ownership, deterministic replay, technical debt, scaling, test coverage | Active | Blocks merge when Critical > 0 or High > 0 |
| **Security Gate** | Auth, authz, household isolation, session security, secrets, provenance, event integrity, dependency risk, abuse cases | Active | Blocks merge when Critical > 0 or High > 0 |
| Data Integrity Gate | — | Planned, not implemented | — |
| Performance Gate | — | Planned, not implemented | — |
| Product Design Gate | — | Planned, not implemented | — |
| Release Gate | — | Planned, not implemented | — |

---

## Open Architectural Debt

Highest-priority items from the RFC technical-debt registers and
`docs/architecture.md`'s known limitations (full register not repeated here):

- **Historical portfolio reconstruction** — undated entity revisions cannot be reconstructed into a true point-in-time view; affects the accuracy of any historical Finance trajectory.
- **Per-request replay/assessment cost** — every assessment rebuilds projections from the log with no caching or invalidation policy. Fine for one user; no defined performance envelope beyond that.
- **Single-writer, no concurrency** — a foundational scalability constraint on the event log, not RFC-005-specific.
- **Mission amendment lifecycle absent** — no supersession workflow exists for changing a Mission's declared policy or assumptions after the fact.
- **Mortgage evidence/product coverage** — the manual adapter is transitional;
  lender feeds, multiple mortgages, product fees/constraints and affordability
  require separately approved contracts.

---

## Next Recommended RFC

**RFC-008 — Financial Resilience Mission. Architecture approved; not
implemented.** The governed architecture is
[`docs/rfc-008-financial-resilience-architecture.md`](docs/rfc-008-financial-resilience-architecture.md),
and it is the canonical document for that implementation. No RFC-008 source
code, tests or framework changes exist in the repository.

Nothing else is authorised as an implicit next Burn. Pension Independence,
Children, connectors and optimisation still require a maintainer decision.

---

## Capability Maturity

Scored Emerging / Developing / Established / Mature.

| Dimension | Score | Why |
|---|---|---|
| **Architecture** | Established | Six merged RFCs and one draft implementation built on one unmodified substrate, with invariants enforced and tested. Not Mature: concurrency, truncation-anchoring, and semantic retrieval remain unbuilt. |
| **Engineering** | Established | Review-gate process and RFC branch/PR pattern followed consistently from RFC-002 onward. Not Mature: only 2 of 6 planned gates exist; RFC-001/003/003.3 skip the deeper report pattern. |
| **Documentation** | Developing | Just reorganized into an indexed, cross-referenced tree with a versioned Design Constitution. Not Established: 3 missing implementation reports and 1 open changelog/version gap remain live. |
| **Testing** | Established | 453 tests after RFC-007 (393-test authoritative baseline), CI-enforced across 4 Python versions, deterministic replay-parity discipline. Not Mature: real model adapters aren't tested in CI (a declared, deliberate choice) and no fuzzing exists. |
| **Governance** | Developing | Merge policy is defined and two gates are active. Not Established: Data Integrity, Performance, Product Design, and Release gates are all still unbuilt. |

---

## Project Timeline

The platform moved through four compressed phases in under two weeks:
a governed substrate first (V1.0 plus the constitutional invariants
that constrain every change since), then two product domains laid on
top of it without touching it, then a presentation layer that made
those domains visible, and now a reusable mission-intelligence seam
paired with the engineering and documentation process to govern what
comes next.

| Milestone | Date | Evidence |
|---|---|---|
| **Constitution** | Engineering invariants: 2026-07-15 (V1.0 release commit `dde3bc1`). Design Constitution: authored 2026-07-20; migrated into git 2026-07-27. | `docs/architecture.md` + `CONTRIBUTING.md` (engineering); `docs/design/design-constitution.md`, migrated via [PR #12](https://github.com/enipeus84/foundry/pull/12) |
| **RFC-001 — Core Domain** | 2026-07-17 | [PR #3](https://github.com/enipeus84/foundry/pull/3), tag `v1.2-core` |
| **RFC-002 — Finance Domain** | 2026-07-18 | [PR #4](https://github.com/enipeus84/foundry/pull/4), tag `v1.3-finance-core` |
| **RFC-003 — Mission Control** | 2026-07-19 | [PR #5](https://github.com/enipeus84/foundry/pull/5), tag `v1.4-mission-control`; extended same day by RFC-003.3 demo mode, [PR #6](https://github.com/enipeus84/foundry/pull/6), tag `v1.4.1-demo-mode` |
| **RFC-004 — Flight Deck** | 2026-07-20 to 2026-07-21 | [PR #7](https://github.com/enipeus84/foundry/pull/7), tag `v1.5-flight-deck`; refined by RFC-004.2, [PR #8](https://github.com/enipeus84/foundry/pull/8) |
| **RFC-005 — Mission Assessment** | 2026-07-27 | [PR #9](https://github.com/enipeus84/foundry/pull/9) — no corresponding tag or CHANGELOG entry (tracked as the open gap above) |
| **RFC-006 — Mission Assessment Framework** | 2026-07-29 | Merged via [PR #16](https://github.com/enipeus84/foundry/pull/16) |
| **RFC-007 — Mortgage Freedom Mission** | 2026-07-29 | Merged via [PR #17](https://github.com/enipeus84/foundry/pull/17) |
| **Engineering Review Gates** | 2026-07-27 | [PR #10](https://github.com/enipeus84/foundry/pull/10), [PR #11](https://github.com/enipeus84/foundry/pull/11) — `docs/engineering/review-gates.md` |
| **Documentation Architecture** | 2026-07-27 | [PR #12](https://github.com/enipeus84/foundry/pull/12) — docs index, RFC index, versioned Design Constitution |
| **PROJECT_STATUS.md** | 2026-07-27 | This document — the first executive-dashboard artifact, opened as its own PR |

---

## Last Updated

- **Date:** 2026-07-29
- **Branch:** `main`
- **Merged RFC head:** `3b2d414f3247c050d3d740b22e538ee014635603`
