# RFC-017 — Value Provenance Framework: Architecture Report

Report shape per RFC-100 §11.1. Verdict vocabulary: `GO` · `CONCERN` · `NO-GO`.

Covers one burn: the **RFC-017 Architecture Burn**, producing the architecture
specification, its adversarial self-review and this report.

## Mission Declaration *(as run)*

| Field | Declared | As run |
|---|---|---|
| **Spacecraft** | EECOM | EECOM |
| **Fuel** | Claude | Claude (`claude-opus-5`) |
| **Effort Level** | not stated in the brief | executed as **HIGH** |
| **Mission Type** | Architecture Burn — "architecture-only burn" | Architecture Burn |
| **Authority** | Governor, via engineering brief | unchanged |

**Effort level disclosure (RFC-100 §6.0).** The brief declared no effort level.
RFC-100 §3.2 and §12.3 prescribe **HIGH** for an Architecture Burn and for any
burn touching a Core seam; this burn proposes four new Core vocabularies and a
Core-owned resolver, so HIGH was executed. The omission is disclosed rather
than resolved silently.

**Classification (FR-015).** Declared and performed as an **Architecture
Burn**. The brief's constraints — "Do not implement code · Do not modify
schemas · Do not introduce events · Do not build UI" — match RFC-100 §3.1
rule 3 exactly. No burn reclassified itself.

---

## Pre-flight

| # | Check | Result | Evidence |
|---|---|---|---|
| 0 | Mission Declaration | **PASS with note** | Four of five fields present; effort level absent from the brief and disclosed above |
| 1 | Repository | **PASS** | working copy of `enipeus84/foundry` (FR-001) |
| 2 | Branch | **PASS** | `claude/rfc-017-value-provenance-5ixkye`, the designated branch (FR-002) |
| 3 | Ownership | **PASS** | working tree clean before work began |
| 4 | CI | **NOT VERIFIED** | no CI access from this session; documentation-only burn changing no source, so no CI-observable surface is touched |
| 5 | Authentication | **N/A** | no credentialed operation performed |
| 6 | Python environment | **N/A** | documentation-only burn; no test execution required by the change |
| 7 | Caffeinate | **N/A** | no long-running job |
| 8 | Worktrees | **PASS** | no stale worktree |
| 9 | **RFC ownership** | **CONCERN — raised, not resolved** | **RFC-017 is reserved by Governor ruling GD-1 (2026-08-06)** for *Asset Detail & Provenance Investigation* |

**Pre-flight verdict: CONCERN, proceeded.**

Check 9 is the same condition RFC-016's Phase 1 burn met and recorded, and it
was handled the same way. The burn proceeded because stopping would have
delivered nothing while the collision is itself the first thing the Governor
needs analysis for, and because RFC-100 §6.0 makes a briefed number "a
statement of fact, not a grant of authority" — something EECOM may neither rely
on nor overturn. The analysis is RFC §0; the decision is **GD-1**.

---

## Architecture Summary

Foundry reports values and cannot decompose any of them. RFC-017 defines the
contract by which any value in any domain can be explained.

A **Value Provenance** is the deterministic, reproducible explanation of one
observable value: the contributions that produce it, each anchored in immutable
canonical facts, together with a **derived and unfalsifiable** statement of how
completely those contributions account for it.

The problem is evidenced, not asserted. Six defects, each with a file and line:

| # | Defect | Evidence |
|---|---|---|
| 1 | References are a flat bag; the rendered honesty signal is a **count** | `core/metrics.py:57-59`; `mission_control.py:1566`, `:2012` |
| 2 | The decomposition is computed and discarded — including the ownership share that determines part of the pension figure and **never enters the reference list** | `finance/metrics.py:546-550`; `finance/pension_metrics.py:153-180` |
| 3 | An explanation already exists, in **display strings** — the relationship between whole and parts survives only in a `display_group` and an English `qualifier` | `finance/mortgage_assessment.py:716-732` |
| 4 | Completeness is computed and then written into **prose** | `finance/mortgage_assessment.py:816-824` |
| 5 | Evidence is **over-attributed**: the employee-contribution figure is supported, on the record, by employer evidence | `finance/pension_assessment.py:1197`, `:1213` |
| 6 | Exclusions disappear and a partial sum reports `status="available"`; one exclusion path leaves **no trace at all** | `finance/metrics.py:540-549`, `:644-651`; `finance/pension_metrics.py:154-155` |

Defect 5 is not a coding error a careful author would avoid: `MetricResult` has
one reference bag per result and nowhere to put a per-component association.
The defect is in the contract, which is why the answer is a contract.

