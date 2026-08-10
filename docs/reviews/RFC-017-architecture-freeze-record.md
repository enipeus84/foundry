# RFC-017 — Value Provenance Framework: Architecture Freeze Record

**Decision: GO — architecture FROZEN.**
**Freeze date:** 2026-08-06
**Frozen head:** `b8cc0ed9c63b10d2fbc03ec9440c154826c7efd6`
**Branch:** `claude/rfc-017-value-provenance-5ixkye`
**Authority:** Governor freeze gate, [PR #45](https://github.com/enipeus84/foundry/pull/45)

**Attribution.** This document records a **Governor act**. It is transcribed by
EECOM at the Governor's direction and is held separately from the architecture
author's artefacts — the RFC, the self-review and the architecture report — so
that the decision is never mistaken for self-certification (RFC-100 §1.2,
§9.4). Nothing in it is EECOM's judgement.

The architecture is accepted **exactly as proposed and amended**. No alternative
model, contract or implementation design was introduced at this gate.

---

## Merge-head verification *(RFC-100 §9.3, Amendment 1)*

| Check | Result |
|---|---|
| Governor-approved head | `b8cc0ed9c63b10d2fbc03ec9440c154826c7efd6` |
| PR head at freeze | same commit, pushed |
| Architecture-only diff | **PASS** — six documents; no production source, test, fixture, template, CSS or runtime configuration (FR-013, §3.1 rule 3) |

## Required checks

| Check | Result |
|---|---|
| RFC numbering and the reservation amendment | **PASS** — GD-1 is recorded. RFC-017 is *Value Provenance Framework*; *Asset Detail & Provenance Investigation* is an unnumbered future consumer boundary. Both moves of that boundary are recorded beside retained originals in RFC-015 §0/§18, RFC-016 §0/§14.1 and `index.md` (RFC-100 §9.2) |
| Programme numbering | **PASS** — GD-10 resolves the collision **without reserving any successor RFC number**. RFC-014 remains the only reservation |
| Canonical event contract | **PASS** — **zero** canonical events, in every phase; no writer, no payload change, no vocabulary amendment to any existing event |
| Core contract | **PASS** — five shapes, four closed vocabularies, eleven values, one explainer seam, fifteen invariants, eight Phase 1 acceptance criteria |
| Honesty rule | **PASS** — completeness and residual are derived by the framework and cannot be declared by a domain |
| Frozen-contract boundary | **PASS** — no change to `MetricResult`, RFC-006, `MissionTarget` or any existing domain calculation |
| Determinism | **PASS** — bitemporal reproduction, deterministic ordering, and refusal rather than re-derivation when a calculation version cannot be reproduced |
| Open implementation-critical decisions | **PASS** — none remain. GD-8 and GD-9 are deferred and confer no implementation authority |
| Documentation coherence (FR-017) | **PASS** — the declared index gap is closed |

## Final Governor decision register

| Decision | Disposition |
|---|---|
| GD-1 | **Settled** — RFC-017 is *Value Provenance Framework*; the investigation boundary is re-earmarked, unnumbered |
| GD-2 | **Settled** — deterministic projection; zero canonical events, in every phase |
| GD-3 | **Settled** — the four provenance vocabularies are closed and not extensible by a domain |
| GD-4 | **Settled** — completeness and residual are framework-derived, never declared |
| GD-5 | **Settled** — Core verifies by arithmetic within one unit and never transforms one |
| GD-6 | **Settled** — bounded, lazy recursion with cycle refusal |
| GD-7 | **Settled** — a partial explanation ships before any consumer surface |
| GD-8 | **Deferred, explicitly.** Whether an assessor must consult provenance. **Confers no implementation authority**; authorises no assessor change and no RFC-006 amendment |
| GD-9 | **Deferred, explicitly.** Whether `MetricResult`'s reference bag is superseded. **Confers no implementation authority**; Phase 5 is not authorised |
| GD-10 | **Settled** — programme numbering resolved **without reserving successor numbers** |

## Phase authority

**RFC-017 Phase 1 — GO.** Implement the **Core Value Provenance Framework**
against acceptance criteria **P1-A through P1-H** (RFC §11.1), proven against a
**mock domain only**.

**RFC-017 Phase 2 — NOT AUTHORISED.** The first domain explainer (property
equity) remains architecturally described and requires subsequent Governor
implementation authority.

**RFC-017 Phase 3 — NOT AUTHORISED.** The partial explainer (pension wealth)
remains architecturally described and requires subsequent Governor
implementation authority.

**RFC-017 Phase 4 and later — NOT AUTHORISED.** Each retains the governance
gates stated in RFC §11, including the GD-7 sequencing rule that a **partial**
explanation must exist before any consumer surface.

## Frozen invariants Phase 1 must preserve

Binding on the Phase 1 Implementation Burn. A change to any of these is a
change to frozen architecture (FR-003) and is a Governor decision, not an
implementation choice.

| # | Invariant |
|---|---|
| 1 | **Zero canonical events and no write path.** No module in the framework may append an event, directly or transitively |
| 2 | **Deterministic projection.** Same log, `as_of`, `known_at` and calculation version ⇒ byte-identical provenance, including ordering |
| 3 | **Framework-derived completeness and residual.** No domain may declare either |
| 4 | **Closed provenance vocabularies.** `PROVENANCE_NODE_KIND`, `CONTRIBUTION_ROLE`, `EXPLANATION_COMPLETENESS` and `EXCLUSION_REASON` are closed and not extensible by a domain |
| 5 | **Core arithmetic verification without transformation.** Core may sum and compare within a single unit; Core may never value, price, convert, weight or otherwise transform a quantity |
| 6 | **Bounded, lazy recursion with cycle refusal.** A cycle makes the node unavailable and surfaces a conflict; it is never resolved by truncation |
| 7 | **`Subject`, `as_of` and `known_at` pass unchanged through recursive expansion.** The resolver never substitutes a broader scope or a different time |
| 8 | **No modification to `MetricResult`, RFC-006, `MissionTarget`, or any existing domain calculation** |
| 9 | **No UI and no consumer adoption.** Phase 1 changes nothing a household can see |

## Rulings on the two items raised at the gate

| Item | Ruling |
|---|---|
| Freeze scope | **Phase 1 only**, as recorded above |
| The §6.4 prose-versus-table refinement | **Not a freeze blocker, and not to be done.** The contract is already normative in the RFC. **Documentation churn solely to restate a contract already made normative is not authorised** |

## What this freeze does not authorise

- Any Phase beyond Phase 1.
- Any consumer, surface, route, form or rendering of a provenance.
- Any assessor change, RFC-006 amendment or `MetricResult` change — GD-8 and
  GD-9 are deferred and confer nothing.
- Any retrofit of a shipped metric, or any change to a value a household
  currently sees.
- Any new canonical event kind, in this or any later phase.
