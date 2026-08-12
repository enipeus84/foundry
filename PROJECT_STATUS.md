# Project Foundry Status

## Executive Summary

Foundry is a durable, model-independent memory substrate — an append-only,
hash-chained event log with a deterministic projection layer (the Canon)
— now carrying two shipped product domains, Core and Finance, and a
single-page product surface, the Flight Deck. Eleven major RFCs have
landed since the V1.0 substrate milestone. Each is built on the same three
substrate files (`eventlog.py`, `canon.py`, `kernel.py`) without ever
modifying them. RFC-006 generalised the domain-neutral Mission Assessment
seam with definition discovery, direction-aware milestones, isolated
providers and generic mission routes. RFC-007 proved that seam by adding
Mortgage Freedom as the second assessment wholly within Finance, and
RFC-008 and RFC-009 completed the set: **all four Finance missions —
Financial Resilience, Financial Independence, Pension Independence and
Mortgage Freedom — now have live assessment providers.** RFC-010 delivered
the Mission Console that presents them, migrating all four missions to one
shared model and renderer, and RFC-011 added the Telemetry Acquisition
platform layer with a merged Phase 1–4 reference implementation.
**RFC-100 (Flight Operations Manual, Revision 2 with Amendment 1) governs how
every subsequent RFC is engineered.** RFC-012 product remediation, RFC-013
Capture Contracts, RFC-015 Capture Target Registry, RFC-016 Phases 1–2 and
RFC-017 Value Provenance have since shipped. RFC-016 Phase 3 Mission Target
Management is now a bounded implementation candidate from frozen authority
`b7957d6`: an authorised operator can declare, replace and withdraw a Mission
Target under `/missions`. TELMU and SAFE have completed independent review with
non-blocking observations; merge remains a separate Governor act.
Authentication, review-gate process and CI remain scoped to a single named
user and two of six planned gates. Overall: an architecturally disciplined,
single-user beta with a production-grade substrate and an unmerged strategic-
intent management candidate.

---

## Current Release