---

## Key Decisions

| # | Decision | Basis |
|---|---|---|
| 1 | **Provenance is a deterministic projection with zero canonical events, in every phase** | storing it puts a fold's output into its own input and creates a second truth that can contradict the first; and storage relocates calculation drift into a contradiction rather than solving it (RFC §3.2, §3.4) |
| 2 | **Completeness and residual are derived by the framework, never declared by a domain** | a self-reported honesty flag is the first thing to rot. No participant can claim to have explained what it has not (RFC §4.5) |
| 3 | **Three contribution roles** — `increases`, `decreases`, `contextual` — describing arithmetic relationships, never domain meanings | `contextual` is the only honest way to express that an ownership share or an exchange rate participated without carrying a share. Signed quantities were considered and rejected (RFC §13) |
| 4 | **Two node kinds** — `observed` / `derived` — answering only "does the explanation continue here?" | quality is already modelled by `EVIDENCE_GRADE` (`core/vocab.py:90-93`) and is not duplicated |
| 5 | **Bitemporal queries** (`as_of` + `known_at`), adopting RFC-011's existing mechanism (`core/acquisition.py:946-949`) | this is what makes "historical explanations are never rewritten" true, rather than aspirational |
| 6 | **Core routes and verifies; Core never calculates.** It may sum and compare within one unit and may never transform one | the `MetricRegistry` discipline (`core/metrics.py:103-105`) and the RFC-012 R9 mitigation: a missing explainer yields **no** provenance, never an invented one |
| 7 | **Bounded, lazy recursion; a cycle is a refusal, not a truncation** | `ValuationLenses.market_value` (`core/acquisition.py:1002-1015`) already recurses eagerly and flattens the structure at `:1007` — the defect, reproduced by the fix |

---

## Contracts Frozen or Proposed

**Proposed, none frozen** (freeze is a Governor act):

- **Vocabularies (all closed, all new):** `PROVENANCE_NODE_KIND` (2 values),
  `CONTRIBUTION_ROLE` (3), `EXPLANATION_COMPLETENESS` (3, derived),
  `EXCLUSION_REASON` (3) — eleven values in total
- **Shapes:** `ValueReference`, `ProvenanceNode`, `Contribution`, `Exclusion`,
  `ExplanationDescriptor`
- **Seams:** `ValueExplainer` (Protocol), `ProvenanceResolver`
- **Fifteen invariants** (RFC §8) and **eight Phase 1 acceptance criteria**
  (RFC §11.1)

**Reused rather than re-invented:** `Subject` (`core/scope.py:21`),
`METRIC_STATUS` (`core/vocab.py:124-127`), `EVIDENCE_GRADE`, the bitemporal
read shape, the registry/descriptor seam pattern.

**Explicitly unchanged:** `MetricRequest`, `MetricResult`, `MetricProvider`,
`MetricRegistry`, `MissionDefinition`, `MissionAssessmentRequest`,
`MissionAssessment`, `MissionMilestone`, `TelemetryItem`, `MissionTarget`,
`TargetQuantity`, and every existing vocabulary. **No event kind is added, in
any phase.**

---

## Scope Exclusions

Declared in RFC §12 and restated here (FR-004): all implementation; all schema
changes; all event definitions; UI, Flight Deck, routes, forms and CLI; Mission
Assessment and any assessor change; capture, editing, correction and manual
attribution workflows; API endpoints and implementation classes; retrofitting
any shipped metric; caching and performance envelope; cross-decomposition
double-count detection; the RFC-013 numbering debt, RFC-014, and mission
instantiation; and any architecture for RFC-018/019/020.

