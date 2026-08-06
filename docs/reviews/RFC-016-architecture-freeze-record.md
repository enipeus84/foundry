# RFC-016 — Mission Target Framework: Architecture Freeze Record

**Decision: GO — architecture FROZEN.**
**Freeze date:** 2026-08-06
**Branch:** `rfc-016-mission-target-framework`
**Authority:** Governor freeze gate, PR #43

The architecture is accepted exactly as proposed by EECOM. No alternative event
model or implementation design was introduced at this gate.

## Required checks

| Check | Result |
|---|---|
| RFC numbering, index and RFC-015 G3 amendment | **PASS** — GD-1 is recorded; RFC-016 is Mission Target Framework and RFC-017 remains reserved for Asset Detail & Provenance Investigation. |
| Mission-instantiation boundary | **PASS** — GD-11 excludes it from this RFC. |
| Canonical event contract | **PASS** — exactly `core.mission_target.declared` and `core.mission_target.closed`; `core.mission_target.updated` is prohibited. |
| Core contract | **PASS** — typed quantities, closed vocabularies, append-only replay, conflict refusal and as-of resolution are specified. |
| RFC-006 boundary | **PASS** — no assessment contract changes; a sibling target projection is the only assessor seam. |
| Household isolation | **PASS** — target household is authoritative; first-target-binds applies. W7 remains a recorded pre-existing watch item. |
| Open implementation-critical decisions | **PASS** — none remain. GD-8 is deferred only to the governed RFC-005 adoption amendment and authorises no present assessor change. |

## Final Governor decision register

| Decision | Disposition |
|---|---|
| GD-1 | **Accepted** — RFC-016 confirmed; RFC-017 reassignment recorded. |
| GD-2 | **Accepted** — two canonical events; no `updated` event. |
| GD-3 | **Accepted** — supersession and withdrawal precede real declaration. |
| GD-4 | **Accepted** — `TARGET_DIMENSION` and `TARGET_HORIZON_KIND` are closed. |
| GD-5 | **Accepted** — RFC-006 contracts remain unchanged. |
| GD-6 | **Accepted** — v1 targets do not move policy bands. |
| GD-7 | **Accepted** — Mortgage change requires a governed RFC-007 amendment. |
| GD-8 | **Deferred** — resolved only in the future RFC-005 adoption amendment; no current integration authority follows. |
| GD-9 | **Accepted** — Financial Independence reference adoption, then Governor gate. |
| GD-10 | **Accepted** — target household authority and first-target-binds. |
| GD-11 | **Accepted** — Mission instantiation is outside RFC-016. |

## Phase authority

**RFC-016 Phase 1 — GO.** Implement the Core Mission Target contract, including
both lifecycle mechanisms, against a mock domain only.

**RFC-016 Phase 2 — GO.** Implement the Finance metric-descriptor seam and
admissibility only. It introduces no assessor changes.

Phases 3–5 are not authorised by this freeze. In particular, Mission Assessment
adoption remains Phase 4 and requires the per-mission amendments and Governor
gates specified by RFC-016.

---

## Governor clarification C-016-01 — 2026-08-06

**Decision: `basis` is optional and limited to 500 Unicode characters.**

The frozen RFC requires `basis` to be length-bounded but did not state its
numeric maximum. Review of the RFC, architecture report, decision register and
this freeze record found no pre-existing value. This clarification completes
that omitted precision without changing the authorised event set, target
lifecycle, projection semantics, or any closed Governor decision.

**RFC-016 Phase 2A — GO.** BOOSTER may implement this bound while remediating
SAFE-016-01 through SAFE-016-05. No other implementation authority changes.