- **Current version:** `1.8.0` ([`pyproject.toml`](pyproject.toml)) — bumped by the Release Closeout burn, which also added the missing CHANGELOG entries for RFC-010, RFC-011, RFC-100 and RFC-012. RFC-005's absent release note is acknowledged retroactively rather than reconstructed ([issue #13](https://github.com/enipeus84/foundry/issues/13)). No git tag was cut; tagging has been dormant since `v1.5-flight-deck` and resuming it is a separate Governor decision
- **Latest merged RFC:** RFC-017 — Value Provenance Framework, completed through Pension Phase 2 on 2026-08-11. RFC-016 Phase 3 is an implementation candidate only and is not merged
- **Governance:** RFC-100 — Flight Operations Manual, Revision 2 merged ([PR #28](https://github.com/enipeus84/foundry/pull/28)) with Amendment 1, Mission Declaration ([PR #29](https://github.com/enipeus84/foundry/pull/29)), both 2026-08-02 ([`docs/rfcs/RFC-100-flight-operations-manual.md`](docs/rfcs/RFC-100-flight-operations-manual.md))
- **Next gate:** governed PR and Governor Merge Review for the RFC-016 Phase 3 candidate; TELMU and SAFE are complete with non-blocking observations, and merge remains a separate Governor act
- **Latest release/tag:** `v1.5-flight-deck` (git tag) — no tag exists for RFC-004.2 or later; see [`docs/rfcs/index.md`](docs/rfcs/index.md)

---

## Architecture Status

| Component | Status | Maturity | Notes |
|---|---|---|---|
| **Core** | Stable substrate concepts since RFC-001; Party/Employer/Mission, Decision lifecycle, Metric Provider, Flight Deck and Mission Assessment contracts | Production substrate / Beta assessment contract | RFC-006 extends Core's public mission-assessment contracts without changing the event substrate — see [`docs/architecture.md`](docs/architecture.md) |
| **Finance** | 8 registered metrics (net worth, liquidity runway, cash flow, asset allocation, employer concentration, debt ratio, cash available, accessible assets) | Beta | Full Financial Projection engine (§16), tax calculation, and AI-assisted analysis remain explicitly out of scope — see [`docs/rfc-002-implementation-report.md`](docs/rfc-002-implementation-report.md) |
| **Mission Assessment** | Definition discovery, direction-aware milestones, closed trajectory/margin/confidence vocabularies, per-instrument applicability, telemetry display regions and isolated provider dispatch; **all four Finance missions have live providers** | Beta | Financial Resilience (RFC-008), Financial Independence (RFC-005), Pension Independence (RFC-009) and Mortgage Freedom (RFC-007) are all live; Children remains outside the fixed hierarchy. Console information architecture was delivered by RFC-010 — see [`docs/rfc-006-mission-assessment-framework.md`](docs/rfc-006-mission-assessment-framework.md) |
| **Flight Deck** | Full homepage + generic authenticated `/missions/{slug}` route | Production (surface) | The RFC-016 Phase 3 candidate adds a separate `/missions` management index without changing Flight Deck assessment behavior |
| **Mission Targets** | Phases 1–2 shipped; Phase 3 operator lifecycle candidate | Candidate | Declare, immutable supersession and withdrawal are reachable under `/missions`; assessment consumption remains unauthorised and `DEBT-016-P3-01` remains unresolved |
| **Authentication** | Google sign-in via Supabase; stateless HMAC-signed cookies; fails closed | Beta | Single allowed email only — no multi-user, roles, or household sharing — see [`README.md` § Authentication](README.md#authentication) |
| **Event sourcing** | Append-only, hash-chained JSONL; sole source of truth | Production | Truncation blindness and single-writer assumption are documented, accepted limitations |
| **Projection engine** | Canon and every domain projection are pure, rebuildable folds | Production (pattern) / Prototype (retrieval) | Retrieval is word-overlap scoring, explicitly a placeholder; semantic/embedding index is roadmap-only |

---

## Engineering Status

- **RFC process:** 11 major RFCs plus sub-RFCs (003.3, 004.1, 004.2, 004A, 004B) shipped via branch-per-RFC + PR; engineering governance itself is now an RFC ([RFC-100](docs/rfcs/RFC-100-flight-operations-manual.md), frozen, documentation burn in flight). Depth is inconsistent — RFC-001/003/003.3 have no dedicated implementation report (see [`docs/rfcs/index.md`](docs/rfcs/index.md)).
- **Documentation:** reorganized into a cross-referenced tree (see [Documentation Status](#documentation-status)).
- **Testing:** The RFC-016 Phase 3 frozen baseline is 802 passing with one
  pre-existing FastAPI/TestClient deprecation warning. Deterministic fixture
  clocks remain mandatory; the candidate adds named lifecycle, staleness,
  authority, malformed-input, hostile-log and zero-write rendering cases.
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
2. RFC-005, RFC-010 and RFC-011 each shipped with no CHANGELOG entry or version bump — RFC-005 is tracked as [issue #13](https://github.com/enipeus84/foundry/issues/13), open; Release Closeout for all three is outstanding.
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

## Next Recommended Gate

**Governed PR and Governor Merge Review for RFC-016 Phase 3.** The exact
implementation candidate has completed TELMU and SAFE review with non-blocking
observations. The remaining work is publication of the governed PR and Governor
merge review. No Phase 4 assessment adoption, Mission instantiation or merge is
authorised by the candidate alone.

---

## Capability Maturity

Scored Emerging / Developing / Established / Mature.

| Dimension | Score | Why |
|---|---|---|
| **Architecture** | Established | Eleven merged RFCs built on one unmodified substrate, with invariants enforced and tested. Not Mature: concurrency, truncation-anchoring, and semantic retrieval remain unbuilt. |
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
| **RFC-007 — Mortgage Freedom Mission** | 2026-07-29 | Merged via [PR #17](https://github.com/enipeus84/foundry/pull/17); property-equity amendment via [PR #19](https://github.com/enipeus84/foundry/pull/19) |
| **RFC-008 — Financial Resilience Mission** | 2026-07-29 | Merged via [PR #18](https://github.com/enipeus84/foundry/pull/18) — adds per-instrument applicability |
| **RFC-009 — Pension Independence Mission** | 2026-07-31 | Merged via [PR #22](https://github.com/enipeus84/foundry/pull/22); shared Mission Detail extraction via [PR #21](https://github.com/enipeus84/foundry/pull/21); post-merge fixture hotfix [PR #23](https://github.com/enipeus84/foundry/pull/23) |
| **RFC-010 — Mission Console UX Framework** | 2026-07-31 | Architecture approved and frozen — [PR #24](https://github.com/enipeus84/foundry/pull/24); implemented in two phases and merged via [PR #25](https://github.com/enipeus84/foundry/pull/25) |
| **RFC-011 — Asset & Telemetry Acquisition Framework** | 2026-07-31 to 2026-08-01 | Architecture Revision 2 approved and frozen — [PR #26](https://github.com/enipeus84/foundry/pull/26); combined Phase 1–4 reference implementation merged via [PR #27](https://github.com/enipeus84/foundry/pull/27) |
| **RFC-100 — Flight Operations Manual** | 2026-08-01 to 2026-08-02 | Revision 2 Governor-approved and frozen; documentation implementation open as draft [PR #28](https://github.com/enipeus84/foundry/pull/28) |
| **Engineering Review Gates** | 2026-07-27 | [PR #10](https://github.com/enipeus84/foundry/pull/10), [PR #11](https://github.com/enipeus84/foundry/pull/11) — `docs/engineering/review-gates.md` |
| **Documentation Architecture** | 2026-07-27 | [PR #12](https://github.com/enipeus84/foundry/pull/12) — docs index, RFC index, versioned Design Constitution |
| **PROJECT_STATUS.md** | 2026-07-27 | This document — the first executive-dashboard artifact, opened as its own PR |

---

## Last Updated

- **Date:** 2026-08-11
- **Branch:** `rfc-016-phase-3-mission-target-management`
- **Frozen authority:** `b7957d63524e49bedcf60273ff5634ebaf8861e3`
- **Updated by:** governance-completion publication. Implementation candidate,
  TELMU and SAFE are complete; Phase 3 remains unmerged and awaits governed PR
  and Governor merge authority.