**The index omission is deliberate and is declared, not hidden.**
[`docs/rfcs/index.md`](rfcs/index.md) is **not** amended by this burn, because
amending it would assert a number the Governor has not ruled — and the row it
currently carries ("RFC-017 is reserved for *Asset Detail & Provenance
Investigation*") is a **correct record of a live ruling** that EECOM has no
authority to overwrite. This is the RFC-016 Phase 1 precedent applied
unchanged. The resulting **FR-017 documentation-coherence gap is real and is
declared**: on a GD-1 ruling, a follow-on governance burn adds the index row,
records the GD-1 amendment beside the original ruling (retaining it verbatim,
per RFC-100 §9.2), and closes the gap.

`PROJECT_STATUS.md` and `CHANGELOG.md` were **not** edited: RFC-100 §2.7 makes
them TELMU's property, and no merged implementation exists to record.

---

## Technical Debt

Nine watch items, all named in RFC §15:

| # | Item |
|---|---|
| W1 | Nothing compels a provider to publish a decomposition |
| W2 | Cross-decomposition double counting is undetectable |
| W3 | Executable historical calculation versions are not retained |
| W4 | Recursive expansion multiplies an already-uncached per-request replay cost |
| W5 | Shipped over-attribution persists until a phase adopts provenance |
| W6 | The word *provenance* now has five meanings in the repository |
| W7 | The assessment registry's blanket `except Exception` masks failure origin |
| W8 | Core cannot verify domain scope containment during expansion |
| W9 | Core cannot verify that an anchor supports a node's quantity |

**W3, W4, W5 and W7 are pre-existing.** They are recorded so they are never
mistaken for something this RFC introduced, and none is fixed here.

---

## Risks

| Risk | Mitigation |
|---|---|
| The framework becomes a second calculation layer — the RFC-012 R9 failure mode | Core may sum and compare within one unit and may never transform one (RFC §6.1). A missing explainer yields no provenance, never an invented one. Asserted by P1-A and P1-B |
| A consumer surface is built before a **partial** explanation exists, and treats `partial` as an error | Proposed binding sequencing rule (RFC §11): Phase 3 — pension wealth, chosen *because* it is partial — ships before any consumer. The RFC-015 G6 precedent, on the same argument |
| Domains adopt the contract by wrapping today's flat reference bags, carrying today's over-attribution into the new shape | Phase 2 and Phase 3 acceptance must assert that the `pension_assessment.py:1213` over-attribution is **not** reproduced. Named as W5 rather than assumed away |
| Recursive expansion degrades an already-uncached replay path | Depth bound is mandatory, not advisory (RFC §5.1); it is also the denial-of-service mitigation in RFC §9 |
| A framework about honesty ships an authorisation guarantee it cannot enforce | Corrected before commit by self-review **A7**: Core guarantees no scope substitution; domain containment is a stated per-domain obligation (W8) |
| Freeze is granted while five Phase 1 blocking decisions are open | GD-2 through GD-6 are called out in RFC §14 and again below. A freeze leaving them open hands BOOSTER the storage model, the vocabularies, the honesty rule and Core's arithmetic bound to settle during implementation — the FR-013 failure |

---

## Self-Review Outcome

[`docs/reviews/RFC-017-architecture-self-review.md`](reviews/RFC-017-architecture-self-review.md)
— **ten amendments applied before commit, six residuals recorded.**

Three mattered, and they share a shape: each was a rule that read correctly and
could not be satisfied.

- **A4** — the draft's unit rule ("a contribution whose unit differs from its
  parent's is refused") would have refused **every legitimate contextual
  factor**, including the ownership share whose invisibility is defect 2 above.
  Unit agreement now binds additive roles only.
- **A5** — `Contribution.quantity` meant "share of the parent" for additive
  roles and "the factor's own magnitude" for contextual ones. One field, two
  meanings, disambiguated by a sibling enum: the exact ambiguity the RFC exists
  to remove. It is now required for additive roles and absent for contextual.
- **A7** — the draft asserted, as a Phase 1 criterion, that expansion never
  surfaces a contributor outside the requesting scope. **Core cannot check
  that**: `resolve_scope` (`core/scope.py:29-53`) takes no view on domain
  ownership by design. This is the same class of error RFC-016's self-review
  caught in its own draft (A3), and it is the class most likely to survive into
  implementation because it reads like a security guarantee.

Also amended: canonical storage shown to relocate rather than solve calculation
drift (A1); `completeness = None` for terminal and unvalued nodes (A2, A8);
expanded-contributor agreement verification (A6); folding `Exclusion` into
`Contribution` considered and rejected with its reason (A9); deterministic
ordering made part of the contract (A10).

---

## Governor Decisions Required

**Ten, none ruled.** One blocks the freeze; five block Phase 1.

| # | Decision | Blocks |
|---|---|---|
| **GD-1** | **The RFC number** (RFC §0) — file here and re-earmark the *Asset Detail & Provenance Investigation* surface to a successor number by dated ruling amending RFC-016's GD-1 (**R1**), or renumber this document and leave RFC-017 reserved (**R2**) | **freeze** |
| **GD-2** | Deterministic projection with zero canonical events, in every phase | **Phase 1** |
| **GD-3** | The four closed vocabularies and their eleven values | **Phase 1** |
| **GD-4** | Completeness is derived, never declared | **Phase 1** |
| **GD-5** | Core's arithmetic bound — sum and compare within one unit; never transform one | **Phase 1** |
| **GD-6** | Bounded, lazy recursion with cycle refusal | **Phase 1** |
| GD-7 | Sequencing: a partial explanation ships before any consumer surface | Phase 3/4 |
| GD-8 | Whether an assessor may be *required* to consult provenance (W1) — recommendation: **defer** | Phase 4 |
| GD-9 | Whether `MetricResult`'s reference bag is eventually superseded (§11 Phase 5) — recommendation: **defer** | Phase 5 |
| GD-10 | RFC-018/019/020 — recommendation: **record as direction only**; RFC §0.4 raises three collisions, including that "RFC-019 — Mission Assessment" names a boundary RFC-006 already shipped | — |

**EECOM raises GD-1 and does not resolve it.** RFC-016's ruling GD-1 is
recorded, dated and attributable, and RFC-100 §2.4 gives EECOM no authority to
amend it. The recommendation is **R1**, on the same two distinguishing facts
that carried R1 in RFC-016 §0.3 — the displacement would be *decided and
recorded*, and the displaced boundary is unstarted — plus one this case adds:
the substrate is prerequisite to the surface, so sequencing it first is correct
regardless of which number each takes.

---

## Files Changed

| File | Change |
|---|---|
| `docs/rfcs/RFC-017-value-provenance-framework.md` | new — the architecture |
| `docs/reviews/RFC-017-architecture-self-review.md` | new — adversarial self-review |
| `docs/rfc-017-architecture-report.md` | new — this report |

**No production source, test, fixture, template, CSS or runtime configuration
is touched** (FR-013, RFC-100 §3.1 rule 3). Documentation exclusively. No
existing document is amended, including [`docs/rfcs/index.md`](rfcs/index.md)
and the frozen RFC-015 and RFC-016 documents.

---

## Validation

- `git diff --stat main...HEAD` contains only the three new documents above.
- `tests/test_docs_governance.py` — relative-Markdown-link resolution passes
  for the new documents.
- Every repository claim in the RFC and the self-review cites a file and line,
  and each was read during this burn: `eventlog.py`, `canon.py`, `kernel.py`,
  `core/metrics.py`, `core/vocab.py`, `core/scope.py`, `core/grammar.py`,
  `core/evidence.py`, `core/acquisition.py`, `core/mission_assessment.py`,
  `finance/metrics.py`, `finance/pension_metrics.py`, `finance/aggregation.py`,
  `finance/pension_evidence.py`, `finance/mortgage_evidence.py`,
  `finance/pension_assessment.py`, `finance/mortgage_assessment.py`,
  `mission_control.py`, `docs/architecture.md`.
- The claim that the ownership `weight` never enters the pension reference list
  (defect 2) was verified by reading `pension_metrics.py:153-160` in full, not
  by grep.
- The claim that four exclusion paths append a limitation and one does not
  (defect 6) was verified against `pension_metrics.py:129-155`.
- **Full test suite not run** — no source changed, so there is nothing this
  burn could have broken.

---

## Repository State

| | |
|---|---|
| Branch | `claude/rfc-017-value-provenance-5ixkye` |
| Implementation files changed | **none** |
| Committed | yes — architecture package only |
| Pushed | yes |
| PR | opened as **draft**; not for merge pending Governor review and a GD-1 ruling (FR-005) |

---

## Recommendation

**Verdict: GO — the architecture package is complete and ready for Governor
review, subject to a ruling on GD-1.**

The framework is smaller than the problem it addresses, which was the
Governor's stated guidance: four vocabularies, eleven values, five shapes, one
seam, zero events, and one rule — **completeness is derived, never declared** —
that no participant can subvert. It is precise enough that Phase 1 requires no
architectural invention: what a provenance record is, what is stored (nothing),
what is verified, what is refused, how recursion terminates, what Core may and
may not compute, and what "done" means are all decided in the document.

**Requested next step:** Governor review, ruling **GD-1 first** — because the
number governs whether this document may be indexed at all — and **GD-2 through
GD-6 alongside any freeze**, each of which carries an EECOM recommendation and
needs no further analysis.

**Do not brief BOOSTER.** No implementation is authorised until the
architecture receives a formal GO and is frozen. On freeze, the freeze record
is the Governor's artefact to issue — this burn does not write one, because a
freeze record written by the party seeking the freeze is not evidence
(RFC-100 §1.2).

**One dependency for whoever holds the pen after a GD-1 ruling:** the index row
withheld above (FR-017) should be added in the same governance burn that
records the ruling, so the coherence gap closes with the decision rather than
outliving it.
